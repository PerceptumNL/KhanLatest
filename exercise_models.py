"""Holds Exercise/UserExercise/UserExerciseCache/UserExerciseGraph/ProblemLog.

Exercise: database entity about a single exercise
UserExercise: database entity about a single user's interaction
   with a single exercise
UserExerciseCache: database entity for a cache to speed access to UserExercise
UserExerciseGraph: all the exercises tried by a single user.  Note that
   this is not a model, despite being in exercise_model.py
   TODO(csilvers): move to a different file in this directory?
ProblemLog: information about a single problem done by a single user in some
    exercise.
StackLog: information about a stack (in Power Mode) done by a single user.
    A stack is a group of problems in an exercise session, characterized by the
    "stack" of cards in the exercise UI (see below).

An 'exercise' is what's on a Khan page like
   http://www.khanacademy.org/math/arithmetic/addition-subtraction/e
"""

import datetime
import itertools
import logging
import math
import random

from google.appengine.ext import db

from exercises import accuracy_model
from exercises import progress_normalizer
import app
import backup_model
import consts
import decorators
from exercises import file_contents, stacks
import experiments
from gae_bingo import gae_bingo
import gandalf.bridge
import layer_cache
import object_property
import phantom_users
import setting_model
import url_util
import user_models
import user_util
import util
from tincan import TinCan


# About 1 out of every N problems in a topic will be a card used for analytics
# purposes
ASSESSMENT_CARD_PERIOD = 8

class Exercise(backup_model.BackupModel):
    """Information about a single exercise."""
    name = db.StringProperty()
    file_name = db.StringProperty()
    pretty_display_name = db.StringProperty()
    short_display_name = db.StringProperty(default="")
    prerequisites = db.StringListProperty()
    covers = db.StringListProperty()
    v_position = db.IntegerProperty() # actually horizontal position on knowledge map
    h_position = db.IntegerProperty() # actually vertical position on knowledge map
    seconds_per_fast_problem = db.FloatProperty(default=consts.INITIAL_SECONDS_PER_FAST_PROBLEM) # Seconds expected to finish a problem 'quickly' for badge calculation

    # True if this exercise is live and visible to all users.
    # Non-live exercises are only visible to admins.
    live = db.BooleanProperty(default=False)

    summative = db.BooleanProperty(default=False)

    # User's requesting a missing video
    video_requests = db.ListProperty(db.Key)

    # Teachers contribute raw html with embedded CSS and JS
    # and we sanitize it with Caja before displaying it to
    # students.
    author = db.UserProperty()
    raw_html = db.TextProperty()
    last_modified = db.DateTimeProperty()
    creation_date = db.DateTimeProperty(auto_now_add=True, default=datetime.datetime(2011, 1, 1))
    description = db.TextProperty()
    tags = db.StringListProperty()

    # List of parent topics
    topic_string_keys = object_property.TsvProperty(indexed=False)

    _serialize_blacklist = [
            "author", "raw_html", "last_modified",
            "coverers", "prerequisites_ex", "assigned",
            "topic_string_keys", "related_video_keys", "video_requests"
            ]

    @staticmethod
    def get_relative_url(exercise_name):
        return "/exercise/%s" % exercise_name

    @property
    def relative_url(self):
        return Exercise.get_relative_url(self.name)

    @property
    def ka_url(self):
        return url_util.absolute_url(self.relative_url)

    @staticmethod
    def get_by_name(name, version=None):
        dict_exercises = Exercise._get_dict_use_cache_unsafe()
        if dict_exercises.has_key(name):
            if dict_exercises[name].is_visible_to_current_user():
                exercise = dict_exercises[name]
                # if there is a version check to see if there are any updates to the video
                if version:
                    # TODO(csilvers): remove circular dependency here
                    import topic_models
                    change = topic_models.VersionContentChange.get_change_for_content(exercise, version)
                    if change:
                        exercise = change.updated_content(exercise)
                return exercise
        return None

    @staticmethod
    def to_display_name(name):
        exercise = Exercise.get_by_name(name)
        return exercise.display_name if exercise else ""

    @property
    def display_name(self):
        # TODO(eater): remove this after adding a display name to all existing exercise entities
        if self.pretty_display_name:
            return self.pretty_display_name
        else:
            return self.name.replace('_', ' ').capitalize()

    @property
    def sha1(self):
        return file_contents.exercise_sha1(self)

    @staticmethod
    def to_short_name(name):
        exercise = Exercise.get_by_name(name)
        return exercise.short_name() if exercise else ""

    def short_name(self):
        return (self.short_display_name or self.display_name)[:11]

    def is_visible_to_current_user(self):
        return self.live or user_util.is_current_user_developer()

    def has_topic(self):
        return bool(self.topic_string_keys)

    def first_topic(self):
        """ Returns this Exercise's first non-hidden parent Topic """

        if self.topic_string_keys:
            return db.get(self.topic_string_keys[0])

        return None

    def request_video(self):
        # TODO(csilvers): get rid of circular dependency here
        user = user_models.UserData.current()
        if (self.video_requested):
            raise Exception("Video for exercise %s already requested by %s" %
                            (self.name, user.username))
        self.video_requests.append(user.key())
        self.put()


    @property
    def video_requested(self):
        user = user_models.UserData.current()
        return (user.key() in self.video_requests)

    @property
    def video_requests_count(self):
        return len(self.video_requests)


    def related_videos_query(self):
        # TODO(csilvers): get rid of circular dependency here
        import exercise_video_model
        query = exercise_video_model.ExerciseVideo.all()
        query.filter('exercise =', self.key()).order('exercise_order')
        return query

    @layer_cache.cache_with_key_fxn(lambda self: "related_videos_%s_%s" %
        (self.key(), setting_model.Setting.topic_tree_version()),
        layer=layer_cache.Layers.Memcache)
    def related_videos_fetch(self):
        exercise_videos = self.related_videos_query().fetch(10)
        for exercise_video in exercise_videos:
            exercise_video.video # Pre-cache video entity
        return exercise_videos

    @staticmethod
    def add_related_video_readable_ids_prop(exercise_dict,
                                            evs=None,
                                            video_dict=None):
        # TODO(csilvers): get rid of circular dependency here
        import exercise_video_model

        if video_dict is None:
            video_dict = {}

        # if no pregotten evs were passed in asynchronously get them for all
        # exercises in exercise_dict
        if evs is None:
            queries = []
            for exercise in exercise_dict.values():
                queries.append(exercise.related_videos_query())

            tasks = util.async_queries(queries, limit=10000)
            evs = [ev for task in tasks for ev in task.get_result()]

        # if too many evs were passed in filter out exercise_videos which are
        # not looking at one of the exercises in exercise_dict
        evs = [ev for ev in evs
               if exercise_video_model.ExerciseVideo.exercise.get_value_for_datastore(ev)
               in exercise_dict]

        # add any videos to video_dict that we need and are not already in
        # the video_dict passed in
        extra_video_keys = [exercise_video_model.ExerciseVideo.video.get_value_for_datastore(ev)
            for ev in evs if exercise_video_model.ExerciseVideo.video.get_value_for_datastore(ev)
            not in video_dict]
        extra_videos = db.get(extra_video_keys)
        extra_video_dict = dict((v.key(), v) for v in extra_videos)
        video_dict.update(extra_video_dict)

        # buid a ev_dict in the form
        # ev_dict[exercise_key][video_key] = (video_readable_id, ev.exercise_order)
        ev_dict = {}
        for ev in evs:
            exercise_key = exercise_video_model.ExerciseVideo.exercise.get_value_for_datastore(ev)
            video_key = exercise_video_model.ExerciseVideo.video.get_value_for_datastore(ev)
            video_readable_id = video_dict[video_key].readable_id

            if exercise_key not in ev_dict:
                ev_dict[exercise_key] = {}

            ev_dict[exercise_key][video_key] = (video_readable_id, ev.exercise_order)

        # update all exercises to include the related_videos in their right
        # orders
        for exercise in exercise_dict.values():
            related_videos = (ev_dict[exercise.key()]
                              if exercise.key() in ev_dict else {})
            related_videos = sorted(related_videos.items(),
                                    key=lambda i:i[1][1])
            exercise.related_video_keys = map(lambda i: i[0], related_videos)
            exercise.related_video_readable_ids = map(lambda i: i[1][0], related_videos)

    # followup_exercises reverse walks the prerequisites to give you
    # the exercises that list the current exercise as its prerequisite.
    # i.e. follow this exercise up with these other exercises
    def followup_exercises(self):
        return [exercise for exercise in Exercise.get_all_use_cache() if self.name in exercise.prerequisites]

    @classmethod
    def all(cls, live_only=False, **kwargs):
        query = super(Exercise, cls).all(**kwargs)
        if live_only or not user_util.is_current_user_developer():
            query.filter("live =", True)
        return query

    @classmethod
    def all_unsafe(cls, **kwargs):
        return super(Exercise, cls).all(**kwargs)

    @staticmethod
    def get_all_use_cache():
        if user_util.is_current_user_developer():
            return Exercise._get_all_use_cache_unsafe()
        else:
            return Exercise._get_all_use_cache_safe()

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda * args, **kwargs: "all_exercises_unsafe_%s" %
            setting_model.Setting.cached_exercises_date())
    def _get_all_use_cache_unsafe():
        query = Exercise.all_unsafe().order('h_position')
        return query.fetch(1000) # TODO(Ben) this limit is tenuous

    @staticmethod
    def _get_all_use_cache_safe():
        return filter(lambda exercise: exercise.live, Exercise._get_all_use_cache_unsafe())

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda * args, **kwargs: "all_exercises_dict_unsafe_%s" %
            setting_model.Setting.cached_exercises_date())
    def _get_dict_use_cache_unsafe():
        exercises = Exercise._get_all_use_cache_unsafe()
        dict_exercises = {}
        for exercise in exercises:
            dict_exercises[exercise.name] = exercise
        return dict_exercises

    @staticmethod
    @layer_cache.cache(expiration=3600)
    def get_count():
        return Exercise.all(live_only=True).count()

    def put(self):
        setting_model.Setting.cached_exercises_date(str(datetime.datetime.now()))
        db.Model.put(self)
        Exercise.get_count(bust_cache=True)

    @staticmethod
    def get_dict(query, fxn_key):
        exercise_dict = {}
        for exercise in query.fetch(10000):
            exercise_dict[fxn_key(exercise)] = exercise
        return exercise_dict

