import datetime
import getpass
import optparse
import os
import re
import subprocess
import sys
import threading
import urllib2
import webbrowser

sys.path.append(os.path.abspath("."))
sys.path.append(os.path.abspath("./tools/google_appengine/"))
import compress
import npm

def popen_results(args):
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    return proc.communicate()[0]


def popen_return_code(args, input=None):
    proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    proc.communicate(input)
    return proc.returncode

def check_deps():
    """Check if npm and friends are installed"""
    return npm.check_dependencies()


def delete_orphan_pyc_files(rootdir):
    print "Deleting 'orphan' .pyc files"
    for (dirpath, unused_dirnames, filenames) in os.walk(rootdir):
        fileset = set(filenames)
        pyc_files = [f for f in fileset
                     if f.endswith('.pyc') or f.endswith('.pyo')]
        for f in pyc_files:
            if f[:-1] not in fileset:   # the .py file isn't present
                os.unlink(os.path.join(dirpath, f))


def compile_handlebar_templates():
    print "Compiling handlebar templates"
    return 0 == popen_return_code([sys.executable,
                                   'deploy/compile_handlebar_templates.py'])


def compile_less_stylesheets():
    print "Compiling less stylesheets"
    return 0 == popen_return_code([sys.executable,
                                   'deploy/compile_less.py'])


def compress_js():
    print "Compressing javascript"
    compress.compress_all_javascript()


def compress_css():
    print "Compressing stylesheets"
    compress.compress_all_stylesheets()


def compress_exercises():
    print "Compressing exercises"
    subprocess.check_call(["ruby", "khan-exercises/build/pack.rb"])


def compile_templates():
    print "Compiling jinja templates"
    return 0 == popen_return_code([sys.executable,
                                   'deploy/compile_templates.py'])

def main():
    start = datetime.datetime.now()
    print "Checking for node and dependencies"
    #if not check_deps(): - We do this only once
    #    return

    # Delete obsolete .pyc files, that do not have an associated .py file.
    delete_orphan_pyc_files('.')

    if not compile_templates():
        print "Failed to compile jinja templates, bailing."
        return

    if not compile_handlebar_templates():
        print "Failed to compile handlebars templates, bailing."
        return

    if not compile_less_stylesheets():
        print "Failed to compile less stylesheets, bailing."
        return

    compress_js()
    compress_css()
    #compress_exercises() -- Fails on most of the old Dutch exercises.

    end = datetime.datetime.now()
    print "Done. Duration: %s" % (end - start)

if __name__ == "__main__":
    main()
