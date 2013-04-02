#!/usr/bin/python

"""Create a test database that we can run dev_appserver against.

USAGE: make_test_db.py <filename to write test db to>

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


class Videos(object):
    """Create Video objects."""
    def __init__(self):
        """All from the real datastore, excepting formats, which I made up."""
        self.courbet = video_models.Video(
            youtube_id='SvFtmPhbNRw',
            readable_id='courbet--the-artist-s-studio--1854-55',
            url=('http://www.youtube.com/watch?'
                 'v=SvFtmPhbNRw&feature=youtube_gdata_player'),
            title=("Courbet's The Artist's Studio, A real allegory summing up "
                   "seven years of my artistic and moral life"),
            description=(u"Gustave Courbet, The Artist's Studio; "
                         u"A real allegory summing up seven years of my "
                         u"artistic and moral life, oil on canvas, 1854-55 "
                         u"(Mus\xe9e d'Orsay, Paris)\n\n"
                         u"Speakers: Dr. Beth Harris and Dr. Steven Zucker"),
            keywords=(u"Courbet, The artist's studio, art history, "
                      u"smarthistory, realism, Mus\xe9e d'Orsay, Paris, "
                      u"history of art"),
            duration=325,
            views=405,
            downloadable_formats=["mp4", "m3u8"],
            # I made this up too: wanted to have a test of extra_properties
            extra_properties={'explore_url':
                              'http://en.wikipedia.org/wiki/Gustave_Courbet'},
            date_added=datetime.datetime(2012, 3, 28, 20, 38, 29, 93528))
        self.courbet.put()

        self.exponents = video_models.Video(
            youtube_id='kITJ6qH7jS0',
            readable_id='exponent-rules-part-1',
            url=('http://www.youtube.com/watch?'
                 'v=kITJ6qH7jS0&feature=youtube_gdata_player'),
            title='Exponent Rules Part 1',
            description='Introduction to exponent rules',
            keywords=('Math, exponents, exponent, rules, Khan, Academy, '
                      'CC_8_EE_1'),
            duration=583,
            views=175660,
            downloadable_formats=["mp4", "png", "m3u8"],
            date_added=datetime.datetime(2012, 3, 28, 20, 37, 54, 354012))
        self.exponents.put()

        self.equations = video_models.Video(
            youtube_id='9DxrF6Ttws4',
            readable_id='one-step-equations',
            url=('http://www.youtube.com/watch?'
                 'v=9DxrF6Ttws4&feature=youtube_gdata_player'),
            title='One Step Equations',
            description='One Step Equations',
            keywords=('One, Step, Equations, CC_39336_A-REI_3'),
            duration=750,
            views=43923,
            downloadable_formats=["m3u8"],
            date_added=datetime.datetime(2012, 3, 28, 20, 37, 54, 600386))
        self.equations.put()
        
        self.domain_and_range = video_models.Video(
            youtube_id='C6F33Ir-sY4',
            readable_id='domain-and-range-1',
            url=('http://www.youtube.com/watch?'
                 'v=C6F33Ir-sY4&feature=youtube_gdata_player'),
            title='Domain and Range 1',
            description='U03_L2_T2_we1 : Domain and Range 1',
            keywords=('U03_L2_T2_we1, Domain, and, Range, CC_39336_F-IF_1, '
                      'CC_39336_F-IF_5'),
            duration=216,
            views=44313,
            downloadable_formats=[],
            date_added=datetime.datetime(2012, 3, 28, 20, 37, 58, 985924))
        self.domain_and_range.put()

        self.absolute_value = video_models.Video(
            youtube_id='NvGTCzAfvr0',
            readable_id='absolute-value-1',
            url=('http://www.youtube.com/watch?'
                 'v=NvGTCzAfvr0&feature=youtube_gdata_player'),
            title='Absolute Value 1',
            description='U02_L2_T1_we2 : Absolute Value 1',
            keywords=('U02_L2_T1_we2, Absolute, Value, '
                      'CC_6_NS_7, CC_6_NS_7_c'),
            duration=202,
            views=99221,
            downloadable_formats=["png"],
            date_added=datetime.datetime(2012, 3, 28, 20, 37, 56, 690725))
        self.absolute_value.put()


class Exercises(object):
    """Create Exercise objects, including some corresponding to test Videos."""
    def __init__(self):
        # TODO(csilvers): add topic_string_keys
        self.exponents = exercise_models.Exercise(
            name=u'exponent_rules',
            short_display_name='Exp. Rules',
            # I added in one_step_equations as a pre-req here so we
            # could test having an actual db-entry exercise as a
            # prereq...
            prerequisites=[u'exponents_2', u'one_step_equations'],
            covers=[u'exponents_2'],
            v_position=6,
            h_position=20,
            seconds_per_fast_problem=4.0,
            live=True,
            summative=False,
            author=None,
            raw_html=None,
            last_modified=None,
            creation_date=datetime.datetime(2012, 3, 28, 20, 38, 49, 511388),
            description=None,
            tags=[])
        self.exponents.put()
            
        self.equations = exercise_models.Exercise(
            name=u'one_step_equations',
            short_display_name='1step eq',
            prerequisites=[u'one_step_equations_0.5'],
            covers=[u'one_step_equations_0.5'],
            v_position=7,
            h_position=27,
            seconds_per_fast_problem=4.0,
            live=True,
            summative=False,
            author=None,
            raw_html=None,
            last_modified=None,
            creation_date=datetime.datetime(2012, 3, 28, 20, 38, 50, 152332),
            description=None,
            tags=[])
        self.equations.put()

        # TODO(csilvers): add a non-live exercise


class ExercisesAndVideos(object):
    """Create ExerciseAndVideoModel's, tying together exercises and videos."""
    def __init__(self, exercises, videos):
        """Takes a Videos object and an Exercises object."""
        self.exponents = exercise_video_model.ExerciseVideo(
            video=videos.exponents,
            exercise=exercises.exponents,
            exercise_order=1)
        self.exponents.put()

        self.equations = exercise_video_model.ExerciseVideo(
            video=videos.equations,
            exercise=exercises.equations,
            exercise_order=1)
        self.equations.put()

        # While this is not technically accurate, we will put the
        # domain/range video with the equations exercise as well, to
        # test exercise_order.
        self.equations_with_domain_range = exercise_video_model.ExerciseVideo(
            video=videos.domain_and_range,
            exercise=exercises.equations,
            exercise_order=2)
        self.equations_with_domain_range.put()