class UserExercise(backup_model.BackupModel):
    """Information about a single user's interaction with a single exercise."""
    user = db.UserProperty()
    exercise = db.StringProperty()
    exercise_model = db.ReferenceProperty(Exercise)
    streak = db.IntegerProperty(default=0)
    _progress = db.FloatProperty(default=None, indexed=False)  # A continuous value >= 0.0, where 1.0 means proficiency. This measure abstracts away the internal proficiency model.
    longest_streak = db.IntegerProperty(default=0, indexed=False)
    first_done = db.DateTimeProperty(auto_now_add=True)
    last_done = db.DateTimeProperty()
    total_done = db.IntegerProperty(default=0)
    total_correct = db.IntegerProperty(default=0)
    last_review = db.DateTimeProperty(default=datetime.datetime.min)
    review_interval_secs = db.IntegerProperty(default=(60 * 60 * 24 * consts.DEFAULT_REVIEW_INTERVAL_DAYS), indexed=False) # Default 7 days until review
    proficient_date = db.DateTimeProperty()
    seconds_per_fast_problem = db.FloatProperty(default=consts.INITIAL_SECONDS_PER_FAST_PROBLEM, indexed=False) # Seconds expected to finish a problem 'quickly' for badge calculation
    _accuracy_model = object_property.ObjectProperty()  # Stateful function object that estimates P(next problem correct). May not exist for old UserExercise objects (but will be created when needed).

    _USER_EXERCISE_KEY_FORMAT = "UserExercise.all().filter('user = '%s')"

    _serialize_blacklist = ["review_interval_secs", "_progress", "_accuracy_model"]

    _MIN_PROBLEMS_FROM_ACCURACY_MODEL = accuracy_model.AccuracyModel.min_streak_till_threshold(consts.PROFICIENCY_ACCURACY_THRESHOLD)
    _MIN_PROBLEMS_REQUIRED = max(_MIN_PROBLEMS_FROM_ACCURACY_MODEL, consts.MIN_PROBLEMS_IMPOSED)

    # Bound function objects to normalize the progress bar display from a probability
    # TODO(david): This is a bit of a hack to not have the normalizer move too
    #     slowly if the user got a lot of wrongs.
    _all_correct_normalizer = progress_normalizer.InvFnExponentialNormalizer(
        accuracy_model=accuracy_model.AccuracyModel().update(correct=False),
        proficiency_threshold=accuracy_model.AccuracyModel.simulate([True] * _MIN_PROBLEMS_REQUIRED)
    ).normalize
    _had_wrong_normalizer = progress_normalizer.InvFnExponentialNormalizer(
        accuracy_model=accuracy_model.AccuracyModel().update([False] * 3),
        proficiency_threshold=consts.PROFICIENCY_ACCURACY_THRESHOLD
    ).normalize

    @property
    def exercise_states(self):
        user_exercise_graph = self.get_user_exercise_graph()
        if user_exercise_graph:
            return user_exercise_graph.states(self.exercise)
        return None

    def accuracy_model(self):
        if self._accuracy_model is None:
            self._accuracy_model = accuracy_model.AccuracyModel(self)
        return self._accuracy_model

    # Faciliate transition for old objects that did not have the _progress property
    @property
    @decorators.clamp(0.0, 1.0)
    def progress(self):
        if self._progress is None:
            self._progress = self._get_progress_from_current_state()
        return self._progress

    def update_proficiency_model(self, correct):
        if not correct:
            self.streak = 0

        self.accuracy_model().update(correct)
        self._progress = self._get_progress_from_current_state()

    @decorators.clamp(0.0, 1.0)
    def _get_progress_from_current_state(self):

        if self.total_correct == 0:
            return 0.0

        prediction = self.accuracy_model().predict()

        if self.accuracy_model().total_done <= self.accuracy_model().total_correct():
            # Impose a minimum number of problems required to be done.
            normalized_prediction = UserExercise._all_correct_normalizer(prediction)
        else:
            normalized_prediction = UserExercise._had_wrong_normalizer(prediction)

        return normalized_prediction

    @staticmethod
    def to_progress_display(num):
        return '%.0f%%' % math.floor(num * 100.0) if num <= consts.MAX_PROGRESS_SHOWN else 'Max'

    def progress_display(self):
        return UserExercise.to_progress_display(self.progress)

    @staticmethod
    def get_key_for_email(email):
        return UserExercise._USER_EXERCISE_KEY_FORMAT % email

    @staticmethod
    def get_for_user_data(user_data):
        query = UserExercise.all()
        query.filter('user =', user_data.user)
        return query

    def get_user_data(self):
        user_data = None

        if hasattr(self, "_user_data"):
            user_data = self._user_data
        else:
            user_data = user_models.UserData.get_from_db_key_email(self.user.email())

        if not user_data:
            logging.critical("Empty user data for UserExercise w/ .user = %s" % self.user)

        return user_data

    def get_user_exercise_graph(self):
        user_exercise_graph = None

        if hasattr(self, "_user_exercise_graph"):
            user_exercise_graph = self._user_exercise_graph
        else:
            user_exercise_graph = UserExerciseGraph.get(self.get_user_data())

        return user_exercise_graph

    def belongs_to(self, user_data):
        return user_data and self.user.email().lower() == user_data.key_email.lower()

    def is_struggling(self, struggling_model=None):
        """ Whether or not the user is currently "struggling" in this exercise
        for a given struggling model. Note that regardless of struggling model,
        if the last question was correct, the student is not considered
        struggling.
        """
        if self.has_been_proficient():
            return False

        return self.history_indicates_struggling(struggling_model)

    # TODO(benkomalo): collapse this method with is_struggling above.
    def history_indicates_struggling(self, struggling_model=None):
        """ Whether or not the history of answers indicates that the user
        is struggling on this exercise.

        Does not take into consideration if the last question was correct. """

        if struggling_model is None or struggling_model == 'old':
            return self._is_struggling_old()
        else:
            # accuracy based model.
            param = float(struggling_model.split('_')[1])
            return self.accuracy_model().is_struggling(
                    param=param,
                    minimum_accuracy=consts.PROFICIENCY_ACCURACY_THRESHOLD,
                    minimum_attempts=consts.MIN_PROBLEMS_IMPOSED)

    def _is_struggling_old(self):
        return self.streak == 0 and self.total_done > 20

    @staticmethod
    @decorators.clamp(datetime.timedelta(days=consts.MIN_REVIEW_INTERVAL_DAYS),
                      datetime.timedelta(days=consts.MAX_REVIEW_INTERVAL_DAYS))
    def get_review_interval_from_seconds(seconds):
        return datetime.timedelta(seconds=seconds)

    def has_been_proficient(self):
        return self.proficient_date is not None

    def get_review_interval(self):
        return UserExercise.get_review_interval_from_seconds(self.review_interval_secs)

    def schedule_review(self, correct, now=None):
        if now is None:
            now = datetime.datetime.now()

        # If the user is not now and never has been proficient, don't schedule a review
        if self.progress < 1.0 and not self.has_been_proficient():
            return

        if self.progress >= 1.0:
            # If the user is highly accurate, put a floor under their review_interval
            self.review_interval_secs = max(self.review_interval_secs, 60 * 60 *24 * consts.DEFAULT_REVIEW_INTERVAL_DAYS)
        else:
            # If the user is no longer highly accurate, put a cap on their review_interval
            self.review_interval_secs = min(self.review_interval_secs, 60 * 60 *24 * consts.DEFAULT_REVIEW_INTERVAL_DAYS)

        review_interval = self.get_review_interval()

        # If we correctly did this review while it was in a review state, and
        # the previous review was correct, extend the review interval
        if correct and self.last_review != datetime.datetime.min:
            time_since_last_review = now - self.last_review
            if time_since_last_review >= review_interval:
                review_interval = time_since_last_review * 2

        if correct:
            self.last_review = now
        else:
            self.last_review = datetime.datetime.min
            review_interval = review_interval // 2

        self.review_interval_secs = review_interval.days * 86400 + review_interval.seconds

    def set_proficient(self, user_data):
        if self.exercise in user_data.proficient_exercises:
            return

        self.proficient_date = datetime.datetime.now()

        user_data.proficient_exercises.append(self.exercise)
        user_data.need_to_reassess = True

        phantom_users.util_notify.update(user_data, self, False, True)

        user_data.put()

    @classmethod
    def from_json(cls, json, user_data):
        '''This method exists for testing convenience only. It's called only
        by code that runs in exclusively in development mode. Do not rely on
        this method in production code. If you need to break this code to
        implement some new feature, feel free!
        '''
        exercise = Exercise.get_by_name(json['exercise'])
        if not exercise:
            return None

        # this is probably completely broken as we don't serialize anywhere near
        # all the properties that UserExercise has. Still, let's see if it works
        return cls(
            key_name=exercise.name,
            parent=user_data,
            user=user_data.user,
            exercise=exercise.name,
            exercise_model=exercise,
            streak=int(json['streak']),
            longest_streak=int(json['longest_streak']),
            first_done=util.parse_iso8601(json['first_done']),
            last_done=util.coalesce(util.parse_iso8601, json['last_done']),
            total_done=int(json['total_done']),
            _accuracy_model=accuracy_model.AccuracyModel()
        )

    @classmethod
    def from_dict(cls, attrs, user_data):
        """ Create a UserExercise model from a dictionary of attributes
        and a UserData model. This is useful for creating these objects
        from the property dictionaries cached in UserExerciseCache.
        """

        user_exercise = cls(
            key_name=attrs["name"],
            parent=user_data,
            user=user_data.user,
            exercise=attrs["name"],
            _progress=attrs["progress"],
        )

        for key in attrs:
            if hasattr(user_exercise, key):
                try:
                    setattr(user_exercise, key, attrs[key])
                except AttributeError:
                    # Some attributes are unsettable -- ignore
                    pass

        return user_exercise

    @staticmethod
    def next_in_topic(user_data, topic, n=3, queued=[]):
        """ Returns the next n suggested user exercises for this topic,
        all prepped and ready for JSONification, as a tuple.

        TODO(save us, Jace): *This* is where the magic will happen.
        """

        exercises = topic.get_exercises(include_descendants=True)
        graph = UserExerciseGraph.get(user_data, exercises_allowed=exercises)

        # Start of by doing exercises that are in review
        stack_dicts = graph.review_graph_dicts()

        if len(stack_dicts) < n:
            # Now get all boundary exercises (those that aren't proficient and
            # aren't covered by other boundary exercises)
            frontier = UserExerciseGraph.get_boundary_names(graph.graph)
            frontier_dicts = [graph.graph_dict(exid) for exid in frontier]

            # If we don't have *any* boundary exercises, fill things out with the other
            # topic exercises. Note that if we have at least one boundary exercise, we don't
            # want to add others to the mix because they may screw w/ the boundary conditions
            # by adding a too-difficult exercise, etc.
            if len(frontier_dicts) == 0:
                frontier_dicts = graph.graph_dicts()

            # Now we sort the exercises by last_done and progress. If five exercises
            # all have the same progress, we want to send the user the one they did
            # least recently. Otherwise, we send the exercise that is most lacking in
            # progress.
            sorted_dicts = sorted(frontier_dicts, key=lambda d: d.get("last_done", None) or datetime.datetime.min)
            sorted_dicts = sorted(sorted_dicts, key=lambda d: d["progress"])

            stack_dicts += sorted_dicts

        # Build up UserExercise objects from our graph dicts
        user_exercises = [UserExercise.from_dict(d, user_data) for d in stack_dicts]

        # Possibly insert a random exercise from this topic. This is used to
        # measure effectiveness and engagement for analytics. We select at
        # random in an effort to be unbiased from the card selection
        # algorithm, # of cards in stack, etc.
        if gandalf.bridge.gandalf('random_analytics_card'):
            def insert_random_card():
                random_dict = random.choice(graph.graph_dicts())
                random_u_e = UserExercise.from_dict(random_dict, user_data)
                random_u_e.scheduler_info = { 'purpose': 'randomized' }
                user_exercises.insert(i, random_u_e)

            for i in range(n):
                if random.random() < 1.0 / ASSESSMENT_CARD_PERIOD:
                    insert_random_card()

        return UserExercise._prepare_for_stack_api(user_exercises, n, queued)

    @staticmethod
    def next_in_review(user_data, n=3, queued=[]):
        """ Returns the next n suggested user exercises for this user's
        review mode, all prepped and ready for JSONification
        """
        graph = UserExerciseGraph.get(user_data)

        # Build up UserExercise objects from our graph dicts
        user_exercises = [UserExercise.from_dict(d, user_data) for d in graph.review_graph_dicts()]

        return UserExercise._prepare_for_stack_api(user_exercises, n, queued)

    @staticmethod
    def next_in_practice(user_data, exercise):
        """ Returns single user exercise used to practice specified exercise,
        all prepped and ready for JSONification
        """
        graph = UserExerciseGraph.get(user_data)
        user_exercise = UserExercise.from_dict(graph.graph_dict(exercise.name), user_data)
        return UserExercise._prepare_for_stack_api([user_exercise])

    @staticmethod
    def _prepare_for_stack_api(user_exercises, n=3, queued=[]):
        """ Returns the passed-in list of UserExercises, with additional properties
        added in preparation for JSONification by our API.

        Limits user_exercises returned to n, and filters out any user_exercises
        that are already queued up in the stack.

        TODO: when we eventually have support for various API projections, get rid
        of this manual property additions.
        """
        # Filter out already queued exercises
        user_exercises = [u_e for u_e in user_exercises if u_e.exercise not in queued][:n]

        for user_exercise in user_exercises:
            exercise = Exercise.get_by_name(user_exercise.exercise)

            # Attach related videos before sending down
            exercise.related_videos = [exercise_video.video for exercise_video in exercise.related_videos_fetch()]

            for video in exercise.related_videos:
                # TODO: this property is used by khan-exercises to render the progress
                # icon for related videos. If we decide to expose ids for all models via the API,
                # this will go away.
                video.id = video.key().id()

            user_exercise.exercise_model = exercise

        return user_exercises


