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
from testutil.make_test_db import Users, Exercises
import setting_model

class ExerciseRequestVideoTest(gae_model.GAEModelTestCase):

    def setUp(self):
        super(ExerciseRequestVideoTest, self).setUp(db_consistency_probability=1)
        Users()
        Exercises()
    def test_request_video(self):
        exs = exercise_models.Exercise.all().fetch(1000)
        user = UserData.current()
        self.assertFalse(exs[0].video_requested)
        exs[0].request_video()
        self.assertTrue(exs[0].video_requested)
        self.assertEqual(exs[0].video_requests_count, 1)
        #test v1.py
