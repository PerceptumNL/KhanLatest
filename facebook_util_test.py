try:
    import unittest2 as unittest
except ImportError:
    import unittest

import facebook_util


class FacebookUtilTest(unittest.TestCase):
    def test_that_is_facebook_user_id_is_robust_to_none(self):
        """Some old users have null values in their user_id or
        user_email fields that may be passed in to this method. Better
        to return false (a valid response) than raise an exception."""
        self.assertFalse(facebook_util.is_facebook_user_id(None))
