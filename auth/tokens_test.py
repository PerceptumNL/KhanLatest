from __future__ import absolute_import

import datetime
from app import App
from third_party.agar.test import BaseTest

import auth.tokens as tokens
import user_models
from testutil import mock_datetime
from testutil import testsize

try:
    import unittest2 as unittest
except ImportError:
    import unittest


class TimestampTests(unittest.TestCase):
    def test_timestamp_creation(self):
        clock = mock_datetime.MockDatetime()

        def assertDatetimeSerializes():
            now = clock.utcnow()
            timestamp = tokens._to_timestamp(now)
            self.assertEquals(now, tokens._from_timestamp(timestamp))

        assertDatetimeSerializes()
        clock.advance_days(1)
        assertDatetimeSerializes()
        clock.advance_days(30)
        assertDatetimeSerializes()
        clock.advance_days(366)
        assertDatetimeSerializes()
        clock.advance(datetime.timedelta(seconds=1))
        assertDatetimeSerializes()
        clock.advance(datetime.timedelta(microseconds=1))
        assertDatetimeSerializes()


class TokenTests(BaseTest):
    def setUp(self):
        super(TokenTests, self).setUp()
        self.orig_recipe_key = App.token_recipe_key
        App.token_recipe_key = 'secret recipe'

    def tearDown(self):
        App.token_recipe_key = self.orig_recipe_key
        super(TokenTests, self).tearDown()

    def make_user(self, user_id, credential_version=None):
        u = user_models.UserData.insert_for(user_id, user_id)
        u.credential_version = credential_version
        u.put()
        return u

    def test_token_expires_properly(self):
        clock = mock_datetime.MockDatetime()
        u = self.make_user("userid1", "credential version 0")
        token = tokens.AuthToken.for_user(u, clock)

        time_to_expiry = datetime.timedelta(30)
        self.assertTrue(token.is_valid(u, time_to_expiry, clock))

        # The day before expiry
        clock.advance_days(29)
        self.assertTrue(token.is_valid(u, time_to_expiry, clock))

        # Right at expiring point!
        clock.advance_days(1)
        self.assertTrue(token.is_valid(u, time_to_expiry, clock))

        # Tick - it's now stale.
        clock.advance(datetime.timedelta(seconds=1))
        self.assertFalse(token.is_valid(u, time_to_expiry, clock))

    def test_token_invalidates_properly(self):
        clock = mock_datetime.MockDatetime()
        u = self.make_user("userid1", "credential version 0")
        token = tokens.AuthToken.for_user(u, clock)

        time_to_expiry = datetime.timedelta(30)
        self.assertTrue(token.is_valid(u, time_to_expiry, clock))

        # Pretend the user changed her password.
        u.credential_version = "credential version 1"
        u.put()
        self.assertFalse(token.is_valid(u, time_to_expiry, clock))

    def test_auth_token_parses(self):
        clock = mock_datetime.MockDatetime()
        u = self.make_user("userid1", "credential version 0")
        token = tokens.AuthToken.for_user(u, clock)

        parsed = tokens.AuthToken.for_value(token.value)
        time_to_expiry = datetime.timedelta(30)
        self.assertTrue(parsed.is_valid(u, time_to_expiry, clock))

    def test_user_retrieval_from_token(self):
        clock = mock_datetime.MockDatetime()
        u = self.make_user("userid1", "credential version 0")
        token = tokens.AuthToken.for_user(u, clock)

        retrieved = tokens.AuthToken.get_user_for_value(
            token.value, user_models.UserData.get_from_user_id, clock)
        self.assertEquals(retrieved.key(), u.key())

    @testsize.medium()
    def test_pw_reset_token_should_be_single_use(self):
        clock = mock_datetime.MockDatetime()
        u = self.make_user("userid1")
        u.set_password("seekrit one")
        pw_token = tokens.PasswordResetToken.for_user(u, clock)

        self.assertTrue(pw_token.is_valid(
                u, datetime.timedelta(1), clock))

        u.set_password("seekrit two")
        self.assertFalse(pw_token.is_valid(
                u, datetime.timedelta(1), clock))

    def test_pw_reset_token_resets_on_subsequent_creations(self):
        clock = mock_datetime.MockDatetime()
        u = self.make_user("userid1", "credential version 0")

        token1 = tokens.PasswordResetToken.for_user(u, clock)
        self.assertTrue(token1.is_valid(u, datetime.timedelta(1), clock))

        token2 = tokens.PasswordResetToken.for_user(u, clock)
        self.assertFalse(token1.is_valid(u, datetime.timedelta(1), clock))
        self.assertTrue(token2.is_valid(u, datetime.timedelta(1), clock))

    @testsize.medium()
    def test_pw_reset_token_does_not_reset_pw_until_used(self):
        clock = mock_datetime.MockDatetime()
        u = self.make_user("userid1")
        u.set_password("seekrit one")
        pw_token = tokens.PasswordResetToken.for_user(u, clock)

        self.assertTrue(pw_token.is_valid(
                u, datetime.timedelta(1), clock))

        # Didn't use the token-just issued it, so the existing pw should work
        self.assertTrue(u.validate_password("seekrit one"))
