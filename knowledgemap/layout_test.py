
from __future__ import with_statement
import datetime
import mock
import zlib
import pickle_util
import topic_models
import topics
from api import jsonify

from google.appengine.ext import db, deferred


import custom_exceptions
import coaches
import exercise_models
import phantom_users.phantom_util
from testutil import gae_model
from testutil import mock_datetime
from coach_resources.coach_request_model import CoachRequest
from user_models import Capabilities, UserData, UniqueUsername, ParentChildPair
from user_models import _USER_KEY_PREFIX
from testutil import testsize
import setting_model
from knowledgemap.layout import MapLayout
import logging
from api import v1_utils
import json
from google.appengine.ext import testbed


class LayoutTest(gae_model.GAEModelTestCase):
    def setUp(self):
        super(LayoutTest, self).setUp(db_consistency_probability=1)
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_taskqueue_stub()
        self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        json_data=open('testutil/topictree.json')
        data = json.load(json_data)
        version = topic_models.TopicVersion.create_new_version()
        version.default = True
        version.put()
        version = topic_models.TopicVersion.create_edit_version()
        v1_utils.topictree_import_task("edit", "root",
                       False,
                       zlib.compress(pickle_util.dump(data)))


    def test_layout_from_editversion(self):
        version = topic_models.TopicVersion.get_edit_version()
        root = topic_models.Topic.get_root(version)
        layout = MapLayout.from_version()
        self.assertEqual(len(layout['topics']), 1)



