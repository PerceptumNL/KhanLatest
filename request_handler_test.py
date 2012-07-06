from __future__ import with_statement
import mock

from google.appengine.ext import db
import webapp2

import request_handler
from testutil import gae_model
import user_models


class DummyHandler(request_handler.RequestHandler):
    pass


# TODO(benkomalo): write tests to check for ACL-checking of
#     request_visible_student_user_data
class RequestHandlerTest(gae_model.GAEModelTestCase):
    def setUp(self):
        super(RequestHandlerTest, self).setUp()
        self.current_user_mock = None
        self.handler = DummyHandler()

    def tearDown(self):
        self.unmock_current_user()
        super(RequestHandlerTest, self).tearDown()

    def unmock_current_user(self):
        if self.current_user_mock:
            self.current_user_mock.stop()
        self.current_user_mock = None

    def fake_request(self, params={}, current_user=None):
        if current_user:
            self.unmock_current_user()
            self.current_user_mock = mock.patch(
                "user_models.UserData.current",
                staticmethod(lambda: current_user))
            self.current_user_mock.start()
        self.handler.request = webapp2.Request.blank("/", POST=params)

    def make_user(self, user_id, email=None, username=None):
        email = email or user_id
        u = user_models.UserData.insert_for(user_id, email, username=username)
        u.user_email = email
        u.put()
        db.get(u.key())  # Flush db transaction.
        return u

    def test_getting_user_data_when_none_specified(self):
        actor = self.make_user("actor")
        self.fake_request(current_user=actor)

        # Note this shouldn't fallback to the current user
        self.assertTrue(self.handler.request_student_user_data() is None)

        # But this one does
        self.assertEquals(
            actor.key(),
            self.handler.request_visible_student_user_data().key())

    def test_getting_user_data_when_explicitly_specified(self):
        actor = self.make_user("actor")
        other = self.make_user("other", username="otherusername")
        self.fake_request(params={"userId": "other"}, current_user=actor)
        self.assertEquals(
            other.key(),
            self.handler.request_student_user_data().key())

        self.fake_request(params={"email": "other"}, current_user=actor)
        self.assertEquals(
            other.key(),
            self.handler.request_student_user_data().key())

        # Legacy naming should work, too, though it warns
        with mock.patch("logging.warning") as warnmock:
            self.fake_request(params={"student_email": "other"},
                              current_user=actor)
            self.assertEquals(
                other.key(),
                self.handler.request_student_user_data().key())
            self.assertEquals(1, warnmock.call_count)

        self.fake_request(params={"username": "otherusername"},
                          current_user=actor)
        self.assertEquals(
            other.key(),
            self.handler.request_student_user_data().key())

    def test_encodes_redirect_to_iri(self):
        handler = request_handler.RequestHandler(None, webapp2.Response())
        handler.redirect(u"http://encode.me/\u2021")

        location_header_value = handler.response.headers['Location']
        self.assertIsInstance(location_header_value, str)
        self.assertEqual("http://encode.me/%E2%80%A1", location_header_value)