class TopicVersions(object):
    """Create a few TopicVersion objects for our topic trees."""
    def __init__(self, users):
        """We need a Users object so we can set last_edited_by."""
        self.earliest_version = topic_models.TopicVersion(
            created_on=datetime.datetime(2012, 3, 28, 20, 43, 4, 899284),
            updated_on=datetime.datetime(2012, 3, 29, 3, 50, 26, 957484),
            made_default_on=datetime.datetime(2012, 3, 29, 2, 2, 54, 41337),
            copied_from=None,
            last_edited_by=users.user2.user,
            number=2,
            title=None,
            description=None,
            default=False,
            edit=False)
        self.earliest_version.put()

        self.latest_version = topic_models.TopicVersion(
            created_on=datetime.datetime(2012, 3, 30, 21, 34, 28, 735412),
            updated_on=datetime.datetime(2012, 3, 30, 21, 34, 53, 164824),
            made_default_on=None,
            copied_from=self.earliest_version.key(),
            last_edited_by=users.user1.user,
            number=11,
            title=None,
            description=None,
            default=False,
            edit=True)
        self.latest_version.put()

    def set_default_version_and_update_stats(self):
        """Make earliest_version the default version (after editing/etc)."""
        # This also calls topic_models._rebuild_content_caches
        # TODO(csilvers): create VersionContentChange and start this
        # earlier in the chaining-process, perhaps at _check_for_problems?
        topic_models._change_default_version(self.latest_version.number, '')


