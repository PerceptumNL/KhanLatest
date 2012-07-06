# -*- coding: utf-8 -*-
import os
import subprocess
import sys
import shutil
import npm
import inspect
import types
import re

# Include "." in python path so pybars can be imported.
sys.path.append(os.path.abspath("."))
from third_party.pybars import Compiler


def validate_env():
    """ Ensures that pre-requisites are met for compiling handlebar templates.
    
    TODO: point to documents when they're made.
    Handlebars doc: https://github.com/wycats/handlebars.js/
    """
    handlebars_path = npm.package_installed("handlebars")
    if handlebars_path:
        subprocess.call([handlebars_path],
                        stderr=subprocess.STDOUT,
                        stdout=subprocess.PIPE)
    else:
        sys.exit("Can't find handlebars. Did you install it?")
        

def compile_template(root_path, rel_path, file_name):
    """ Compiles a single template into an output that can be used by the
    JavaScript client.
    
    This logic is dependent on javascript/shared-package/templates.js
    
    """
    handlebars_path = npm.package_installed("handlebars")
    try:
        dir_path = os.path.join(root_path, rel_path)
        
        # Total hack to rename the file temporarily to be namespaced. There
        # is no way to tell handlebars to prefix the resulting template with
        # a namespace, so we need to rename the file temporarily.
        qualified_name = file_name
        while True:
            head, tail = os.path.split(rel_path)
            if tail:
                qualified_name = "%s_%s" % (tail, qualified_name)
            else:
                break
            rel_path = head
        
        input_path = os.path.join(dir_path, qualified_name)
        shutil.copyfile(os.path.join(dir_path, file_name), input_path)
        
        # Append ".js" to the template name for the output name.
        output_path = "%s.js" % os.path.join(dir_path, file_name)
        
        # "-m" for minified output
        # "-f" specifies output file
        subprocess.call([handlebars_path, "-m", "-f", output_path, input_path],
                        stderr=subprocess.STDOUT,
                        stdout=subprocess.PIPE)
        os.remove(input_path)
        print "Compiled to %s" % output_path
    except subprocess.CalledProcessError:
        #sys.exit("Error compiling %s" % file_path)
        pass


def compile_template_to_python(root_path, rel_path, file_name):
    dir_path = os.path.join(root_path, rel_path)
    input_path = os.path.join(dir_path, file_name)
    test_path = input_path + ".json"

    # We intentionally ignore Handlebars templates that don't have unit tests
    # when compiling to Python. If someday all templates have unit tests we
    # should emit an error here.
    if not os.path.exists(test_path):
        return None

    package_name = rel_path.replace("-", "_").split("_")[0]
    original_function_name = os.path.splitext(file_name)[0]
    partial_name = package_name + "_" + original_function_name
    function_name = original_function_name.replace("-", "_")

    out_dir_path = os.path.join("compiled_templates",
                                package_name + "_package")
    output_path = os.path.join(out_dir_path, function_name) + ".py"
    init_path = os.path.join(out_dir_path, "__init__.py")

    compiler = Compiler()

    in_file = open(input_path, 'r')
    source = unicode(in_file.read())
    # Pybars doesn't handle {{else}} for some reason
    source = re.sub(r'{{\s*else\s*}}', "{{^}}", source)
    template = compiler.compile(source)

    output_string = []
    output_string.append("from third_party.pybars._compiler import strlist, "
                         "_pybars_, Scope, escape, resolve, partial")
    output_string.append("")

    def write_fn(template, name, indent):

        output_string.append("%sdef %s(context, helpers=None, partials=None):"
                             % (indent, name))
        output_string.append("%s    pybars = _pybars_" % indent)
        output_string.append("")

        output_string.append("%s    # Begin constants" % indent)

        for name, val in template.func_globals.items():
            if name.startswith("constant_"):
                if isinstance(val, unicode):
                    output_string.append("%s    %s = %s" %
                                         (indent, name, repr(val)))

        output_string.append("")

        for name, val in template.func_globals.items():
            if name.startswith("constant_"):
                if isinstance(val, types.FunctionType):
                    write_fn(val, name, indent + "    ")

        output_string.append("%s    # End constants" % indent)

        compiled_fn = inspect.getsource(template)
        fn_lines = compiled_fn.split("\n")

        for line in fn_lines[1:]:
            output_string.append("%s%s" % (indent, line))

    write_fn(template, function_name, "")

    if not os.path.exists(out_dir_path):
        os.makedirs(out_dir_path)

    out_file = open(init_path, 'w')
    out_file.close()

    out_file = open(output_path, 'w')
    out_file.write("\n".join(output_string))
    out_file.close()

    print "Compiled to %s" % output_path

    return (partial_name, package_name, function_name)


def compile_templates():
    partials_buffer = "from handlebars.render import handlebars_template\n\n"
    partials_buffer += "handlebars_partials = {\n"

    root_path = "javascript"
    rel_path_index = len(root_path) + 1
    for dir_path, dir_names, file_names in os.walk(root_path):
        for file_name in file_names:
            if file_name.endswith(".handlebars"):
                # os.path.relpath is not available until Python 2.6
                compile_template(root_path,
                                 dir_path[rel_path_index:],
                                 file_name)

                partial_info = compile_template_to_python(
                    root_path, dir_path[rel_path_index:], file_name)

                if partial_info:
                    partial_string = (
                        "    \"%s\": "
                        "lambda params, partials=None, helpers=None: "
                        "handlebars_template(\"%s\", \"%s\", params),\n" %
                        (partial_info[0], partial_info[1], partial_info[2]))
                    partials_buffer += partial_string

    partials_buffer += "}\n"

    out_file = open(os.path.join("compiled_templates", "__init__.py"), 'w')
    out_file.write(partials_buffer)
    out_file.close()

if __name__ == "__main__":
    validate_env()
    compile_templates()
