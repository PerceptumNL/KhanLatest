import mock

from google.appengine.api import users
import webapp2

import main
import request_cache
from testutil import fake_user
from testutil import gae_model
import user_models


# shorthand notations
def _user_counts():
    return user_models.UserData.all().count()


def _cur_user():
    return user_models.UserData.current(create_if_none=False)


class PostLoginTest(gae_model.GAEModelTestCase):
    def setUp(self):
        super(PostLoginTest, self).setUp()
        self._patches = []

    def tearDown(self):
        for p in self._patches:
            p.stop()

        request_cache.flush()

        # Sanity check to ensure we tore down things properly
        self.assertTrue(_cur_user() is None)

        super(PostLoginTest, self).tearDown()

    def mock_method(self, method_path, mocked_impl):
        patcher = mock.patch(method_path, mocked_impl)
        self._patches.append(patcher)
        patcher.start()

    def initiate_fake_request(self):
        request = webapp2.Request.blank("/postlogin")
        request.get_response(main.application)

    def fake_google_login(self, gid, google_email):
        """Pretend to login with Google and executes /postlogin handler."""
        stub_user = users.User(google_email, _user_id=gid)
        self.mock_method('google.appengine.api.users.get_current_user',
                          lambda: stub_user)
        self.initiate_fake_request()

    def fake_fb_login(self, fb_id, fb_email):
        """Pretend to login with Facebook and executes /postlogin handler."""
        profile = {'name': "Facebook user [%s]" % unicode(fb_email),
                   'email': unicode(fb_email),
                   'id': unicode(fb_id)}

        self.mock_method(
            'facebook.get_user_from_cookie_patched',
            lambda cookies, app_id, app_secret: {'uid': fb_id,
                                                 'access_token': 'unused'})
        self.mock_method(
            'facebook_util.get_profile_from_cookies',
            lambda: profile)
        self.mock_method(
            'facebook_util._get_profile_from_fb_token',
            lambda access_token: profile)

        self.initiate_fake_request()

    def test_basic_google_login_for_new_user(self):
        self.assertEquals(0, _user_counts())
        self.fake_google_login(123, "joe@gmail.com")
        self.assertEquals(1, _user_counts())
        self.assertEquals("joe@gmail.com", _cur_user().email)

    def test_basic_fb_login_for_new_user(self):
        self.assertEquals(0, _user_counts())
        self.fake_fb_login(123, "fbuser@gmail.com")
        self.assertEquals(1, _user_counts())
        self.assertEquals("fbuser@gmail.com", _cur_user().email)

    def test_fb_login_for_existing_user(self):
        # An existing facebook user in our system - we don't know
        # their email yet, because historically we didn't ask.
        existing = fake_user.fb_user(123)
        self.assertFalse(existing.has_sendable_email())
        self.assertEquals(1, _user_counts())

        # Have them login, but this time FB gave us their e-mail.
        self.fake_fb_login(123, "fbuser@gmail.com")

        # At this point, that same user should have just gotten their email
        # updated since there were no conflicts with other accounts.
        self.assertEquals(1, _user_counts())
        self.assertEquals(existing.key(), _cur_user().key())
        self.assertEquals("fbuser@gmail.com",
                          _cur_user().email)
        self.assertTrue(_cur_user().has_sendable_email())

    def test_old_fb_user_with_clashing_email_doesnt_clobber_others(self):
        email = "user@gmail.com"

        # An existing google user with user@gmail.com
        user1 = fake_user.google_user(123, email)

        # An existing facebook user in our system - we don't know
        # their email yet, because historically we didn't ask.
        user2 = fake_user.fb_user(123)
        self.assertFalse(user2.has_sendable_email())

        # Now, pretend the FB user logs in and we now get their e-mail
        self.fake_fb_login(123, "user@gmail.com")

        current = _cur_user()

        self.assertEquals(
            2, _user_counts(),
            msg="New user shouldn't be created on FB email change")

        self.assertNotEquals(
            user1.key(), current.key(),
            msg="Shouldn't have logged in as the Google user")

        self.assertEquals(
            user2.key(), current.key(),
            msg="Should have logged in as the FB user")

        self.assertFalse(
            current.has_sendable_email(),
            msg="FB email should not have been updated since it "
                "conflicts with a different user's")

    def test_google_user_changing_emails_doesnt_clobber_others(self):
        # An existing Google user
        user1 = fake_user.google_user(123, "original@gmail.com")

        # An existing Facebook user - say they logged in after we started
        # collecting e-mails from FB users, so we have their email.
        user2 = fake_user.fb_user(123, "new@gmail.com")

        # Now, pretend the Google user logs in, but their e-mail has changed
        # to match the FB user's!
        self.fake_google_login(123, "new@gmail.com")

        # Unfortunately, we can't "merge" accounts, and it would suck to
        # clobber that other FB account and not make it accessible. So until
        # we can properly merge, we can't update the e-mail of that Google
        # user .
        current = _cur_user()
        self.assertEquals(2, _user_counts())
        self.assertEquals(
            user1.key(), current.key(),
            msg="Google user should still have access to old account")

        retrieved_by_email = \
            user_models.UserData.get_from_user_input_email("new@gmail.com")
        self.assertEquals(
            user2.key(), retrieved_by_email.key(),
            msg="The FB user should still own the new e-mail")
