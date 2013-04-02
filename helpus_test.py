from __future__ import with_statement

import mock
import datetime

from google.appengine.ext import db

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
from testutil.make_test_db import Users, Exercises, Topics, TopicVersions, Videos, MapLayout, stub
import setting_model
import helpus
from testutil import handler_test_utils
import os

class HelpUsTest(gae_model.GAEModelTestCase):

    def setUp(self):
        super(HelpUsTest, self).setUp(db_consistency_probability=1)
        users = Users()
        exercises = Exercises()
        topic_versions = TopicVersions(users)
        videos = Videos()
        unused_topics = Topics(users, topic_versions, exercises, videos)
        unused_map_layout = MapLayout(topic_versions)
        os.environ["QUERY_STRING"] = "test"

    def test_videoless_exercises(self):
        vl_exs = helpus.get_videoless_exercises()
        self.assertEqual(len(vl_exs), 2)
        self.assertEqual(vl_exs[0]['topics'][0], "Mathematics [late]")