class Topics(object):
    """Various Topic trees, attached to our TopicVersions."""
    def __init__(self, users, topic_versions, exercises, videos):
        """Create Topic's and insert existing exercises/videos into them."""

        # We have two occurrences of (most) every topic, one for the
        # earliest topic-version, and one for the latest.  To make
        # this easier, we store the common elements in a map --
        # everything except the version and the parent-child
        # relationships.
        root_fields = {
            'standalone_title': 'The Root of All Knowledge',
            'id': 'root',
            'extended_slug': '',
            'description': 'All concepts fit into the root of all knowledge',
            'tags': [],
            'hide': True,
            'created_on': datetime.datetime(2012, 3, 28, 20, 37, 8, 650430),
            'updated_on': datetime.datetime(2012, 3, 30, 21, 29, 0, 354519),
            'last_edited_by': None
            }

        math_fields = {
            'standalone_title': 'All About Math',
            'id': 'math',
            'extended_slug': '',
            'description': 'A super-topic I made up for this test',
            'tags': ['math'],
            'hide': False,
            'created_on': datetime.datetime(2011, 3, 27, 19, 17, 14, 12),
            'updated_on': datetime.datetime(2012, 1, 30, 11, 18, 17, 14087),
            'last_edited_by': users.developer.user
            }

        art_fields = {
            'standalone_title': 'All About Art',
            'id': 'art',
            'extended_slug': '',
            'description': 'A super-topic I made up for this test',
            'tags': ['art', 'art history'],
            'hide': False,
            'created_on': datetime.datetime(2012, 4, 2, 1, 21, 28, 12345),
            'updated_on': datetime.datetime(2012, 4, 2, 1, 21, 29, 54321),
            'last_edited_by': users.user1.user
            }

        art_of_math_fields = {
            'standalone_title': 'The Art of Mathematics',
            'id': 'art_of_math',
            'extended_slug': '',
            'description': 'A topic with two parents I made up for this test',
            'tags': ['math', 'art', 'interdisciplinary'],
            'hide': True,
            'created_on': datetime.datetime(2012, 4, 5, 1, 21, 28, 12345),
            'updated_on': datetime.datetime(2012, 4, 5, 1, 21, 29, 54321),
            'last_edited_by': users.user1.user
            }

        exponents_fields = {
            'standalone_title': 'Basic Exponents',
            'id': 'basic-exponents',
            'extended_slug': '',
            'description': '',
            'tags': [],
            'hide': False,
            'created_on': datetime.datetime(2012, 3, 28, 20, 37, 54, 265414),
            'updated_on': datetime.datetime(2012, 3, 30, 21, 28, 37, 146678),
            'last_edited_by': None
            }

        other_fields = {
            'standalone_title': 'Mathematics (other)',
            'id': 'math-other',
            'extended_slug': '',
            'description': 'Miscellaneous math topics',
            'tags': ['math'],
            'hide': False,
            'created_on': datetime.datetime(2012, 1, 21, 20, 37, 54, 265414),
            'updated_on': datetime.datetime(2012, 1, 23, 21, 28, 37, 146678),
            'last_edited_by': None
            }

        equations_fields = {
            'standalone_title': 'One-Step Equations',
            'id': 'basic-equations',
            'extended_slug': '',
            'description': 'A topic I made up for this test',
            'tags': ['math', 'equations'],
            'hide': False,
            'created_on': datetime.datetime(2011, 3, 28, 9, 7, 4, 7012),
            'updated_on': datetime.datetime(2012, 1, 30, 1, 8, 7, 4087),
            'last_edited_by': users.developer.user
            }

        # Now the real fun: creating a tree.  Each version will have a
        # slightly different tree.  We have to insert the root
        # manually, but after that we can use a convenience routine.

        # The early-topic-version tree.
        self.early_root = topic_models.Topic(
            title='The Root of All Knowledge [early]',
            version=topic_versions.earliest_version,
            key_name=topic_models.Topic.get_new_key_name(),
            **root_fields)
        self.early_root.put()

        math = topic_models.Topic.insert('Mathematics [early]',
                                         self.early_root, **math_fields)

        exponents = topic_models.Topic.insert('Exponents (Basic) [early]',
                                              math, **exponents_fields)
        self.add_content_to(exercises.exponents, exponents)
        self.add_content_to(videos.exponents, exponents)        

        equations = topic_models.Topic.insert('Equations (one-step) [early]',
                                              math, **equations_fields)
        self.add_content_to(exercises.equations, equations)
        self.add_content_to(videos.equations, equations)        
        # In our early topic-tree, we incorrectly say that absolute
        # value falls under equations.  (That will be fixed in the
        # later topic-tree!)
        self.add_content_to(videos.absolute_value, equations)

        other = topic_models.Topic.insert('Other [early]',
                                          math, **other_fields)
        self.add_content_to(videos.domain_and_range, other)

        art = topic_models.Topic.insert('Art History [early]',
                                        self.early_root, **art_fields)
        self.add_content_to(videos.courbet, art)

        # The late-topic-version tree.
        self.late_root = topic_models.Topic(
            title='The Root of All Knowledge [late]',
            version=topic_versions.latest_version,
            key_name=topic_models.Topic.get_new_key_name(),
            **root_fields)
        self.late_root.put()

        math = topic_models.Topic.insert('Mathematics [late]',
                                         self.late_root, **math_fields)

        exponents = topic_models.Topic.insert('Exponents (Basic) [late]',
                                              math, **exponents_fields)
        self.add_content_to(exercises.exponents, exponents)
        self.add_content_to(videos.exponents, exponents)        

        equations = topic_models.Topic.insert('Equations (one-step) [late]',
                                              math, **equations_fields)
        self.add_content_to(exercises.equations, equations)
        self.add_content_to(videos.equations, equations)        

        other = topic_models.Topic.insert('Other [late]',
                                          math, **other_fields)
        self.add_content_to(videos.domain_and_range, other)
        self.add_content_to(videos.absolute_value, other)

        art = topic_models.Topic.insert('Art History [late]',
                                        self.late_root, **art_fields)
        self.add_content_to(videos.courbet, art)
        # Let's also test having a Url entity as a child.
        art_video_url = url_model.Url(
            url='http://www.youtube.com/watch?v=oZOsR0TzbJ8',
            title='The History of Art in 3 Minutes',
            created_on=datetime.datetime(2011, 3, 24, 13, 55, 0, 12311),
            updated_on=datetime.datetime(2012, 5, 30, 1, 11, 22, 40871),
        )
        art_video_url.put()
        self.add_content_to(art_video_url, art)

        # Add in a hidden topic as well, with a url of its own
        art_of_math = topic_models.Topic.insert('Mathematics of Art',
                                                self.late_root,
                                                **art_of_math_fields)
        art_of_math_video_url = url_model.Url(
            url='http://www.youtube.com/watch?v=vb4OrqPBQyA',
            title='Mathematics & art',
            created_on=datetime.datetime(2011, 3, 24, 13, 55, 0, 12312),
            updated_on=datetime.datetime(2012, 5, 30, 1, 11, 22, 40872),
        )
        art_of_math_video_url.put()
        self.add_content_to(art_of_math_video_url, art_of_math)

        # Now that we've set up the topic trees, let's make one of
        # them the default.  This also updates some internal caches.
        topic_versions.set_default_version_and_update_stats()

    def add_content_to(self, content_object, parent):
        """Add an exercise, video, or url as a child of topic-node 'parent'."""
        parent.child_keys.append(content_object.key())
        parent.put()

        content_object.topic_string_keys.append(str(parent.key()))
        content_object.put()


