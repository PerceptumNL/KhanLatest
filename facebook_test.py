
import base64
import hashlib
import hmac
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import facebook


class FacebookTest(unittest.TestCase):
    def make_signed_req(self, sig, payload):
        return ".".join([base64.urlsafe_b64encode(sig),
                         base64.urlsafe_b64encode(payload)])

    def assertSafeFail(self, sig, payload):
        actual = facebook.parse_signed_request(
            self.make_signed_req(sig, payload), "secret")
        self.assertEquals({}, actual)

    @mock.patch('logging.error')
    def test_parsing_invalid_requests_doesnt_throw(self, log_error):
        self.assertEquals({},
                          facebook.parse_signed_request("invalid", "secret"))
        self.assertSafeFail("not", "encoded properly!")
        self.assertSafeFail("notjson", "blah")
        self.assertSafeFail("notdict", "null")
        self.assertSafeFail("notdict", "[]")
        self.assertSafeFail("notHMAC256", "{}")
        self.assertSafeFail("stillnotHMAC256", '{"algorithm": "invalid"}')
        self.assertSafeFail("sigmismatch", '{"algorithm": "HMAC-SHA256"}')

        self.assertEquals(8, log_error.call_count)

    def test_parsing_valid_request(self):
        payload = '{"algorithm": "HMAC-SHA256", "user_id": "1234"}'
        signature = hmac.new("secret",
                             base64.urlsafe_b64encode(payload),
                             hashlib.sha256).digest()
        signed = self.make_signed_req(signature, payload)

        parsed = facebook.parse_signed_request(signed, "secret")
        self.assertEquals("1234", parsed.get("user_id", None))
