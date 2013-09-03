from __future__ import with_statement
import datetime
import mock

from google.appengine.ext import db
from testutil.make_test_db import *

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
from tincan import TinCan
from exercise_models import StackLog, Exercise, UserExercise

class TinCanTest(gae_model.GAEModelTestCase):
    def setUp(self):
        super(TinCanTest, self).setUp(db_consistency_probability=1)
        print >>sys.stderr, 'Making users'
        self.users = Users()

        print >>sys.stderr, 'Making videos'
        videos = Videos()
        print >>sys.stderr, 'Making exercises'
        exercises = Exercises()
        print >>sys.stderr, 'Making exercises-and-videos'
        self.exercises_and_videos = ExercisesAndVideos(exercises, videos)
        #print >>sys.stderr, 'Watching and doing videos and exercises'
        #users.add_progress(exercises_and_videos)

    def make_user(self, email):
        return UserData.insert_for(email, email)

    def make_user_json(self, user, is_coaching):
        return {
            'email': user.key_email,
            'isCoachingLoggedInUser': is_coaching,
        }

    #def test_add_a_coach(self):
    #    import logging
    #    import json
    #    u=UserData.all().get()
    #    logging.error(u)
    #    s=UserExercise.all().fetch(100)
    #    logging.error(s)
    #    for _s in s:
    #        print _s.progress
        #tc=TinCan.create_assessment(u, s, "launched") 
        #logging.error(json.dumps(tc.statement,sort_keys=True,
        #                            indent=4, separators=(',', ': ')))
    
        #stack_log_source = exercise_models.StackLog(
        #        key_name=exercise_models.StackLog.key_for(user_data.user_id, stack_uid),
        #        user_id=user_data.user_id,
        #        time_last_done=datetime.datetime.now(),
        #        review_mode=review_mode,
        #        topic_mode=topic_mode,
        #        exercise_id=user_exercise.exercise,
        #        topic_id=topic_id,
        #        cards_list=[],
        #        extra_data={},
        #)
    def test_assessments(self):
        TinCan.testMode = True
        user_exercise1 = self.users.user1.get_or_insert_exercise(
            self.exercises_and_videos.exponents.exercise)
        for i in range(1,10):
            exercise_util.attempt_problem(self.users.user1, user_exercise1,
                                          i,   # problem_number
                                          1,   # attempt_number
                                          "one",  # attempt_content -- wrong!!
                                          "sha1_unused?",         # sha1
                                          "random_seed",     # random seed
                                          True,  # gotten to the right answer?
                                          0,      # number of hints tried
                                          15,     # time taken (in seconds?)
                                          False,  # being done in review mode?
                                          False,  # being done in topic/power mode?
                                          "obsolete",   # problem_type
                                          "127.0.0.1",  # ip address
                                          {},
                                          "TEST",
                                          "TEST",
                                          1,
                                          7,
                                          async_problem_log_put=False,
                                          async_stack_log_put=False)
        # He's asking for a hint!