class MapLayout(object):
    """MapLayout objects connect topics which contain exercises in a graph."""
    def __init__(self, topic_versions):
        """Create a MapLayout object for each topic-tree we have."""
        self.layout = {}
        for (i, version) in enumerate((topic_versions.earliest_version,
                                       topic_versions.latest_version)):
            # TODO(csilvers): just add every topic that has an
            # exercise as a child.
            mlayout = {'polylines': [], 'topics': {}}
            mlayout['topics']['basic-equations'] = {
                'icon_url': '/images/power-mode/badges/default-40x40.png',
                'id': 'basic-equations',
                'standalone_title': 'One-Step Equations',
                'x': i,
                'y': 6,
                }
            mlayout['topics']['basic-exponents'] = {
                'icon_url': '/images/power-mode/badges/default-40x40.png',
                'id': 'basic-exponents',
                'standalone_title': 'Basic Exponents',
                'x': i,
                'y': 16,
                }
            mlayout['polylines'].append(
                {'path': [{'x': i, 'y': 6}, {'x': i, 'y': 16}]},
                )
            
            self.layout[version.number] = layout.MapLayout(
                    key_name=layout.MapLayout.key_for_version(version),
                    version=version,
                    layout=mlayout)
            self.layout[version.number].put()
            db.get(self.layout[version.number].key())


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
    handler_test_utils.start_dev_appserver()
    try:
        stub()

        print >>sys.stderr, 'Making users'
        users = Users()

        print >>sys.stderr, 'Making videos'
        videos = Videos()
        print >>sys.stderr, 'Making exercises'
        exercises = Exercises()
        print >>sys.stderr, 'Making exercises-and-videos'
        exercises_and_videos = ExercisesAndVideos(exercises, videos)
        print >>sys.stderr, 'Watching and doing videos and exercises'
        users.add_progress(exercises_and_videos)

        print >>sys.stderr, 'Making topic versions'
        topic_versions = TopicVersions(users)
        print >>sys.stderr, 'Making topic trees'
        unused_topics = Topics(users, topic_versions, exercises, videos)
        print >>sys.stderr, 'Making map layout'
        unused_map_layout = MapLayout(topic_versions)

        print >>sys.stderr, 'Making common core map'
        unused_common_core_map = CommonCoreMap()
        
        # OK, that was enough to create the db.  Let's put it in its
        # official home.
        print >>sys.stderr, 'Copying out data'
        shutil.copy(os.path.join(handler_test_utils.tmpdir,
                                 'datastore', 'test.sqlite'),
                    db_filename)

        print >>sys.stderr, 'Done!  Output in %s' % db_filename
    finally:
        # We keep around the tmpdir for debugging/etc
        handler_test_utils.stop_dev_appserver(delete_tmpdir=False)


if __name__ == '__main__':
    try:
        db_filename = sys.argv[1]
    except IndexError:
        sys.exit(__doc__)

    main(db_filename)
