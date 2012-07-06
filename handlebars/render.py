import sys
import re
import urllib
import logging
import copy
import traceback
import os.path


import api.jsonify
from app import App
from third_party.pybars import Compiler


# Helpers (from javascript/shared-package/handlebars-extras.js)


def handlebars_repeat(context, options, count):
    fn = options["fn"]
    ret = ""

    for i in xrange(0, count):
        ret = ret + u''.join(fn(context))

    return ret


def handlebars_to_login_redirect_href(context, destination):
    redirectParam = "/postlogin?continue=" + destination
    return "/login?continue=" + urllib.quote(redirectParam, '')


def handlebars_commafy(context, number):
    return re.sub(r'(\d)(?=(\d{3})+$)', r'\1,', str(number))


def handlebars_arraylength(context, array):
    return len(array)


def handlebars_multiply(context, num1, num2):
    val = unicode(float(num1) * float(num2))
    if val[-2:] == u".0":
        return val[:-2]
    return val


def handlebars_skillbar(context, end=0, start=0, exerciseStates={}):
    subcontext = copy.copy(exerciseStates)
    subcontext.update({"start": start, "end": end})
    return handlebars_template("shared", "skill-bar", subcontext)


def handlebars_ellipsis(context, data, length):
    text_stripped = re.sub("<[^>]*>", "", data)
    if len(text_stripped) < length:
        return text_stripped
    else:
        return text_stripped[:(length - 3)] + "..."


handlebars_helpers = {
    "repeat": handlebars_repeat,
    "toLoginRedirectHref": handlebars_to_login_redirect_href,
    "commafy": handlebars_commafy,
    "arrayLength": handlebars_arraylength,
    "multiply": handlebars_multiply,
    "skill-bar": handlebars_skillbar,
    "ellipsis": handlebars_ellipsis,
}


def handlebars_dynamic_load(package, name):
    """ Dynamically compile a Handlebars template.

    NOTE: This will do nothing in production mode!
    """

    if not App.is_dev_server:
        return None

    combined_name = "%s_%s" % (package, name)
    if combined_name in handlebars_partials:
        handlebars_partials[combined_name]

    logging.info("Dynamically loading %s-package/%s.handlebars."
                  % (package, name))

    test_file_name = ("clienttemplates/%s-package/%s.handlebars.json"
                      % (package, name))
    if not os.path.exists(test_file_name):
        logging.error("Attempting to call server-side template with"
                      " no test file. Looking for: %s"
                      % test_file_name)
        return None

    file_name = "clienttemplates/%s-package/%s.handlebars" % (package, name)

    in_file = open(file_name, 'r')
    source = unicode(in_file.read())
    # HACK: Pybars doesn't handle {{else}} for some reason
    source = source.replace("{{else}}", "{{^}}")

    matches = re.search('{{>[\s]*([\w\-_]+)[\s]*}}', source)
    if matches:
        for partial in matches.groups():
            (partial_package, partial_name) = partial.split("_")
            handlebars_dynamic_load(partial_package, partial_name)

    compiler = Compiler()
    function = compiler.compile(source)
    handlebars_partials[combined_name] = function

    return function


def handlebars_check_context(obj, path="context"):
    """ Validate parameters to Handlebars renderer.

    Only simple types may be passed into Handlebars template rendering.
    """

    if (obj is not None
        and not isinstance(obj, api.jsonify.SIMPLE_TYPES)
        and not isinstance(obj, (dict, list))):
        raise Exception(
            "Invalid type passed to handlebars_template at path '%s': %s"
            % (path, type(obj)))

    if isinstance(obj, dict):
        for key, child in obj.iteritems():
            handlebars_check_context(child, path + "[\"%s\"]" % key)
    elif isinstance(obj, list):
        for idx, child in enumerate(obj):
            handlebars_check_context(child, path + "[%d]" % idx)


def handlebars_template(package, name, context):
    """ Invoke a template and return the output string """

    handlebars_check_context(context)

    package_name = package.replace("-", "_")
    function_name = name.replace("-", "_")

    # Enable for debugging
    if False:
        logging.info("Rendering template %s.%s with context: %s" %
            (package, name, api.jsonify.jsonify(context)))

    module_name = ("compiled_templates.%s_package.%s"
                   % (package_name, function_name))

    function = None

    if App.is_dev_server:
        # In dev mode, load all templates dynamically
        function = handlebars_dynamic_load(package, name)

    else:
        # In production mode, dynamically load the compiled template module and
        # find the function

        if not module_name in sys.modules:
            try:
                __import__(module_name)
            except ImportError:
                logging.info("Import error: %s" % traceback.format_exc())

        if module_name in sys.modules:
            function = getattr(sys.modules[module_name], function_name)

    if function:
        try:
            ret = function(context,
                           helpers=handlebars_helpers,
                           partials=handlebars_partials)
            return u"".join(ret)
        except:
            logging.error("Exception running Handlebars template: %s"
                         % traceback.format_exc())
            return u""
    else:
        return u""


def render_from_jinja(package, name, context):
    """ Wrapper for rendering a Handlebars template from Jinja.

    This is provided in case we want to handle this case specially.
    """
    ret = handlebars_template(package, name, context)
    return ret

try:
    from compiled_templates import handlebars_partials
except:
    handlebars_partials = {}
    pass