class UserExerciseCache(db.Model):
    """Cache of user-specific exercise states.

    This cache is optimized for read and deserialization.
    It can be reconstituted at any time via UserExercise objects.
    """

    # Bump this whenever you change the structure of the cached UserExercises
    # and need to invalidate all old caches
    CURRENT_VERSION = 9

    version = db.IntegerProperty()
    dicts = object_property.UnvalidatedObjectProperty()

    def user_exercise_dict(self, exercise_name):
        return self.dicts.get(exercise_name) or UserExerciseCache.dict_from_user_exercise(None)

    def update(self, user_exercise):
        self.dicts[user_exercise.exercise] = UserExerciseCache.dict_from_user_exercise(user_exercise)

    @staticmethod
    def key_for_user_data(user_data):
        return "UserExerciseCache:%s" % user_data.key_email

    @staticmethod
    def get(user_data_or_list):
        if not user_data_or_list:
            raise Exception("Must provide UserData when loading UserExerciseCache")

        # We can grab a single UserExerciseCache or do an optimized grab of a bunch of 'em
        user_data_list = user_data_or_list if type(user_data_or_list) == list else [user_data_or_list]

        # Try to get 'em all by key name
        user_exercise_caches = UserExerciseCache.get_by_key_name(
                map(
                    lambda user_data: UserExerciseCache.key_for_user_data(user_data),
                    user_data_list),
                config=db.create_config(read_policy=db.EVENTUAL_CONSISTENCY)
                )

        # For any that are missing or are out of date,
        # build up asynchronous queries to repopulate their data
        async_queries = []
        missing_cache_indices = []
        for i, user_exercise_cache in enumerate(user_exercise_caches):
            if not user_exercise_cache or user_exercise_cache.version != UserExerciseCache.CURRENT_VERSION:
                # Null out the reference so the gc can collect, in case it's
                # a stale version, since we're going to rebuild it below.
                user_exercise_caches[i] = None

                # This user's cached graph is missing or out-of-date,
                # put it in the list of graphs to be regenerated.
                async_queries.append(UserExercise.get_for_user_data(user_data_list[i]))
                missing_cache_indices.append(i)

        if len(async_queries) > 0:
            caches_to_put = []

            # Run the async queries in batches to avoid exceeding memory limits.
            # Some coaches can have lots of active students, and their user
            # exercise information is too much for app engine instances.
            BATCH_SIZE = 5
            for i in range(0, len(async_queries), BATCH_SIZE):
                tasks = util.async_queries(async_queries[i:i + BATCH_SIZE])

                # Populate the missing graphs w/ results from async queries
                for j, task in enumerate(tasks):
                    user_index = missing_cache_indices[i + j]
                    user_data = user_data_list[user_index]
                    user_exercises = task.get_result()

                    user_exercise_cache = UserExerciseCache.generate(user_data, user_exercises)
                    user_exercise_caches[user_index] = user_exercise_cache

                    if len(caches_to_put) < 10:
                        # We only put 10 at a time in case a teacher views a report w/ tons and tons of uncached students
                        caches_to_put.append(user_exercise_cache)

            # Null out references explicitly for GC.
            tasks = None
            async_queries = None

            if len(caches_to_put) > 0:
                # Fire off an asynchronous put to cache the missing results. On the production server,
                # we don't wait for the put to finish before dealing w/ the rest of the request
                # because we don't really care if the cache misses.
                future_put = db.put_async(caches_to_put)

                if app.App.is_dev_server:
                    # On the dev server, we have to explicitly wait for get_result in order to
                    # trigger the put (not truly asynchronous).
                    future_put.get_result()

        if not user_exercise_caches:
            return []

        # Return list of caches if a list was passed in,
        # otherwise return single cache
        return user_exercise_caches if type(user_data_or_list) == list else user_exercise_caches[0]

    @staticmethod
    def dict_from_user_exercise(user_exercise, struggling_model=None):
        # TODO(david): We can probably remove some of this stuff here.
        return {
                "streak": user_exercise.streak if user_exercise else 0,
                "longest_streak": user_exercise.longest_streak if user_exercise else 0,
                "progress": user_exercise.progress if user_exercise else 0.0,
                "struggling": user_exercise.is_struggling(struggling_model) if user_exercise else False,
                "total_done": user_exercise.total_done if user_exercise else 0,
                "last_done": user_exercise.last_done if user_exercise else datetime.datetime.min,
                "last_review": user_exercise.last_review if user_exercise else datetime.datetime.min,
                "review_interval_secs": user_exercise.review_interval_secs if user_exercise else 0,
                "proficient_date": user_exercise.proficient_date if user_exercise else 0,
                }

    @staticmethod
    def generate(user_data, user_exercises=None):

        if not user_exercises:
            user_exercises = UserExercise.get_for_user_data(user_data)

        current_user = user_models.UserData.current()
        is_current_user = current_user and current_user.user_id == user_data.user_id

        # Experiment to try different struggling models.
        # It's important to pass in the user_data of the student owning the
        # exercise, and not of the current viewer (as it may be a coach).
        struggling_model = experiments.StrugglingExperiment.get_alternative_for_user(
                user_data, is_current_user) or experiments.StrugglingExperiment.DEFAULT

        dicts = {}

        # Build up cache
        for user_exercise in user_exercises:
            user_exercise_dict = UserExerciseCache.dict_from_user_exercise(
                    user_exercise, struggling_model)

            # In case user has multiple UserExercise mappings for a specific exercise,
            # always prefer the one w/ more problems done
            if user_exercise.exercise not in dicts or dicts[user_exercise.exercise]["total_done"] < user_exercise_dict["total_done"]:
                dicts[user_exercise.exercise] = user_exercise_dict

        return UserExerciseCache(
                key_name=UserExerciseCache.key_for_user_data(user_data),
                version=UserExerciseCache.CURRENT_VERSION,
                dicts=dicts,
            )


