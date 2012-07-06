# -*- coding: utf-8 -*-
import os
import shutil
import sys


def append_paths():
    os.environ["SERVER_SOFTWARE"] = ""
    os.environ["CURRENT_VERSION_ID"] = ""

    # Poor-man's `which` command, to find out where appengine lives.
    for path in os.environ['PATH'].split(':'):
        if os.path.isdir(path) and 'dev_appserver.py' in os.listdir(path):
            break
    else:
        # Default to Mac's default location -- best we can do.
        path = ("/Applications/GoogleAppEngineLauncher.app/Contents/"
                "Resources/GoogleAppEngine-default.bundle/Contents/"
                "Resources/google_appengine")

    app_engine_path = os.path.join(os.path.dirname(path), 'google_appengine')
    if not os.path.isdir(app_engine_path):
        raise RuntimeError('%s is not a directory' % app_engine_path)

    sys.path.append(app_engine_path)
    import dev_appserver
    dev_appserver.fix_sys_path()

    # Also append the root of the appengine tree so we can load things
    # like config_jinja
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))


# Append app and GAE paths so we can simulate our app environment
# when precompiling templates (otherwise compilation will bail on errors)
append_paths()

# Pull in some jinja magic
from jinja2 import FileSystemLoader
import webapp2
from webapp2_extras import jinja2

# Using our app's standard jinja config so we pick up custom globals
# and filters
import config_jinja  # @UnusedImport


def compile_templates():

    src_path = os.path.join(os.path.dirname(__file__), "..", "templates")
    dest_path = os.path.join(os.path.dirname(__file__),
                             "..",
                             "compiled_templates.zip")

    jinja2.default_config["environment_args"]["loader"] = \
        FileSystemLoader(src_path)

    env = jinja2.get_jinja2(app=webapp2.WSGIApplication()).environment

    try:
        shutil.rmtree(dest_path)
    except:
        pass

    # Compile templates to zip, crashing on any compilation errors
    env.compile_templates(dest_path, extensions=["html", "json", "xml", "js"],
            ignore_errors=False, py_compile=False, zip='deflated')

if __name__ == "__main__":
    compile_templates()
