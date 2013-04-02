import os
import urllib

import url_util
from app import App

try:
    import unittest2 as unittest
except ImportError:
    import unittest


class TestUrl(unittest.TestCase):
    def setUp(self):
        super(TestUrl, self).setUp()

        self.orig_app_dev_server = App.is_dev_server
        App.is_dev_server = False
        self.orig_host = None

    def tearDown(self):
        App.is_dev_server = self.orig_app_dev_server

    def stub_server_name(self, stubbed_name):
        if 'HTTP_HOST' in os.environ:
            self.orig_host = os.environ['HTTP_HOST']
        else:
            self.orig_host = None
        os.environ['HTTP_HOST'] = stubbed_name

    def restore_server_name(self):
        if self.orig_host:
            os.environ['HTTP_HOST'] = self.orig_host
        else:
            del os.environ['HTTP_HOST']

    def test_url_insecuring_on_normal_url(self):
        self.stub_server_name('www.khanacademie.nl')

        # relative URL
        self.assertEqual("http://www.khanacademie.nl/postlogin",
                         url_util.insecure_url("/postlogin"))

        # absolute URL
        self.assertEqual("http://www.khanacademie.nl/postlogin",
                         url_util.insecure_url("https://www.khanacademie.nl/postlogin"))
        self.restore_server_name()

    def test_url_securing_on_appspot_url(self):
        self.stub_server_name("non-default.khanacademie.appspot.com")
        # relative url
        self.assertEqual("https://non-default.khanacademie.appspot.com/foo",
                         url_util.secure_url("/foo"))
        # Absolute url
        self.assertEqual("https://non-default.khanacademie.appspot.com/foo",
                         url_util.secure_url("http://non-default.khanacademie.appspot.com/foo"))
        self.restore_server_name()

    def test_url_insecuring_on_appspot_url(self):
        self.stub_server_name("non-default.khanacademie.appspot.com")
        # relative url
        self.assertEqual("http://non-default.khanacademie.appspot.com/foo",
                         url_util.insecure_url("/foo"))
        # Absolute url
        self.assertEqual("http://non-default.khanacademie.appspot.com/foo",
                         url_util.insecure_url("https://non-default.khanacademie.appspot.com/foo"))
        self.restore_server_name()

    def test_detection_of_ka_urls(self):
        def is_ka_url(url):
            return url_util.is_khanacademy_url(url)

        self.stub_server_name("www.khanacademie.nl")
        print url_util.static_url("/images/foo")
        self.assertTrue(is_ka_url("/relative/url"))
        self.assertTrue(is_ka_url(url_util.absolute_url("/relative/url")))
        self.assertTrue(is_ka_url(url_util.static_url("/images/foo")))
        self.assertTrue(is_ka_url("http://www.khanacademie.nl"))
        self.assertTrue(is_ka_url("http://smarthistory.khanacademie.nl"))
        self.assertTrue(is_ka_url("http://www.khanacademie.nl/"))
        self.assertTrue(is_ka_url("http://www.khanacademie.nl/foo"))
        self.restore_server_name()

    def test_detection_of_non_ka_urls(self):
        self.assertFalse(url_util.is_khanacademy_url("http://evil.com"))
        self.assertFalse(url_util.is_khanacademy_url("https://khanacademie.phising.com"))

    def test_opengraph_url_for_dev_server(self):
        self.stub_server_name("localhost")
        self.assertEqual("http://www.khanacademie.nl/foo",
                         url_util.opengraph_url("/foo"))

    def test_opengraph_url_for_appspot_url(self):
        self.stub_server_name("non-default.khanacademie.appspot.com")
        self.assertEqual("http://www.khanacademie.nl/foo",
                         url_util.opengraph_url("/foo"))

    def test_opengraph_url_for_ka_org_url(self):
        self.stub_server_name("www.khanacademie.nl")
        self.assertEqual("http://www.khanacademie.nl/foo",
                         url_util.opengraph_url("/foo"))

    def test_opengraph_url_for_subdomain_ka_url(self):
        self.stub_server_name("beta.wild.khanacademie.nl")
        self.assertEqual("http://beta.wild.khanacademie.nl/foo",
                         url_util.opengraph_url("/foo"))

    def test_iri_to_uri_encodes_to_utf8(self):
        original_unicode = u"/\u00fe/\u00f4?\u00ef=\u2021"

        # verify correct encoding
        encoded_string = url_util.iri_to_uri(original_unicode)
        self.assertIsInstance(encoded_string, str)
        self.assertEqual("/%C3%BE/%C3%B4?%C3%AF=%E2%80%A1", encoded_string)

        # verify that we can roundtrip back to the original unicode
        decoded_string = urllib.unquote(encoded_string).decode("utf-8")
        self.assertIsInstance(decoded_string, unicode)
        self.assertEqual(original_unicode, decoded_string)

    def test_iri_to_uri_is_idempotent(self):
        unicode_string = u"/\u00fe/\u00f4?\u00ef=\u2021"
        self.assertEqual(
            url_util.iri_to_uri(unicode_string),
            url_util.iri_to_uri(url_util.iri_to_uri(unicode_string)))

    def test_iri_to_uri_is_sane_for_complex_url(self):
        # test without the added complexity of unicode characters just
        # to sanity check that a complex URL is not mangled
        unicode_string = (u"http://user:password@www.host.com/with/path/and"
                          u"?query=string&is=sane")
        encoded_string = url_util.iri_to_uri(unicode_string)
        self.assertIsInstance(encoded_string, str)
        self.assertEqual(unicode_string, encoded_string)