class UserExerciseGraph(object):
    """All the UserExercise data for a single user."""
    def __init__(self, graph={}, cache=None):
        self.graph = graph
        self.cache = cache

    def graph_dict(self, exercise_name):
        return self.graph.get(exercise_name)

    def graph_dicts(self):
        return sorted(sorted(self.graph.values(),
                             key=lambda graph_dict: graph_dict["v_position"]),
                             key=lambda graph_dict: graph_dict["h_position"])

    def proficient_exercise_names(self):
        return [graph_dict["name"] for graph_dict in self.proficient_graph_dicts()]

    def suggested_exercise_names(self):
        return [graph_dict["name"] for graph_dict in self.suggested_graph_dicts()]

    def review_exercise_names(self):
        return [graph_dict["name"] for graph_dict in self.review_graph_dicts()]

    def has_completed_review(self):
        # TODO(david): This should return whether the user has completed today's
        #     review session.
        return not self.review_exercise_names()

    def reviews_left_count(self):
        # TODO(david): For future algorithms this should return # reviews left
        #     for today's review session.
        # TODO(david): Make it impossible to have >= 100 reviews.
        return len(self.review_exercise_names())

    def suggested_graph_dicts(self):
        return [graph_dict for graph_dict in self.graph_dicts() if graph_dict["suggested"]]

    def proficient_graph_dicts(self):
        return [graph_dict for graph_dict in self.graph_dicts() if graph_dict["proficient"]]

    def review_graph_dicts(self):
        return [graph_dict for graph_dict in self.graph_dicts() if graph_dict["reviewing"]]

    def recent_graph_dicts(self, n_recent=2):
        return sorted(
                [graph_dict for graph_dict in self.graph_dicts() if graph_dict["last_done"]],
                reverse=True,
                key=lambda graph_dict: graph_dict["last_done"],
                )[0:n_recent]

    @staticmethod
    def mark_reviewing(graph):
        """ Mark to-be-reviewed exercise dicts as reviewing, which is used by the knowledge map
        and the profile page.
        """

        # an exercise ex should be reviewed iff all of the following are true:
        #   * ex and all of ex's covering ancestors either
        #      * are scheduled to have their next review in the past, or
        #      * were answered incorrectly on last review (i.e. streak == 0 with proficient == true)
        #   * none of ex's covering ancestors should be reviewed or ex was
        #     previously incorrectly answered (ex.streak == 0)
        #   * the user is proficient at ex
        # the algorithm:
        #   for each exercise:
        #     traverse it's ancestors, computing and storing the next review time (if not already done),
        #     using now as the next review time if proficient and streak==0
        #   select and mark the exercises in which the user is proficient but with next review times in the past as review candidates
        #   for each of those candidates:
        #     traverse it's ancestors, computing and storing whether an ancestor is also a candidate
        #   all exercises that are candidates but do not have ancestors as
        #   candidates should be listed for review. Covering ancestors are not
        #   considered for incorrectly answered review questions
        #   (streak == 0 and proficient).

        now = datetime.datetime.now()

        def compute_next_review(graph_dict):
            if graph_dict.get("next_review") is None:
                graph_dict["next_review"] = datetime.datetime.min

                if graph_dict["total_done"] > 0 and graph_dict["last_review"] and graph_dict["last_review"] > datetime.datetime.min:
                    next_review = graph_dict["last_review"] + UserExercise.get_review_interval_from_seconds(graph_dict["review_interval_secs"])

                    if next_review > now and graph_dict["proficient"] and graph_dict["streak"] == 0:
                        next_review = now

                    if next_review > graph_dict["next_review"]:
                        graph_dict["next_review"] = next_review

                for covering_graph_dict in graph_dict["coverer_dicts"]:
                    covering_next_review = compute_next_review(covering_graph_dict)
                    if (covering_next_review > graph_dict["next_review"] and
                            graph_dict["streak"] != 0):
                        graph_dict["next_review"] = covering_next_review

            return graph_dict["next_review"]

        def compute_is_ancestor_review_candidate(graph_dict):
            if graph_dict.get("is_ancestor_review_candidate") is None:

                graph_dict["is_ancestor_review_candidate"] = False

                for covering_graph_dict in graph_dict["coverer_dicts"]:
                    graph_dict["is_ancestor_review_candidate"] = (graph_dict["is_ancestor_review_candidate"] or
                            covering_graph_dict["is_review_candidate"] or
                            compute_is_ancestor_review_candidate(covering_graph_dict))

            return graph_dict["is_ancestor_review_candidate"]

        for graph_dict in graph.values():
            graph_dict["reviewing"] = False # Assume false at first
            compute_next_review(graph_dict)

        candidate_dicts = []
        for graph_dict in graph.values():
            if (graph_dict["proficient"] and
                    graph_dict["next_review"] <= now and
                    graph_dict["total_done"] > 0):
                graph_dict["is_review_candidate"] = True
                candidate_dicts.append(graph_dict)
            else:
                graph_dict["is_review_candidate"] = False

        for graph_dict in candidate_dicts:
            if (not compute_is_ancestor_review_candidate(graph_dict) or
                    graph_dict["streak"] == 0):
                graph_dict["reviewing"] = True

    def states(self, exercise_name):
        graph_dict = self.graph_dict(exercise_name)

        return {
            "proficient": graph_dict["proficient"],
            "suggested": graph_dict["suggested"],
            "struggling": graph_dict["struggling"],
            "reviewing": graph_dict["reviewing"]
        }

    @staticmethod
    def current():
        return UserExerciseGraph.get(user_models.UserData.current())

    @staticmethod
    def get(user_data_or_list, exercises_allowed=None):
        if not user_data_or_list:
            return [] if type(user_data_or_list) == list else None

        # We can grab a single UserExerciseGraph or do an optimized grab of a bunch of 'em
        user_data_list = user_data_or_list if type(user_data_or_list) == list else [user_data_or_list]
        user_exercise_cache_list = UserExerciseCache.get(user_data_list)

        if not user_exercise_cache_list:
            return [] if type(user_data_or_list) == list else None

        exercise_dicts = UserExerciseGraph.exercise_dicts(exercises_allowed)

        user_exercise_graphs = map(
                lambda (user_data, user_exercise_cache): UserExerciseGraph.generate(user_data, user_exercise_cache, exercise_dicts),
                itertools.izip(user_data_list, user_exercise_cache_list))

        # Return list of graphs if a list was passed in,
        # otherwise return single graph
        return user_exercise_graphs if type(user_data_or_list) == list else user_exercise_graphs[0]

    @staticmethod
    def dict_from_exercise(exercise):
        return {
                "id": exercise.key().id(),
                "name": exercise.name,
                "display_name": exercise.display_name,
                "h_position": exercise.h_position,
                "v_position": exercise.v_position,
                "proficient": None,
                "explicitly_proficient": None,
                "suggested": None,
                "prerequisites": map(lambda exercise_name: {"name": exercise_name, "display_name": Exercise.to_display_name(exercise_name)}, exercise.prerequisites),
                "covers": exercise.covers,
                "live": exercise.live,
            }

    @staticmethod
    def exercise_dicts(exercises_allowed=None):
        return map(
                UserExerciseGraph.dict_from_exercise,
                exercises_allowed or Exercise.get_all_use_cache()
        )

    @staticmethod
    def get_and_update(user_data, user_exercise):
        user_exercise_cache = UserExerciseCache.get(user_data)
        user_exercise_cache.update(user_exercise)
        return UserExerciseGraph.generate(user_data, user_exercise_cache, UserExerciseGraph.exercise_dicts())

    @staticmethod
    def get_boundary_names(graph):
        """ Return the names of the exercises that succeed
        the student's proficient exercises.
        """
        all_exercises_dict = {}

        def is_boundary(graph_dict):
            name = graph_dict["name"]

            if name in all_exercises_dict:
                return all_exercises_dict[name]

            # Don't suggest already-proficient exercises
            if graph_dict["proficient"]:
                all_exercises_dict.update({name: False})
                return False

            # First, assume we're suggesting this exercise
            is_suggested = True

            # Don't suggest exercises that are covered by other suggested exercises
            for covering_graph_dict in graph_dict["coverer_dicts"]:
                if is_boundary(covering_graph_dict):
                    all_exercises_dict.update({name: False})
                    return False

            # Don't suggest exercises if the user isn't proficient in all prerequisites
            for prerequisite_graph_dict in graph_dict["prerequisite_dicts"]:
                if not prerequisite_graph_dict["proficient"]:
                    all_exercises_dict.update({name: False})
                    return False

            all_exercises_dict.update({name: True})
            return True

        boundary_graph_dicts = []
        for exercise_name in graph:
            graph_dict = graph[exercise_name]
            if graph_dict["live"] and is_boundary(graph_dict):
                boundary_graph_dicts.append(graph_dict)

        boundary_graph_dicts = sorted(sorted(boundary_graph_dicts,
                             key=lambda graph_dict: graph_dict["v_position"]),
                             key=lambda graph_dict: graph_dict["h_position"])

        return [graph_dict["name"]
                    for graph_dict in boundary_graph_dicts]

    @staticmethod
    def get_attempted_names(graph):
        """ Return the names of the exercises that the student has attempted.

        Exact details, such as the threshold that marks a real attempt
        or the relevance rankings of attempted exercises, TBD.
        """
        progress_threshold = 0.5

        attempted_graph_dicts = filter(
                                    lambda graph_dict:
                                        (graph_dict["progress"] > progress_threshold
                                            and not graph_dict["proficient"]),
                                    graph.values())

        attempted_graph_dicts = sorted(attempted_graph_dicts,
                            reverse=True,
                            key=lambda graph_dict: graph_dict["progress"])

        return [graph_dict["name"] for graph_dict in attempted_graph_dicts]

    @staticmethod
    def mark_suggested(graph):
        """ Mark 5 exercises as suggested, which are used by the knowledge map
        and the profile page.

        Attempted but not proficient exercises are suggested first,
        then padded with exercises just beyond the proficiency boundary.

        TODO: Although exercises might be marked in a particular order,
        they will always be returned by suggested_graph_dicts()
        sorted by knowledge map position. We might want to change that.
        """
        num_to_suggest = 5
        suggested_names = UserExerciseGraph.get_attempted_names(graph)

        if len(suggested_names) < num_to_suggest:
            boundary_names = UserExerciseGraph.get_boundary_names(graph)
            suggested_names.extend(boundary_names)

        suggested_names = suggested_names[:num_to_suggest]

        for exercise_name in graph:
            is_suggested = exercise_name in suggested_names
            graph[exercise_name]["suggested"] = is_suggested

    @staticmethod
    def generate(user_data, user_exercise_cache, exercise_dicts):

        graph = {}

        # Build up base of graph
        for exercise_dict in exercise_dicts:

            user_exercise_dict = user_exercise_cache.user_exercise_dict(exercise_dict["name"])

            graph_dict = {}

            graph_dict.update(user_exercise_dict)
            graph_dict.update(exercise_dict)
            graph_dict.update({
                "coverer_dicts": [],
                "prerequisite_dicts": [],
            })

            # In case user has multiple UserExercise mappings for a specific exercise,
            # always prefer the one w/ more problems done
            if graph_dict["name"] not in graph or graph[graph_dict["name"]]["total_done"] < graph_dict["total_done"]:
                graph[graph_dict["name"]] = graph_dict

        # Cache coverers and prereqs for later
        for graph_dict in graph.values():
            # Cache coverers
            for covered_exercise_name in graph_dict["covers"]:
                covered_graph_dict = graph.get(covered_exercise_name)
                if covered_graph_dict:
                    covered_graph_dict["coverer_dicts"].append(graph_dict)

            # Cache prereqs
            for prerequisite_exercise_name in graph_dict["prerequisites"]:
                prerequisite_graph_dict = graph.get(prerequisite_exercise_name["name"])
                if prerequisite_graph_dict:
                    graph_dict["prerequisite_dicts"].append(prerequisite_graph_dict)

        # Set explicit proficiencies
        for exercise_name in user_data.proficient_exercises:
            graph_dict = graph.get(exercise_name)
            if graph_dict:
                graph_dict["proficient"] = graph_dict["explicitly_proficient"] = True

        # Calculate implicit proficiencies
        def set_implicit_proficiency(graph_dict):
            if graph_dict["proficient"] is not None:
                return graph_dict["proficient"]

            graph_dict["proficient"] = False

            # Consider an exercise implicitly proficient if the user has
            # never missed a problem and a covering ancestor is proficient
            if graph_dict["streak"] == graph_dict["total_done"]:
                for covering_graph_dict in graph_dict["coverer_dicts"]:
                    if set_implicit_proficiency(covering_graph_dict):
                        graph_dict["proficient"] = True
                        break

            return graph_dict["proficient"]

        for exercise_name in graph:
            set_implicit_proficiency(graph[exercise_name])

        # Calculate suggested and reviewing
        UserExerciseGraph.mark_suggested(graph)
        UserExerciseGraph.mark_reviewing(graph)

        return UserExerciseGraph(graph=graph, cache=user_exercise_cache)


