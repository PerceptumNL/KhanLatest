import mock

from google.appengine.api import users
from google.appengine.ext import db
from third_party.agar.test import BaseTest

import auth.tokens
import facebook_util
import request_cache
import user_models
import uid

# Ugh - this has to be here (after user_models) due to circular dependencies
from api.auth import auth_models


# shorthand notations
def _user_counts():
    return user_models.UserData.all().count()


def _cur_user():
    return user_models.UserData.current(create_if_none=False)


class OAuthMapTests(BaseTest):
    def setUp(self):
        super(OAuthMapTests, self).setUp()
        self._patches = []

    def tearDown(self):
        for p in self._patches:
            p.stop()

        request_cache.flush()
        super(OAuthMapTests, self).tearDown()

    # TODO(benkomalo): a lot of the stubbing is similar/copied from
    # login_tests.py and is probably useful in a general test
    # utility. Move it out.
    def mock_method(self, method_path, mocked_impl):
        patcher = mock.patch(method_path, mocked_impl)
        self._patches.append(patcher)
        patcher.start()

    def make_user(self, user_id, db_key_email, user_email):
        u = user_models.UserData.insert_for(user_id, db_key_email)
        u.user_email = user_email
        u.put()
        db.get(u.key())  # Flush db transaction.
        return u

    def make_google_user(self, google_user_id, email):
        google_user_id = uid.google_user_id(
                users.User(_user_id=google_user_id, email=email))
        return self.make_user(google_user_id,
                              db_key_email=email,
                              user_email=email)

    def make_fb_user(self, fb_id, email=None):
        fb_user_id = facebook_util.FACEBOOK_ID_PREFIX + str(fb_id)

        # Note - the db_key_email of Facebook users never change.
        return self.make_user(fb_user_id,
                              db_key_email=fb_user_id,
                              user_email=email or fb_user_id)

    def make_oauth_map(self):
        oauth_map = auth_models.OAuthMap()
        oauth_map.request_token_secret = "seekrit"
        oauth_map.request_token = "request token"
        oauth_map.callback_url = "/some_page"
        oauth_map.put()
        return oauth_map

    def fake_request(self, oauth_map):
        # The OAuth requests involve lots of callbacks, but essentially
        # it gets down to this call which needs to resolve the user from the
        # OAuthMap.
        oauth_map.get_user_data()

    def fake_google_auth(self, oauth_map, gid, email):
        oauth_map.google_request_token = "google request token"
        oauth_map.google_request_token_secret = "google request secret"
        oauth_map.google_access_token = "google access token"
        oauth_map.google_access_token_secret = "google access secret"
        oauth_map.put()
        
        self.mock_method(
            "api.auth.google_oauth_client."
                "GoogleOAuthClient.access_user_id_and_email",
             lambda client, oauth_map: (str(gid), email))
        
        self.fake_request(oauth_map)

    def fake_facebook_auth(self, oauth_map, fb_id, fb_email):
        oauth_map.facebook_authorization_code = "fb auth code"
        oauth_map.facebook_access_token = "fb access token"
        oauth_map.put()
        
        profile = {'name': "Facebook user [%s]" % unicode(fb_email),
                   'email': unicode(fb_email),
                   'id': unicode(fb_id)}

        self.mock_method(
            'facebook_util._get_profile_from_fb_token',
            lambda access_token: profile)
        
        self.fake_request(oauth_map)

    def fake_password_auth(self, oauth_map, user_with_pw):
        oauth_map.khan_auth_token = \
                auth.tokens.AuthToken.for_user(user_with_pw).value
        oauth_map.put()

        self.fake_request(oauth_map)

    def test_new_google_login(self):
        oauth_map = self.make_oauth_map()
        self.assertEquals(0, _user_counts())
        self.fake_google_auth(oauth_map, 123, "google_user@gmail.com")
        self.assertEquals(1, _user_counts())
        self.assertTrue(oauth_map.uses_google())
        self.assertFalse(oauth_map.uses_facebook())
        self.assertFalse(oauth_map.uses_password())
        self.assertEquals("google_user@gmail.com",
                          oauth_map.get_user_data().email)

    def test_new_fb_login(self):
        oauth_map = self.make_oauth_map()
        self.assertEquals(0, _user_counts())
        self.fake_facebook_auth(oauth_map, 456, "fb_user@gmail.com")
        self.assertEquals(1, _user_counts())
        self.assertFalse(oauth_map.uses_google())
        self.assertTrue(oauth_map.uses_facebook())
        self.assertFalse(oauth_map.uses_password())

        self.assertEquals(facebook_util.FACEBOOK_ID_PREFIX + "456",
                          oauth_map.get_user_id())
        # TODO(benkomalo): this assert fails since FB users who create their
        # account via OAuth don't get their e-mails updated properly until
        # they log into the website at least once (and it /postlogin).
        # (See the TODO in OAuthMap._get_authenticated_user_info regarding
        # having to consolidate with /postlogin logic.)
        #self.assertEquals("fb_user@gmail.com",
        #                  oauth_map.get_user_data().email)

    def test_existing_google_login(self):
        existing = self.make_google_user(123, "google_user@gmail.com")
        self.assertEquals(1, _user_counts())

        oauth_map = self.make_oauth_map()
        self.fake_google_auth(oauth_map, 123, "google_user@gmail.com")
        self.assertEquals(1, _user_counts())
        self.assertEquals(existing.user_id, oauth_map.get_user_id())

    def test_existing_fb_login(self):
        existing = self.make_fb_user(456, "fb_user@gmail.com")
        self.assertEquals(1, _user_counts())

        oauth_map = self.make_oauth_map()
        self.fake_facebook_auth(oauth_map, 456, "fb_user@gmail.com")
        self.assertEquals(1, _user_counts())
        self.assertEquals(existing.user_id, oauth_map.get_user_id())

    def test_fb_login_for_existing_gmail_user_with_matching_email(self):
        email = "advanced_user@gmail.com"
        existing = self.make_google_user(123, email)
        self.assertEquals(1, _user_counts())

        oauth_map = self.make_oauth_map()
        self.fake_facebook_auth(oauth_map, 123, email)
        self.assertEquals(1, _user_counts())
        self.assertEquals(existing.user_id, oauth_map.get_user_id())
        self.assertEquals(existing.email, oauth_map.get_user_data().email)

    def test_existing_ka_login(self):
        existing = self.make_user("kauser",
                                  "kauser@gmail.com",
                                  "kauser@gmail.com")
        existing.set_password("user password")
        self.assertEquals(1, _user_counts())

        oauth_map = self.make_oauth_map()
        self.fake_password_auth(oauth_map, existing)

        self.assertEquals(1, _user_counts())
        self.assertEquals(existing.user_id, oauth_map.get_user_id())
