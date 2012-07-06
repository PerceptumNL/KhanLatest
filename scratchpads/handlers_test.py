import os
import webapp2

import main
import gandalf.bridge
from testutil import gae_model
import scratchpads.models as scratchpads


class ScratchpadHandlerTest(gae_model.GAEModelTestCase):
    def setUp(self):
        super(ScratchpadHandlerTest, self).setUp()

        if 'HTTP_HOST' in os.environ:
            self.orig_host = os.environ['HTTP_HOST']
        else:
            self.orig_host = None

        os.environ['HTTP_HOST'] = 'www.khanacademy.org'

        if 'QUERY_STRING' in os.environ:
            self.orig_qs = os.environ['QUERY_STRING']
        else:
            self.orig_qs = None

        os.environ['QUERY_STRING'] = ""

        # Mock out gandalf
        self._real_gandalf = gandalf.bridge.gandalf

        # By default, make the current user pass the gandalf filters
        self.permitted_by_gandalf = True

        def mock_gandalf(bridge_name):
            if bridge_name == 'scratchpads':
                return self.permitted_by_gandalf
            else:
                return self._real_gandalf(bridge_name)

        gandalf.bridge.gandalf = mock_gandalf

        self.revision_data = {
            'code': 'var pi = 3.0;',
            'image_url': 'data:image/png;base64,' + 'i' * 8000
        }

        self.scratchpad_data = {
            'title': 'Cool Fractal',
            'revision': self.revision_data
        }

    def tearDown(self):
        if self.orig_host:
            os.environ['HTTP_HOST'] = self.orig_host
        else:
            del os.environ['HTTP_HOST']

        if self.orig_qs:
            os.environ['QUERY_STRING'] = self.orig_host
        else:
            del os.environ['QUERY_STRING']

        gandalf.bridge.gandalf = self._real_gandalf

        super(ScratchpadHandlerTest, self).tearDown()

    def get(self, path):
        request = webapp2.Request.blank(path)
        return request.get_response(main.application)

    def test_get_scratchpad_new(self):
        resp = self.get('/explore/new')
        self.assertEqual(resp.status_int, 200)

    def test_get_scratchpad_new_gandalf_block(self):
        self.permitted_by_gandalf = False
        resp = self.get('/explore/new')
        self.assertEqual(resp.status_int, 404)

    def test_get_scratchpad_show(self):
        scratchpad = scratchpads.Scratchpad.create(**self.scratchpad_data)

        resp = self.get('/explore/%s/%s' % (
            scratchpad.slug, scratchpad.id
        ))
        self.assertEqual(resp.status_int, 200)

    def test_get_scratchpad_image(self):
        scratchpad = scratchpads.Scratchpad.create(**self.scratchpad_data)

        resp = self.get('/explore/%s/%s/image.png' % (
            scratchpad.slug, scratchpad.id
        ))
        self.assertEqual(resp.status_int, 200)

    def test_get_scratchpad_show_gandalf_block(self):
        # Even if the user is gandalf restricted, they should still be able to
        # access the show page
        self.permitted_by_gandalf = False

        scratchpad = scratchpads.Scratchpad.create(**self.scratchpad_data)

        resp = self.get('/explore/%s/%s' % (
            scratchpad.slug, scratchpad.id
        ))
        self.assertEqual(resp.status_int, 200)

    def test_get_deleted_scratchpad_show_404(self):
        # Scratchpads marked as deleted should act exactly as if they really
        # were deleted

        scratchpad = scratchpads.Scratchpad.create(**self.scratchpad_data)
        scratchpad.deleted = True
        scratchpad.put()

        resp = self.get('/explore/slug/%s' % scratchpad.id)
        self.assertEqual(resp.status_int, 404)

    def test_get_scratchpad_show_404(self):
        resp = self.get('/explore/slug/9999')
        self.assertEqual(resp.status_int, 404)

    def test_get_scratchpad_list_explorations(self):
        resp = self.get('/explore')
        self.assertEqual(resp.status_int, 200)

    def test_get_scratchpad_list_explorations_gandalf_block(self):
        self.permitted_by_gandalf = False
        resp = self.get('/explore')
        self.assertEqual(resp.status_int, 404)

    def test_get_scratchpad_list_tutorials(self):
        resp = self.get('/explore/tutorials')
        self.assertEqual(resp.status_int, 200)

    def test_get_scratchpad_list_tutorials_gandalf_block(self):
        self.permitted_by_gandalf = False
        resp = self.get('/explore/tutorials')
        self.assertEqual(resp.status_int, 404)
