#!/usr/bin/python

# Notes(sergio)
# Template to create tests, CSV write sample
# USAGE: python testutil/mytest_db.py <existingdb|newdb>

"""Create a test database that we can run dev_appserver against.

The test-db is meant to have datastore entries for everything that a
person can do in khan academy: there are exercises and videos, topics
and topic-trees, commoncore objects and promotion objects, and of
course users who have done things.

This database can be used directly, via dev_appserver
--datastore=test_db, and it can be used for testing, such as
api/v1_endtoend_test.py.  When you use the database, it's recommended
you make a copy of it first (via 'cp') and use that, so the original
database isn't affected by any changes you make.

This file can also be used as a library for tests that want to create
a db for testing.
"""


import datetime
import os
import shutil
import sys

from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext.remote_api import remote_api_stub
from third_party.mapreduce import control

import exercise_models
import exercise_video_model
from exercises import exercise_util
from knowledgemap import layout
from phantom_users import phantom_util
from testutil import handler_test_utils
import topic_models
import url_model
import user_models
import video_models


class Users(object):
    """Various UserData objects."""
    def __init__(self):
        """Create users of different types: moderator, phantom, etc."""
        self.user1 = user_models.UserData.insert_for(
            'user1', 'user1@example.com', username='user1profilename')
        self.user1.set_password(self.user1.user_id)
        self.user1.update_nickname('User One')

        self.user2 = user_models.UserData.insert_for(
            'user2', 'user2@example.com', username='user2profilename')
        self.user2.set_password(self.user2.user_id)
        self.user2.update_nickname('User Two')
        
        self.moderator = user_models.UserData.insert_for(
            'moderator', 'moderator@example.com',
            username='moderatorprofilename')
        self.moderator.set_password(self.moderator.user_id)
        self.moderator.update_nickname('Moderator')
        self.moderator.moderator = True
        self.moderator.put()

        self.developer = user_models.UserData.insert_for(
            'developer', 'developer@example.com',
            username='developerprofilename')
        self.developer.set_password(self.developer.user_id)
        self.developer.update_nickname('Developer')
        self.developer.developer = True
        self.developer.put()

        self.child = user_models.UserData.insert_for(
            'child', 'child@example.com',
            username='childprofilename',
            # Make this child very young. 13 years from now, this account will
            # no longer be a child, tests will fail, and this will need to
            # be updated.
            birthdate=datetime.date(2012, 5, 16))
        self.child.set_password(self.child.user_id)
        self.child.update_nickname('child')
        self.child.put()

        # It may also be useful to have a phantom user
        self.phantom = phantom_util._create_phantom_user_data()

        # TODO(csilvers): add a facebook-id user and a google-id user
        # TODO(csilvers): add an admin user (probably has to be a google id)

    def add_progress(self, exercises_and_videos):
        """Take a list of ExerciseAndVideo objects, set per-user progress."""
        # TODO(csilvers): stub out datetime.datetime.now() and .utcnow()
        # and set these at some specific time.

        # We can have many VideoLog entries for a single video.
        # Args are user, video, seconds watched, last second watched.
        # We stub out the time here so the database is deterministic.
        video_models.VideoLog.add_entry(
            self.user1, exercises_and_videos.exponents.video,
            exercises_and_videos.exponents.video.duration / 10,
            exercises_and_videos.exponents.video.duration / 10 + 1)
        video_models.VideoLog.add_entry(
            self.user1, exercises_and_videos.exponents.video,
            exercises_and_videos.exponents.video.duration / 2,
            exercises_and_videos.exponents.video.duration / 2 + 2)

        user_exercise1 = self.user1.get_or_insert_exercise(
            exercises_and_videos.exponents.exercise)
        exercise_util.attempt_problem(self.user1, user_exercise1,
                                      1,   # problem_number
                                      1,   # attempt_number
                                      "one",  # attempt_content -- wrong!!
                                      "sha1_unused?",         # sha1
                                      "random_seed",     # random seed
                                      False,  # gotten to the right answer?
                                      0,      # number of hints tried
                                      15,     # time taken (in seconds?)
                                      False,  # being done in review mode?
                                      False,  # being done in topic/power mode?
                                      "obsolete",   # problem_type
                                      "127.0.0.1",  # ip address
                                      async_problem_log_put=False)
        # He's asking for a hint!
        exercise_util.attempt_problem(self.user1, user_exercise1,
                                      1, 2, "hint", "sha1", "random_seed2",
                                      False, 1, 90, False, False,
                                      "obsolete", "127.0.0.1",
                                      async_problem_log_put=False)
        # Ten seconds later (or maybe 100?), he gets it right.
        exercise_util.attempt_problem(self.user1, user_exercise1,
                                      1, 2, "two", "sha1", "random_seed2",
                                      True, 1, 100, False, False,
                                      "obsolete", "127.0.0.1",
                                      async_problem_log_put=False)
        # Now he's got it! -- the second problem is a breeze.
        exercise_util.attempt_problem(self.user1, user_exercise1,
                                      2, 1, "right", "sha1", "random_seed3",
                                      True, 0, 10, False, False,
                                      "obsolete", "127.0.0.1",
                                      async_problem_log_put=False)

        user_exercise2 = self.user1.get_or_insert_exercise(
            exercises_and_videos.equations.exercise)
        for i in xrange(1, 25):    # 20 is enough to get a streak badge
            exercise_util.attempt_problem(self.user1, user_exercise2,
                                          i, 1, "firsttry", "sha1", "seed4",
                                          True, 0, (30 - i), False, False,
                                          "obsolete", "127.0.0.1",
                                          async_problem_log_put=False)

        # TODO(csilvers): test in power mode?  In practice mode?

    def run_mapreduces(self):
        """Runs the mapreduces that update user info based on progress."""
        # TODO(csilvers): get this to work -- use mapreduce_stub.py
        # This is taken from badges/util_badges.py
        unused_badges_id = control.start_map(
            name="UpdateUserBadges",
            handler_spec="badges.util_badges.badge_update_map",
            reader_spec=(
                "third_party.mapreduce.input_readers.DatastoreInputReader"),
            mapper_parameters={
                "input_reader": {"entity_kind": "user_models.UserData"},
                },
            mapreduce_parameters={"processing_rate": 250},
            shard_count=64,
            queue_name="user-badge-queue"
            )