class ProblemLog(backup_model.BackupModel):
    """Information about a single user with a single problem in an exercise."""
    user = db.UserProperty()
    user_id = db.StringProperty()  # Stable unique identifying string for a user
    exercise = db.StringProperty()
    correct = db.BooleanProperty(default=False)
    time_done = db.DateTimeProperty(auto_now_add=True)
    time_taken = db.IntegerProperty(default=0, indexed=False)
    hint_time_taken_list = db.ListProperty(int, indexed=False)
    hint_after_attempt_list = db.ListProperty(int, indexed=False)
    count_hints = db.IntegerProperty(default=0, indexed=False)
    problem_number = db.IntegerProperty(default=-1) # Used to reproduce problems
    hint_used = db.BooleanProperty(default=False, indexed=False)
    points_earned = db.IntegerProperty(default=0, indexed=False)
    earned_proficiency = db.BooleanProperty(default=False) # True if proficiency was earned on this problem
    suggested = db.BooleanProperty(default=False) # True if the exercise was suggested to the user

    # True if the problem was done while in review mode
    review_mode = db.BooleanProperty(default=False, indexed=False)

    # True if the problem was done while in context-switching topic mode
    topic_mode = db.BooleanProperty(default=False, indexed=False)

    sha1 = db.StringProperty(indexed=False)
    seed = db.StringProperty(indexed=False)
    problem_type = db.StringProperty(indexed=False)
    count_attempts = db.IntegerProperty(default=0, indexed=False)
    time_taken_attempts = db.ListProperty(int, indexed=False)
    attempts = db.StringListProperty(indexed=False)
    random_float = db.FloatProperty() # Add a random float in [0, 1) for easy random sampling
    ip_address = db.StringProperty(indexed=False)

    @classmethod
    def key_for(cls, user_data, exid, problem_number):
        return "problemlog_%s_%s_%s" % (user_data.key_email, exid,
            problem_number)

    @classmethod
    def from_json(cls, json, user_data, exercise):
        """This method exists for testing convenience only. It's called only
        by code that runs in exclusively in development mode. Do not rely on
        this method in production code. If you need to break this code to
        implement some new feature, feel free!
        """
        problem_number = int(json['problem_number'])
        return cls(
            attempts=json['attempts'],
            correct=bool(json['correct']),
            count_attempts=int(json['count_attempts']),
            count_hints=int(json['count_hints']),
            earned_proficiency=bool(json['earned_proficiency']),
            exercise=exercise.name,
            hint_after_attempt_list=json['hint_after_attempt_list'],
            hint_time_taken_list=json['hint_time_taken_list'],
            hint_used=bool(json['hint_used']),
            ip_address=json['ip_address'],
            key_name=cls.key_for(user_data, exercise.name, problem_number),
            points_earned=int(json['points_earned']),
            problem_number=problem_number,
            problem_type=json['problem_type'],
            random_float=json['random_float'],
            review_mode=bool(json['review_mode']),
            seed=json['seed'],
            sha1=json['sha1'],
            suggested=bool(json['suggested']),
            time_done=util.parse_iso8601(json['time_done']),
            time_taken=int(json['time_taken']),
            time_taken_attempts=json['time_taken_attempts'],
            user=user_data.user,
            user_id=user_data.user_id,
        )

    def put(self):
        if self.random_float is None:
            self.random_float = random.random()
        db.Model.put(self)

    @property
    def ka_url(self):
        return url_util.absolute_url("/exercise/%s?problem_number=%s" % \
            (self.exercise, self.problem_number))

    @staticmethod
    def get_for_user_data_between_dts(user_data, dt_a, dt_b):
        query = ProblemLog.all()
        query.filter('user =', user_data.user)

        query.filter('time_done >=', dt_a)
        query.filter('time_done <', dt_b)

        query.order('time_done')

        return query

    def time_taken_capped_for_reporting(self):
        # For reporting's sake, we cap the amount of time that you can be considered to be
        # working on a single problem at 60 minutes. If you've left your browser open
        # longer, you're probably not actively working on the problem.
        return min(consts.MAX_WORKING_ON_PROBLEM_SECONDS, self.time_taken)

    def time_started(self):
        return self.time_done - datetime.timedelta(seconds=self.time_taken_capped_for_reporting())

    def time_ended(self):
        return self.time_done

    def minutes_spent(self):
        return util.minutes_between(self.time_started(), self.time_ended())

