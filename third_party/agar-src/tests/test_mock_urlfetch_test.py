from google.appengine.api import urlfetch
from agar.test import MockUrlfetchTest

class MockHTTPRequestTest(MockUrlfetchTest):

    def test_get_google(self):
        self.set_response("http://google.com/foobar", "foobar", 404)
        
        result = urlfetch.fetch("http://google.com/foobar")

        self.assertEqual(404, result.status_code)
        self.assertEqual("foobar", result.content)

    def test_get_unregistered_url(self):
        self.assertRaises(Exception,  urlfetch.fetch, "http://google.com/foobar")

    def test_multiple_http_verbs_same_uri(self):
        self.set_response("http://example.com/v1/foobars", "test content")
        self.set_response("http://example.com/v1/foobars",
                          status_code=303,
                          method='POST',
                          headers={'Location': 'http://example.com/v1/foobars/123'})

        result1 = urlfetch.fetch("http://example.com/v1/foobars")

        self.assertEqual(200, result1.status_code)
        self.assertEqual("test content", result1.content)

        result2 = urlfetch.fetch("http://example.com/v1/foobars", method='POST', payload="foo=bar")

        self.assertEqual(303, result2.status_code)
        self.assertEqual(None, result2.content)
        
    def test_raise_download_error(self):
        self.set_response("http://example.com/", content=urlfetch.DownloadError("Deadline exceeded"))

        self.assertRaises(urlfetch.DownloadError,  urlfetch.fetch, "http://example.com/")
        