class CommonCoreMap(object):
    """A CommonCoreMap object."""
    # TODO(csilvers): download data from:
    #    http://www.khanacademy.org/api/v1/commoncore
    pass


def SetPromoRecords(user):
    # TODO(csilvers):
    #   models.PromoRecord.record_promo(promo_name, user_data.user_id)
    pass


def stub():
    """Do all the function-stubbing we need to do."""
    # Most important: make sure we can talk to the dev-appserver.
    remote_api_stub.ConfigureRemoteApi(
        None,
        '/_ah/remote_api',
        auth_func=(lambda: ('test', 'test')),   # username/password
        servername=handler_test_utils.appserver_url[len('http://'):])
    os.environ['SERVER_SOFTWARE'] = 'Development (remote-api)/1.0'
    os.environ['HTTP_HOST'] = 'localhost'

    # We want to do 'deferred' tasks immediately.
    def fake_defer(fn, *fn_args, **defer_kwargs):
        """fn_args are for fn, defer_kwargs are for deferred.defer."""
        fn(*fn_args)
    deferred.defer = fake_defer


def main(db_filename):
    """Start a dev_appserver, create db entries on it, and exit."""
    try:
       with open(db_filename): 
           filename=db_filename
    except IOError:
           filename=None
    handler_test_utils.start_dev_appserver(db=filename)
    try:
        stub()

        from user_models import UserData
        import csv
        if filename == None:
            print >>sys.stderr, 'Making users'
            Users()
            print >>sys.stderr, 'Making users:Done'

        users = UserData.all().fetch(100)
        with open('users.csv', 'wb') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=' ',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            for u in users:
                print u.nickname
                spamwriter.writerow([u.nickname])

        print >>sys.stderr, 'Done!  Output in %s' % db_filename

        if filename == None:
            shutil.copy(os.path.join(handler_test_utils.tmpdir,
                                 'datastore', 'test.sqlite'),
                        db_filename)

    finally:
        # We keep around the tmpdir for debugging/etc
        handler_test_utils.stop_dev_appserver(delete_tmpdir=False)


if __name__ == '__main__':
    try:
        db_filename = sys.argv[1]
    except IndexError:
        sys.exit(__doc__)

    main(db_filename)
