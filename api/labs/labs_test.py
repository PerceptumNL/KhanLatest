import contextlib
import urllib
import urllib2

from google.appengine.ext.remote_api import remote_api_stub

import gandalf.bridge
import gandalf.models
import gandalf.filters
import scratchpads.models as scratchpad_models
from testutil import handler_test_utils
from testutil import oauth_test_client
from testutil import testsize
import user_models

try:
    import json
except ImportError:
    import simplejson as json

try:
    import unittest2 as unittest     # python 2.5
except ImportError:
    import unittest                  # python 2.6+


@testsize.large()
def setUpModule():
    handler_test_utils.start_dev_appserver(db='testutil/test_db.sqlite')
    remote_api_stub.ConfigureRemoteApi(
        None,
        '/_ah/remote_api',
        auth_func=(lambda: ('test', 'test')),   # username/password
        servername=handler_test_utils.appserver_url[len('http://'):])
    oauth_test_client.stub_for_oauth()


def tearDownModule():
    # Let's emit the dev_appserver's logs in case those are helpful.
    # TODO(csilvers): only emit if there are >0 failures?
    print
    print '---------------- START DEV_APPSERVER LOGS ---------------------'
    print open(handler_test_utils.dev_appserver_logfile_name()).read()
    print '----------------- END DEV_APPSERVER LOGS ----------------------'

    oauth_test_client.unstub_for_oauth()
    oauth_test_client.clear_oauth_tokens_cache()
    handler_test_utils.stop_dev_appserver()


class AnonRequestFetcher(object):
    def fetch(self, path, method, data=None, headers=None):
        if headers is None:
            headers = {}

        url = handler_test_utils.appserver_url + path
        request = urllib2.Request(url, data, headers)

        # Force override the request method to support 'PUT' and 'DELETE'
        #   See http://stackoverflow.com/questions/4511598)
        request.get_method = lambda: method

        return urllib2.urlopen(request).read().strip()


