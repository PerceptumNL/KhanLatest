import fnmatch
import os
import re
import simplejson
import subprocess
import tempfile


from handlebars.render import handlebars_template
import npm
from testutil import testsize

try:
    import unittest2 as unittest
except ImportError:
    import unittest


# these are "large" tests because npm phones home to check versions
# TODO(chris): move dependency checking out of the tests
@testsize.large()
def setUpModule():
    if not npm.check_dependencies():
        raise AssertionError('npm dependency check failed. Is npm installed?')


# Unit test to ensure that Python & JS outputs match
class HandlebarsTest(unittest.TestCase):
    def test_handlebars_templates(self):
        matches = []
        for root, dirnames, filenames in os.walk('javascript'):
            for filename in fnmatch.filter(filenames, '*.handlebars.json'):
                package = re.match('javascript/([^-]+)-package', root)
                package = package.group(1)
                matches.append((package, root, filename))

        for match in matches:
            package = match[0]
            template_name = re.sub('\.handlebars\.json$', '', match[2])
            test_file = os.path.join(match[1], match[2])
            handlebars_file = re.sub('handlebars\.json$',
                                     'handlebars',
                                     test_file)

            # Load test file data
            in_file = open(test_file, 'r')
            source = in_file.read()
            test_data = simplejson.loads(source)

            print "Testing %s..." % handlebars_file

            # Run Python template (append extra newline to make
            # comparison with JS easier)
            python_output = str(handlebars_template(package,
                                                    template_name,
                                                    test_data)) + "\n"

            # Run JS template in node.js
            tmp = tempfile.TemporaryFile()
            subprocess.call(
                [
                    "node",
                    "javascript/test/handlebars-test.js",
                    handlebars_file,
                    test_file
                ],
                stdout=tmp)
            tmp.seek(0, 0)
            js_output = str(tmp.read())

            if js_output != python_output:
                f = open("unittest-%s-python.txt" % template_name, "w")
                f.write(python_output)
                f = open("unittest-%s-js.txt" % template_name, "w")
                f.write(js_output)
                print ("Test failed! Wrote output to unittest-%s-python.txt "
                       "and unittest-%s-js.txt."
                       % (template_name, template_name))

            self.assertEqual(js_output, python_output)
