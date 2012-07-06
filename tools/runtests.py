#!/usr/bin/env python

import optparse
import os
import sys
# For python2.5 install the unittest2 package
try:   # Work under either python2.5 or python2.7
    import unittest2 as unittest
except ImportError:
    import unittest

import xmlrunner

import appengine_tool_setup

USAGE = """%prog [options] [TEST_SPEC] ...

Run unit tests for App Engine apps.

This script will set up the Python path and environment. Test files
are expected to be named with a _test.py suffix.

TEST_SPEC   Specify tests by directory, file, or dotted name. Omit to
            use the current directory.

            Directory name: recursively search for files named *_test.py

            File name: find tests in the file.

            Dotted name: find tests specified by the name, e.g.,
            auth.tokens_test.TimestampTests.test_timestamp_creation,
            importer.autonow_test
"""


TEST_FILE_RE = '*_test.py'


def file_path_to_module(path):
    return path.replace('.py', '').replace(os.sep, '.')


def main(test_specs, should_write_xml, max_size, appengine_sdk_dir=None):
    appengine_tool_setup.fix_sys_path(appengine_sdk_dir)

    # This import needs to happen after fix_sys_path is run.
    from testutil import testsize
    testsize.set_max_size(max_size)

    num_errors = 0

    for test_spec in test_specs:
        loader = unittest.loader.TestLoader()
        if not os.path.exists(test_spec):
            suite = loader.loadTestsFromName(test_spec)
        elif test_spec.endswith('.py'):
            suite = loader.loadTestsFromName(file_path_to_module(test_spec))
        else:
            suite = loader.discover(test_spec,
                                    pattern=TEST_FILE_RE,
                                    top_level_dir=os.getcwd())

        if should_write_xml:
            runner = xmlrunner.XMLTestRunner(verbose=True,
                                             output='test-reports')
        else:
            runner = unittest.TextTestRunner(verbosity=2)

        result = runner.run(suite)
        if not result.wasSuccessful():
            num_errors += 1

    return num_errors


if __name__ == '__main__':
    parser = optparse.OptionParser(USAGE)
    parser.add_option('--sdk', dest='sdk', metavar='SDK_PATH',
                      help='path to the App Engine SDK')
    parser.add_option('--max-size', dest='max_size', metavar='SIZE',
                      choices=['small', 'medium', 'large'],
                      default='medium',
                      help='run tests this size and smaller ("small", '
                           '"medium", "large")')
    parser.add_option('--xml', dest='xml', action='store_true',
                      help='write xUnit XML')

    options, args = parser.parse_args()

    if not args:
        test_specs = [os.getcwd()]
    else:
        test_specs = args

    num_errors = main(test_specs, options.xml, options.max_size, options.sdk)
    sys.exit(min(num_errors, 127))    # exitcode of 128+ means 'signal'