class ScratchpadApiTest(unittest.TestCase):
    def setUp(self):
        self.oauth_fetcher = oauth_test_client.OAuthRequestFetcher()
        self.oauth_fetcher.set_user()

        self.anon_fetcher = AnonRequestFetcher()

        self.revision_data = {
            'code': 'var pi = 3.0;',
            'image_url': 'data:image/png;base64,' + 'i' * 8000,
        }

        self.scratchpad_data = {
            'title': 'Cool Fractal',
            'revision': self.revision_data,
        }

        # WARNING: The gandalf related stuff cannot be sanely mocked at the
        # moment. This is because the API server is actually running in
        # a different process, so mocking out gandalf.bridge.gandalf won't
        # work. This problem is further aggravated by the Gandalf cache, which
        # makes it difficult to control gandalf's behaviour even by manually
        # inserting/deleting GandalfFilter and GandalfBridge records.
        #
        # See scratchpads/handlers_test.py for the desired mocking mechanism.
        #
        # TODO(jlfwong): Fix this either by
        #   1. Figuring out some sane way to bypass the gandalf cache
        #   2. Stop spawning an extra process and just hit the API methods
        #      directly using gae_model.GAEmodelTestCase. This will mean
        #      supporting OAuth requests not made via real url fetches. This
        #      would allow real mocking support.

        # For now, we'll just set up the "scratchpads" gandalf bridge to permit
        # all users
        self._gandalf_bridge = (gandalf.models.GandalfBridge
            .get_or_insert('scratchpads'))
        self._gandalf_bridge.put()

        self._gandalf_filter = gandalf.models.GandalfFilter(
            bridge=self._gandalf_bridge,
            filter_type='all-users',
            whitelist=True,
            context=gandalf.filters.AllUsersBridgeFilter)
        self._gandalf_filter.put()

    def tearDown(self):
        # Delete the gandalf records created.
        self._gandalf_bridge.delete()
        self._gandalf_filter.delete()

    # -- HTTP Helper Methods --

    def assertRaisesHTTPError(self, error_code, method=None):
        """Assert that the HTTPError with the specified error_code is raised.

        Can either be passed a method to execute or used as a context manager,
        just like regular assertRaises.
        """

        @contextlib.contextmanager
        def _assertRaisesHTTPError():
            try:
                yield
                self.fail("Expecting HTTPError, but no exception was raised")
            except urllib2.HTTPError, why:
                self.assertEqual(error_code, why.code)

        if method is None:
            return _assertRaisesHTTPError()
        else:
            with _assertRaisesHTTPError():
                method()

    def fetch(self, path, method, use_oauth=True, headers=None, data=None):
        """Fetches a given path (e.g. /api/labs/scratchpads/1)

        Arguments:
            path:
                The path on the server to retrieve.

            method:
                The HTTP method to use as a string (GET/POST/PUT/DELETE).

            use_oauth:
                Determines whether the request will be oauth signed. Pass
                use_oauth=False if you want the request to be anonymous.

            headers:
                Dict of extra headers for the request.
                Default headers for the request will not be overwritten.

            data:
                Payload for the request. If this argument is a string, it will
                be used verbatim as the payload. Otherwise, if it's not None,
                it will be json encoded and Content-type: application/json will
                be added to the headers.

        Returns:
            The response body as a string from fetching the given path
        """

        if headers is None:
            headers = {}

        if data is not None and not isinstance(data, basestring):
            data = json.dumps(data)
            headers['Content-type'] = 'application/json'

        fetcher = self.oauth_fetcher if use_oauth else self.anon_fetcher
        return fetcher.fetch(path, method, headers=headers, data=data)

    def get(self, *args, **kwargs):
        kwargs['method'] = 'GET'
        return self.fetch(*args, **kwargs)

    def post(self, *args, **kwargs):
        kwargs['method'] = 'POST'
        return self.fetch(*args, **kwargs)

    def put(self, *args, **kwargs):
        kwargs['method'] = 'PUT'
        return self.fetch(*args, **kwargs)

    def delete(self, *args, **kwargs):
        kwargs['method'] = 'DELETE'
        return self.fetch(*args, **kwargs)

    # -- Scratchpad specific helper methods --

    def _api_create_scratchpad(self, data, use_oauth=True):
        """Create a scratchpad via the API.

        Arguments:
            data:
                The data payload to be JSON encoded and POSTed to the API
                endpoint.

            use_oauth:
                Determines whether the request will be oauth signed. Pass
                use_oauth=False if you want the request to be anonymous.

        Returns:
            The response as a dict, JSON-decoded from the response body.
        """
        post_resp = self.post("/api/labs/scratchpads",
            data=data, use_oauth=use_oauth)
        return json.loads(post_resp)

    def _api_update_scratchpad(self, scratchpad_id, data, use_oauth=True):
        """Update a scratchpad via the API.

        Arguments:
            scratchpad_id:
                The id of the scratchpad to retrieve via the API.

            data:
                The data payload to be JSON encoded and PUT to the API
                endpoint.

            use_oauth:
                Determines whether the request will be oauth signed. Pass
                use_oauth=False if you want the request to be anonymous.
        """
        put_resp = self.put("/api/labs/scratchpads/%s" % scratchpad_id,
            data=data, use_oauth=use_oauth)
        return json.loads(put_resp)

    def _api_get_scratchpad(self, scratchpad_id, use_oauth=True):
        """Get a scratchpad via the API.

        Arguments:
            scratchpad_id:
                The id of the scratchpad to retrieve via the API.

            use_oauth:
                Determines whether the request will be oauth signed. Pass
                use_oauth=False if you want the request to be anonymous.

        Returns:
            The response as a dict, JSON-decoded from the response body.
        """
        get_resp = self.get("/api/labs/scratchpads/%s" % scratchpad_id,
            use_oauth=use_oauth)
        return json.loads(get_resp)

    def _api_get_user_scratchpads(self, user_data, use_oauth=True):
        """Get a list of scratchpads created by the specified user_data via
        the API.

        Arguments:
            user_data:
                The scratchpads retrieved were created by the user specified by
                user_data.

            use_oauth:
                Determines whether the request will be oauth signed. Pass
                use_oauth=False if you want the request to be anonymous.

        Returns:
            The response as a list, JSON-decoded from the response body.
        """
        get_resp = self.get('/api/labs/user/scratchpads?' +
            urllib.urlencode({'email': user_data.email}))
        return json.loads(get_resp)

    def _api_delete_scratchpad(self, scratchpad_id, use_oauth=True):
        """Delete a scratchpad via the API.

        Arguments:
            scratchpad_id:
                The id of the scratchpad to delete via the API.

            use_oauth:
                Determines whether the request will be oauth signed. Pass
                use_oauth=False if you want the request to be anonymous.

        Returns:
            None
        """
        self.delete("/api/labs/scratchpads/%s" % scratchpad_id,
            use_oauth=use_oauth)

    # -- Other Helper Methods --

    def _oauth_user_data(self):
        return user_models.UserData.get_from_username_or_email(
            self.oauth_fetcher.email)

    # -- Functional Tests --
    # These tests evaluate whether the user can do what they're supposed to be
    # allowed to do.

    def test_create_as_anonymous(self):
        # Anonymous users should be able to create scratchpads.
        scratchpad_pre_count = scratchpad_models.Scratchpad.all().count()

        scratchpad_json = self._api_create_scratchpad(self.scratchpad_data,
            use_oauth=False)

        self.assertEqual(scratchpad_models.Scratchpad.all().count(),
            scratchpad_pre_count + 1)

        scratchpad = scratchpad_models.Scratchpad.get_by_id(
            scratchpad_json['id'])

        self.assertIsNotNone(scratchpad)

        revision = scratchpad.revision
        self.assertIsNotNone(scratchpad.revision.created)
        self.assertEqual(scratchpad.title, self.scratchpad_data['title'])
        self.assertEqual(revision.code, self.revision_data['code'])
        self.assertEqual(revision.image_url, self.revision_data['image_url'])

    def test_create_as_logged_in(self):
        # Logged in users should be able to create scratchpads and have them
        # associated with their user id.
        scratchpad_pre_count = scratchpad_models.Scratchpad.all().count()

        scratchpad_json = self._api_create_scratchpad(self.scratchpad_data)

        self.assertEqual(scratchpad_models.Scratchpad.all().count(),
            scratchpad_pre_count + 1)

        scratchpad = scratchpad_models.Scratchpad.get_by_id(
            scratchpad_json['id'])

        self.assertIsNotNone(scratchpad)
        self.assertEqual(scratchpad.user_id, self._oauth_user_data().user_id)

    def test_update_as_logged_in(self):
        # Logged in users should be able to update scratchpads they created.
        data = {}
        data.update(self.scratchpad_data)
        data.update({
            'user_id': self._oauth_user_data().user_id
        })
        scratchpad = scratchpad_models.Scratchpad.create(**data)

        update_data = {}
        update_data.update(self.scratchpad_data)
        update_data.update({
            # Including the id is superfluous, but backbone does this, so we
            # should do that here too
            'id': scratchpad.id,
            'title': 'New Title',
            'revision': {
                'code': 'new code',
                'image_url': 'http://placekitten.com/g/200/200',
            }
        })

        scratchpad_json = self._api_update_scratchpad(scratchpad.id,
            update_data)

        self.assertEqual(scratchpad_json['id'], scratchpad.id)

        updated_scratchpad = scratchpad_models.Scratchpad.get_by_id(
            scratchpad_json['id'])
        updated_revision = updated_scratchpad.revision

        self.assertEqual(updated_scratchpad.title, update_data['title'])
        self.assertEqual(updated_revision.code,
            update_data['revision']['code'])
        self.assertEqual(updated_revision.image_url,
            update_data['revision']['image_url'])

    def test_fork_as_logged_in(self):
        # Logged in users should be able to fork a pre-existing scratchpad.
        origin_scratchpad = scratchpad_models.Scratchpad.create(
            title='Foo',
            revision=dict(
                code='var foo;',
                image_url='http://placekitten.com/g/200/200'
            )
        )

        data = {}
        data.update(self.scratchpad_data)
        data.update({
            'origin_revision_id': origin_scratchpad.revision.id,
            'origin_scratchpad_id': origin_scratchpad.id
        })

        scratchpad_json = self._api_create_scratchpad(data)

        scratchpad = scratchpad_models.Scratchpad.get_by_id(
            scratchpad_json['id'])

        self.assertIsNotNone(scratchpad)
        self.assertEqual(scratchpad.origin_revision_id,
            data['origin_revision_id'])
        self.assertEqual(scratchpad.origin_scratchpad_id,
            data['origin_scratchpad_id'])

    def test_delete_as_logged_in(self):
        # Logged in users should be able to delete their own scratchpads.
        data = {}
        data.update(self.scratchpad_data)
        data.update({
            'user_id': self._oauth_user_data().user_id
        })
        scratchpad = scratchpad_models.Scratchpad.create(**data)

        self._api_delete_scratchpad(scratchpad.id)

        # When scratchpads are deleted, they aren't actually removed from the
        # database - they just have a flag set on them indicating that they're
        # deleted
        deleted_scratchpad = scratchpad_models.Scratchpad.get_by_id(
            scratchpad.id)

        self.assertIsNotNone(deleted_scratchpad)
        self.assertTrue(deleted_scratchpad.deleted)

    def test_get_scratchpad_list_for_current_user_as_logged_in(self):
        # Users should be able to see all the explorations they've made.
        user = self._oauth_user_data()

        data = {}
        data.update(self.scratchpad_data)
        data["user_id"] = user.user_id

        scratchpad_models.Scratchpad.create(**data)

        scratchpads_json = self._api_get_user_scratchpads(user)

        scratchpad_count_for_user = (scratchpad_models.Scratchpad
            .filtered_all()
            .filter('user_id = ', user.user_id)
            .count())

        self.assertEqual(len(scratchpads_json), scratchpad_count_for_user)
        self.assertEqual(scratchpads_json[0]['title'], data['title'])
        self.assertEqual(scratchpads_json[0]['user_id'], user.user_id)

    def test_get_scratchpad_list_deleted_scratchpads_filtered_out(self):
        # Deleted scratchpads should not show up in lists of scratchpads.
        user = self._oauth_user_data()

        data = {}
        data.update(self.scratchpad_data)
        data.update({
            "user_id": user.user_id,
            "title": "Deleted Scratchpad"
        })

        scratchpad = scratchpad_models.Scratchpad.create(**data)
        scratchpad.deleted = True
        scratchpad.put()

        # Force consistency by querying the model immediately after marking it
        # as deleted. Without this, we get a stale list of entities in the API
        # call. The stale list will contain the scratchpad with the title
        # "Deleted Scratchpad", but it won't be marked as deleted yet.
        scratchpad_models.Scratchpad.get_by_id(scratchpad.id)

        scratchpads_json = self._api_get_user_scratchpads(user)

        self.assertFalse(any(
            [s["title"] == data["title"] for s in scratchpads_json]
        ))

    def test_create_as_developer(self):
        # Developers should be able create scratchpads with developer-only
        # fields set.
        self.oauth_fetcher.set_user(developer=True)
        scratchpad_pre_count = scratchpad_models.Scratchpad.all().count()

        data = {}
        data.update(self.scratchpad_data)
        data.update({
            'category': 'tutorial',
            'difficulty': 0,
            'youtube_id': 'LWNLE4sklfI',
        })

        scratchpad_json = self._api_create_scratchpad(data)

        self.assertEqual(scratchpad_models.Scratchpad.all().count(),
            scratchpad_pre_count + 1)

        scratchpad = scratchpad_models.Scratchpad.get_by_id(
            scratchpad_json['id'])

        self.assertIsNotNone(scratchpad)
        self.assertEqual(scratchpad.category, data['category'])
        self.assertEqual(scratchpad.difficulty, data['difficulty'])
        self.assertEqual(scratchpad.youtube_id, data['youtube_id'])

    def test_update_as_developer(self):
        # Developers should be able to update scratchpads and change
        # developer-only fields.
        self.oauth_fetcher.set_user(developer=True)

        data = {}
        data.update(self.scratchpad_data)
        data.update({
            'user_id': self._oauth_user_data().user_id
        })
        scratchpad = scratchpad_models.Scratchpad.create(**data)

        update_data = {}
        update_data.update(self.scratchpad_data)
        update_data.update({
            'category': 'official',
            'difficulty': 10,
            'youtube_id': 'oHg5SJYRHA0',
        })

        scratchpad_json = self._api_update_scratchpad(scratchpad.id,
            update_data)

        updated_scratchpad = scratchpad_models.Scratchpad.get_by_id(
            scratchpad_json['id'])

        self.assertEqual(updated_scratchpad.category, update_data['category'])
        self.assertEqual(updated_scratchpad.difficulty,
            update_data['difficulty'])
        self.assertEqual(updated_scratchpad.youtube_id,
            update_data['youtube_id'])

    def test_update_tutorial_owned_by_other_as_developer(self):
        # Developers should be able to update tutorial/official scratchpads
        # owned by other developers.
        self.oauth_fetcher.set_user(developer=True)

        other_developer = user_models.UserData.insert_for(
            'other_developer', 'other_developer@example.com',
            username='otherdeveloperprofilename')
        other_developer.set_password(other_developer.user_id)
        other_developer.update_nickname('Other Developer')
        other_developer.developer = True
        other_developer.put()

        # Create a tutorial owned by a different developer
        data = {}
        data.update(self.scratchpad_data)
        data.update({
            'user_id': other_developer.user_id,
            'category': 'tutorial'
        })

        scratchpad = scratchpad_models.Scratchpad.create(**data)

        update_data = {}
        update_data.update(self.scratchpad_data)
        update_data['difficulty'] = 30

        scratchpad_json = self._api_update_scratchpad(scratchpad.id,
            update_data)

        updated_scratchpad = scratchpad_models.Scratchpad.get_by_id(
            scratchpad_json['id'])

        self.assertNotEqual(updated_scratchpad.difficulty,
            scratchpad.difficulty)
        self.assertEqual(updated_scratchpad.difficulty,
            update_data['difficulty'])

    def test_delete_scratchpad_created_by_other_as_developer(self):
        # Developers should be able to delete scratchpads created by anyone.
        self.oauth_fetcher.set_user(developer=True)

        user = self._oauth_user_data()

        scratchpad = scratchpad_models.Scratchpad.create(
            **self.scratchpad_data)

        self.assertNotEqual(scratchpad.user_id, user.user_id)

        self._api_delete_scratchpad(scratchpad.id)

        deleted_scratchpad = scratchpad_models.Scratchpad.get_by_id(
            scratchpad.id)

        self.assertIsNotNone(deleted_scratchpad)
        self.assertTrue(deleted_scratchpad.deleted)

    # -- Access Tests --
    # These tests evaluate whether users are correctly restricted from doing
    # what they're not allowed to do.

    def test_restrict_update_as_anonymous(self):
        # Anonymous users should not be able to update anonymously created
        # scratchpads.
        scratchpad = scratchpad_models.Scratchpad.create(
            **self.scratchpad_data)

        # Ensure that the scratchpad does indeed have no owner
        self.assertIsNone(scratchpad.user_id)

        with self.assertRaisesHTTPError(401):  # Unauthorized
            self._api_update_scratchpad(scratchpad.id, self.scratchpad_data,
                use_oauth=False)

    def test_restrict_create_developer_only_fields_as_logged_in(self):
        # Regular logged in users should not be able to set developer-only
        # fields when creating a scratchpad.
        with self.assertRaisesHTTPError(403):
            data = {}
            data.update(self.scratchpad_data)
            data['category'] = 'tutorial'
            self._api_create_scratchpad(data)

        with self.assertRaisesHTTPError(403):
            data = {}
            data.update(self.scratchpad_data)
            data['difficulty'] = 10
            self._api_create_scratchpad(data)

        with self.assertRaisesHTTPError(403):
            data = {}
            data.update(self.scratchpad_data)
            data['youtube_id'] = 'LWNLE4sklfI'
            self._api_create_scratchpad(data)

    def test_restrict_update_developer_only_fields_as_logged_in(self):
        # Regular logged in users should not be able to change developer-only
        # fields in an update to a scratchpad they created.
        data = {}
        data.update(self.scratchpad_data)
        data.update({
            'user_id': self._oauth_user_data().user_id
        })
        scratchpad = scratchpad_models.Scratchpad.create(**data)

        with self.assertRaisesHTTPError(403):
            data = {}
            data.update(self.scratchpad_data)
            data['category'] = 'tutorial'
            self._api_update_scratchpad(scratchpad.id, data)

        with self.assertRaisesHTTPError(403):
            data = {}
            data.update(self.scratchpad_data)
            data['difficulty'] = 10
            self._api_update_scratchpad(scratchpad.id, data)

        with self.assertRaisesHTTPError(403):
            data = {}
            data.update(self.scratchpad_data)
            data['youtube_id'] = 'LWNLE4sklfI'
            self._api_update_scratchpad(scratchpad.id, data)

    def test_restrict_update_scratchpad_created_by_other_as_logged_in(self):
        # Regular users should not be able to update other users scratchpads.
        other_user = user_models.UserData.insert_for(
            'other_user', 'other_user@example.com',
            username='otheruserprofilename')
        other_user.set_password(other_user.user_id)
        other_user.update_nickname('Other user')
        other_user.put()

        data = {}
        data.update(self.scratchpad_data)
        data.update({
            'user_id': other_user.user_id
        })
        scratchpad = scratchpad_models.Scratchpad.create(**data)

        with self.assertRaisesHTTPError(403):
            self._api_update_scratchpad(scratchpad.id, self.scratchpad_data)

    def test_restrict_delete_scratchpad_created_by_other_as_logged_in(self):
        other_user = user_models.UserData.insert_for(
            'other_user', 'other_user@example.com',
            username='otheruserprofilename')
        other_user.set_password(other_user.user_id)
        other_user.update_nickname('Other user')
        other_user.put()

        data = {}
        data.update(self.scratchpad_data)
        data.update({
            'user_id': other_user.user_id
        })
        scratchpad = scratchpad_models.Scratchpad.create(**data)

        with self.assertRaisesHTTPError(403):
            self._api_delete_scratchpad(scratchpad.id)

    # -- Error Tests --
    # These tests evaluate whether the system errors out in a sane way when
    # something goes wrong or there's bad input

    def test_update_scratchpad_not_found(self):
        with self.assertRaisesHTTPError(404):
            self._api_update_scratchpad(9999, self.scratchpad_data)

    def test_update_scratchpad_deleted(self):
        # A deleted scratchpad should act exactly as if it's gone from the API
        # standpoint

        data = {}
        data.update(self.scratchpad_data)
        scratchpad = scratchpad_models.Scratchpad.create(**data)
        scratchpad.deleted = True
        scratchpad.put()

        with self.assertRaisesHTTPError(404):
            self._api_update_scratchpad(scratchpad.id, self.scratchpad_data)

    def test_delete_scratchpad_deleted(self):
        # A deleted scratchpad should act exactly as if it's gone from the API
        # standpoint

        data = {}
        data.update(self.scratchpad_data)
        scratchpad = scratchpad_models.Scratchpad.create(**data)
        scratchpad.deleted = True
        scratchpad.put()

        with self.assertRaisesHTTPError(404):
            self._api_delete_scratchpad(scratchpad.id)