# commit_problem_log is used by our deferred problem log insertion process
def commit_problem_log(problem_log_source, user_data=None, async=True):
    try:
        if not problem_log_source or not problem_log_source.key().name:
            logging.critical("Skipping problem log commit due to missing problem_log_source or key().name")
            return
    except db.NotSavedError:
        # Handle special case during new exercise deploy
        logging.critical("Skipping problem log commit due to db.NotSavedError")
        return

    if problem_log_source.count_attempts > 1000:
        logging.info("Ignoring attempt to write problem log w/ attempts over 1000.")
        return

    #for TinCan
    user_data = user_models.UserData.get_from_user_id(problem_log_source.user_id)
    exercise = Exercise.get_by_name(problem_log_source.exercise)
    if exercise == None:
        logging.error("TinCan: Can't find exercise %s" % problem_log_source.exercise)
    user_exercise = user_data.get_or_insert_exercise(exercise)
    # Committing transaction combines existing problem log with any followup attempts
    def txn():
        problem_log = ProblemLog.get_by_key_name(problem_log_source.key().name())

        if not problem_log:
            problem_log = ProblemLog(
                key_name = problem_log_source.key().name(),
                user = problem_log_source.user,
                user_id = problem_log_source.user_id,
                exercise = problem_log_source.exercise,
                problem_number = problem_log_source.problem_number,
                time_done = problem_log_source.time_done,
                sha1 = problem_log_source.sha1,
                seed = problem_log_source.seed,
                problem_type = problem_log_source.problem_type,
                suggested = problem_log_source.suggested,
                ip_address = problem_log_source.ip_address,
                review_mode = problem_log_source.review_mode,
                topic_mode = problem_log_source.topic_mode,
        )

        problem_log.count_hints = max(problem_log.count_hints, problem_log_source.count_hints)
        problem_log.hint_used = problem_log.count_hints > 0
        index_attempt = max(0, problem_log_source.count_attempts - 1)

        # Bump up attempt count
        if problem_log_source.attempts[0] != "hint": # attempt
            TinCan.create_question(user_data, "answered", exercise, problem_log=problem_log_source)
            if index_attempt < len(problem_log.time_taken_attempts) \
               and problem_log.time_taken_attempts[index_attempt] != -1:
                # This attempt has already been logged. Ignore this dupe taskqueue execution.
                logging.info("Skipping problem log commit due to dupe taskqueue\
                    execution for attempt: %s, key.name: %s" % \
                    (index_attempt, problem_log_source.key().name()))
                return

            problem_log.count_attempts += 1

            # Add time_taken for this individual attempt
            problem_log.time_taken += problem_log_source.time_taken
            util.insert_in_position(index_attempt,
                    problem_log.time_taken_attempts,
                    problem_log_source.time_taken, filler= -1)

            # Add actual attempt content
            util.insert_in_position(index_attempt, problem_log.attempts,
                    problem_log_source.attempts[0], filler="")

            # Proficiency earned should never change per problem
            problem_log.earned_proficiency = problem_log.earned_proficiency or \
                problem_log_source.earned_proficiency

        else: # hint
            TinCan.create_question(user_data, "interacted", exercise, problem_log=problem_log)
            index_hint = max(0, problem_log_source.count_hints - 1)

            if index_hint < len(problem_log.hint_time_taken_list) \
               and problem_log.hint_time_taken_list[index_hint] != -1:
                # This attempt has already been logged. Ignore this dupe taskqueue execution.
                return

            # Add time taken for hint
            util.insert_in_position(index_hint,
                    problem_log.hint_time_taken_list,
                    problem_log_source.time_taken, filler= -1)

            # Add attempt number this hint follows
            util.insert_in_position(index_hint,
                    problem_log.hint_after_attempt_list,
                    problem_log_source.count_attempts, filler= -1)

        # Points should only be earned once per problem, regardless of attempt count
        problem_log.points_earned = max(problem_log.points_earned, problem_log_source.points_earned)

        # Correct cannot be changed from False to True after first attempt
        problem_log.correct = (problem_log_source.count_attempts == 1 or problem_log.correct) and problem_log_source.correct and not problem_log.count_hints


        # Only send progressed and completed events when exercise is not proficient and answer has been correct
        if hasattr(problem_log_source, "explicitly_proficient") and \
            not getattr(problem_log_source, "explicitly_proficient"):
            if hasattr(problem_log_source, "completed") and getattr(problem_log_source, "completed"):
                TinCan.create_question(user_data, "progressed", exercise, user_exercise=user_exercise)
            if user_exercise.progress >= 1.0:
                TinCan.create_question(user_data, "completed", exercise, problem_log=problem_log)


        logging.info(problem_log.time_ended())
        problem_log.put()

    #for testing purposes
    if async:
        db.run_in_transaction(txn)
    else:
        txn()


