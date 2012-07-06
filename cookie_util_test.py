

import cookie_util
import os
import unittest


class CookieTest(unittest.TestCase):
    def setUp(self):
        super(CookieTest, self).setUp()

        self.orig_cookies = None
        if 'HTTP_COOKIE' in os.environ:
            self.orig_cookies = os.environ.get('HTTP_COOKIE')

    def tearDown(self):
        if self.orig_cookies is not None:
            os.environ['HTTP_COOKIE'] = self.orig_cookies
        elif 'HTTP_COOKIE' in os.environ:
            del os.environ['HTTP_COOKIE']
        self.orig_cookies = None
        super(CookieTest, self).tearDown()

    def fake_cookie_val(self, value):
        os.environ['HTTP_COOKIE'] = value

    def test_parsing_empty_cookies(self):
        cookies = cookie_util.get_all_cookies()

        # Coerces to False
        self.assertFalse(cookies)

        # But can still dereference as a dict (though value is always empty)
        self.assertFalse(cookies.get('foo'))

    def test_parsing_normal_cookies(self):
        self.fake_cookie_val('foo=bar;')
        cookies = cookie_util.get_all_cookies()
        
        self.assertEquals('bar', cookies.get('foo').value)
        self.assertIsNone(cookies.get('nonexisttent'))

    def test_parsing_cookies_with_corrupt_values(self):
        self.fake_cookie_val('goodvalue=123; keyonly=; invalid@chars=ignore;')
        cookies = cookie_util.get_all_cookies()
        
        self.assertEquals('123', cookies.get('goodvalue').value)
        self.assertEquals('', cookies.get('keyonly').value)
        self.assertIsNone(cookies.get('invalid@chars'))
