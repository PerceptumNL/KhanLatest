from __future__ import absolute_import

from third_party.agar.test import BaseTest

import auth.tokens
import user_models
from app import App
from auth.models import UserNonce
from testutil import testsize


class CredentialTest(BaseTest):
    def setUp(self):
        super(CredentialTest, self).setUp()
        self.orig_recipe_key = App.token_recipe_key
        App.token_recipe_key = 'secret recipe'

    def tearDown(self):
        App.token_recipe_key = self.orig_recipe_key
        super(CredentialTest, self).tearDown()

    def make_user(self, email):
        u = user_models.UserData.insert_for(email, email)
        u.put()
        return u

    @testsize.medium()
    def test_password_validation(self):
        u = self.make_user('bob@example.com')

        # No pw yet. Nothing should pass
        self.assertFalse(u.validate_password('password'))

        u.set_password('Password1')
        self.assertFalse(u.validate_password('password'))
        self.assertTrue(u.validate_password('Password1'))

    @testsize.medium()
    def test_updating_password(self):
        u = self.make_user('bob@example.com')

        u.set_password('Password1')
        token = auth.tokens.AuthToken.for_user(u)
        self.assertTrue(token.is_authentic(u))

        u.set_password('NewS3cr3t!')
        self.assertFalse(u.validate_password('Password1'))
        self.assertTrue(u.validate_password('NewS3cr3t!'))

        # The old token should be invalidated
        self.assertFalse(token.is_authentic(u))


class NonceTest(BaseTest):
    def make_user(self, email):
        u = user_models.UserData.insert_for(email, email)
        u.put()
        return u

    def test_nonce_types_distinct(self):
        u = self.make_user('bob@example.com')
        type1 = UserNonce.make_for(u, "type1")
        self.assertTrue(UserNonce.get_for(u, "type2") is None)
        self.assertEquals(type1.value, UserNonce.get_for(u, "type1").value)

    def test_nonce_values_are_user_specific(self):
        bob = self.make_user('bob@example.com')
        joe = self.make_user('joe@example.com')
        UserNonce.make_for(bob, "type")

        self.assertTrue(UserNonce.get_for(joe, "type") is None)

    def test_nonces_dont_keep_growing(self):
        u = self.make_user('bob@example.com')
        # Subsequent calls for make_for overwrite existing nonce
        # values of the same type.
        value1 = UserNonce.make_for(u, "type1").value
        value2 = UserNonce.make_for(u, "type1").value
        self.assertNotEquals(value1, value2)
        self.assertEquals(1, UserNonce.all().ancestor(u).count())