# TODO(david): Tests. See how problem logs are tested.
class StackLog(backup_model.BackupModel):
    """Information about a single user's stack in Power Mode (exercises)."""
    user_id = db.StringProperty()
    finished = db.BooleanProperty(default=False)
    time_started = db.DateTimeProperty(auto_now_add=True, indexed=False)
    time_last_done = db.DateTimeProperty(indexed=False)  # Avoiding auto_now due to its unpredictable magic
    cards_left = db.IntegerProperty(default=stacks.DEFAULT_CARDS_PER_STACK, indexed=False)

    # True if the problem was done while in review mode
    review_mode = db.BooleanProperty(default=False)

    # True if the problem was done while in context-switching topic mode
    topic_mode = db.BooleanProperty(default=False)

    # This will only be valid in practice (single-exercise) mode
    exercise_id = db.StringProperty(default="")

    # This value is not valid in review mode (which presents a mix of proficient
    # exercises to review)
    topic_id = db.StringProperty(default="")

    # TODO(david): Could make this double-serialized (eg. jsonify the
    #     elements) if performance is desired.
    cards_list = object_property.JsonProperty()

    # Somewhere to stick arbitrary data. Example uses: A/B test data,
    # review-mode specific information.
    extra_data = object_property.JsonProperty()

    @staticmethod
    def key_for(user_id, stack_uid):
        return "stacklog_%s_%s" % (user_id, stack_uid)

    # TODO(david): Not needed right now, get rid of this and property indices?
    @staticmethod
    def get_unfinished(user_id, topic_mode, review_mode, exercise_id, topic_id):
        """Query for an unfinished (in-progress) stack."""
        query = StackLog.all()
        query = query.filter('finished = ', False)
        query = query.filter('user_id = ', user_id)

        if topic_mode:
            # There should only be one unfinished stack per topic
            query = query.filter('topic_id = ', topic_id)
            query = query.filter('topic_mode = ', True)
        elif review_mode:
            query = query.filter('review_mode = ', True)
        else:
            # Practice mode, so stack is exercise-specific
            query = query.filter('exercise_id = ', exercise_id)

        return query.get()

