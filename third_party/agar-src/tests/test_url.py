from webapp2 import WSGIApplication
from webtest import Request
from agar.url import uri_for
from agar.test import BaseTest


class UriTest(BaseTest):
    def setUp(self):
        self.method = uri_for
        WSGIApplication.request = Request.blank("/")
        super(UriTest, self).setUp()

    def test_get_uri(self):
        uri = self.method('api-v1')
        self.assertEqual(uri, '/api/v1/model1')

    def test_get_invalid_uri_name(self):
        try:
            invalid_uri_name = 'invalid-uri-name'
            uri = uri_for(invalid_uri_name)
            self.fail("Got uri '%s' for invalid uri name '%s'" % (uri, invalid_uri_name))
        except Exception, e:
            self.assertEqual(e.message, "Route named '%s' is not defined." % invalid_uri_name)
