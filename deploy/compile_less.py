# -*- coding: utf-8 -*-
import os
import subprocess
import sys
import npm

# this path manipulation is needed so that this file can import the packages.py
pwd = os.path.abspath(".")
if pwd not in sys.path:
    sys.path.append(pwd)

import js_css_packages.iterator
import js_css_packages.packages


def validate_env():
    path = npm.package_installed("lessc")
    if path:
        subprocess.call([path],
                        stderr=subprocess.STDOUT,
                        stdout=subprocess.PIPE)
    else:
        sys.exit("Can't find less compiler. Check that it's installed.")


def compile_template(dir_path, file_name):
    less_path = npm.package_installed("lessc")

    input_path = os.path.join(dir_path, file_name)
    output_path = "%s.css" % os.path.join(dir_path, file_name)

    try:
        subprocess.check_call([less_path, input_path, output_path])
    except subprocess.CalledProcessError, e:
        sys.exit(e.returncode)

    print "Compiled to %s" % output_path


def compile_less(packages, root_dir):
    for _, package_path, files in js_css_packages.iterator.resolve_files(
            root_dir, packages, ".css"):
        less_files = [f for f in files if f.endswith(".less")]
        if len(less_files) > 1:
            raise Exception("Only one less file allowed per package: " +
            "see https://sites.google.com/a/khanacademy.org" +
            "/forge/technical/less-stylesheets")
        elif less_files:
            compile_template(package_path, less_files[0])


if __name__ == "__main__":
    validate_env()
    compile_less(js_css_packages.packages.stylesheets, "../stylesheets")