def commit_stack_log(stack_log_source, card, cards_done, cards_left,
        associated_log_type, associated_log_key):
    """Create a stack log or find the corresponding existing log and update it,
    then save in the datastore.

    associated_log is the log related to the activity performed for this card.
    Currently, it's just the associated ProblemLog for this card, but could
    possibly include VideoLog in the future.
    """
    def txn():
        stack_log = StackLog.get(stack_log_source.key())
        if stack_log is None:
            stack_log = stack_log_source

        # Update the stack log with information from this card
        if cards_left == 0:
            stack_log.finished = True
        stack_log.time_last_done = max(stack_log_source.time_last_done,
                stack_log.time_last_done)
        stack_log.cards_left = min(cards_left, stack_log.cards_left)

        if stack_log_source.topic_mode:
            stack_log.extra_data.setdefault('topic_mode', {})
            util.update_dict_with(stack_log.extra_data['topic_mode'],
                    stack_log_source.extra_data.get('topic_mode', {}),
                    { 'count_proficient': max, 'just_completed': max })

        # Add associated log key (eg. ProblemLog) and the card info sent from
        # the client at the right position in the list of cards
        card_info = {
            'card': card,
            'associated_log': {
                associated_log_type: str(associated_log_key)
            }
        }
        util.insert_in_position(cards_done, stack_log.cards_list, card_info, {})

        stack_log.put()

    db.run_in_transaction(txn)

