import mock
import webapp2
import webtest

# unittest2 backports features from Python 2.7
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import wsgi_compat


class SetUnicodeHeaderName(webapp2.RequestHandler):
    def get(self):
        self.response.headers[u'bad_name'] = 'good_value'


class SetUnicodeHeaderValue(webapp2.RequestHandler):
    def get(self):
        self.response.headers['good_name'] = u'bad_value'


_app = webapp2.WSGIApplication([
        ('/unicode_header_name', SetUnicodeHeaderName),
        ('/unicode_header_value', SetUnicodeHeaderValue),
        ])

    
class WSGICompatHeaderMiddlewareTestCase(unittest.TestCase):
    def setUp(self):
        super(WSGICompatHeaderMiddlewareTestCase, self).setUp()
        app = wsgi_compat.WSGICompatHeaderMiddleware(_app)
        self.app = webtest.TestApp(app)

    @mock.patch('logging.warn')
    def test_log_bad_header_name_type(self, mock_warn):
        self.app.get('/unicode_header_name')
        mock_warn.assert_called_once_with(
            "Non-str header (u'bad_name', <type 'str'>)")

    @mock.patch('logging.warn')
    def test_log_bad_header_value_type(self, mock_warn):
        self.app.get('/unicode_header_value')
        mock_warn.assert_called_once_with(
            "Non-str header ('good_name', <type 'unicode'>)")
