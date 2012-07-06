"""Holds DailyActivityLog, LogSummaryShardConfig, and LogSummary.

These database entities hold summary information related to a user.
VideoLog and ProblemLog show more specific information (for
video-watching and exercise-doing, respectively) and live in
video_models.py and exercise_models.py.

DailyActivityLog: points/exercises won per day, to show in the profile.
   James: this could have been a LogSummary type but was made before
   LogSummary existed.
LogSummaryShardConfig: Tracks the number of shards for each named log summary.
LogSummary: Keeps a variety of different types of summaries pulled
   from the logs.
"""

import datetime
import logging
import random

from google.appengine.ext import db

import object_property


class DailyActivityLog(db.Model):
    """ A log entry for a dashboard presented to users and coaches.

    This is used in the end-user-visible dashboards that display
    student activity and breaks down where the user is spending her time.
    """

    user = db.UserProperty()
    date = db.DateTimeProperty()

    # TODO(benkomalo): This pickles models and is fragile to breakage!
    # If the ClassDailyActivity class signature changes or moves
    # modules, this could break.
    activity_summary = object_property.ObjectProperty()

    @staticmethod
    def get_key_name(user_data, date):
        return "%s:%s" % (user_data.key_email, date.strftime("%Y-%m-%d-%H"))

    @staticmethod
    def build(user_data, date, activity_summary):
        log = DailyActivityLog(key_name=DailyActivityLog.get_key_name(user_data, date))
        log.user = user_data.user
        log.date = date
        log.activity_summary = activity_summary
        return log

    @staticmethod
    def get_for_user_data_between_dts(user_data, dt_a, dt_b):
        query = DailyActivityLog.all()
        query.filter('user =', user_data.user)

        query.filter('date >=', dt_a)
        query.filter('date <', dt_b)
        query.order('date')

        return query


class LogSummaryTypes:
    USER_ADJACENT_ACTIVITY = "UserAdjacentActivity"
    CLASS_DAILY_ACTIVITY = "ClassDailyActivity"


class LogSummaryShardConfig(db.Model):
    """Tracks the number of shards for each named log summary."""
    name = db.StringProperty(required=True)
    num_shards = db.IntegerProperty(required=True, default=1)

    @staticmethod
    def increase_shards(name, num):
        """Increase the number of shards for a given sharded counter.
        Will never decrease the number of shards.

        Parameters:
        name - The name of the counter
        num - How many shards to use

        """
        config = LogSummaryShardConfig.get_or_insert(name, name=name)

        def txn():
            if config.num_shards < num:
                config.num_shards = num
                config.put()

        db.run_in_transaction(txn)


class LogSummary(db.Model):
    """Keeps a variety of different types of summaries pulled from the logs."""
    user = db.UserProperty()
    start = db.DateTimeProperty()
    end = db.DateTimeProperty()
    summary_type = db.StringProperty()

    # TODO(benkomalo): This pickles models and is fragile to breakage!
    # If the ClassDailyActivity class signature changes or moves
    # modules, this could break.
    summary = object_property.UnvalidatedObjectProperty()
    name = db.StringProperty(required=True)

    @staticmethod
    def get_start_of_period(activity, delta):
        date = activity.time_started()

        if delta == 1440:
            return datetime.datetime(date.year, date.month, date.day)

        if delta == 60:
            return datetime.datetime(date.year, date.month, date.day, date.hour)

        raise Exception("unhandled delta to get_key_name")

    @staticmethod
    def get_end_of_period(activity, delta):
        return LogSummary.get_start_of_period(activity, delta) + datetime.timedelta(minutes=delta)

    @staticmethod
    def get_name(user_data, summary_type, activity, delta):
        return LogSummary.get_name_by_dates(
            user_data,
            summary_type,
            LogSummary.get_start_of_period(activity, delta),
            LogSummary.get_end_of_period(activity, delta))

    @staticmethod
    def get_name_by_dates(user_data, summary_type, start, end):
        return "%s:%s:%s:%s" % (user_data.key_email, summary_type,
                                start.strftime("%Y-%m-%d-%H-%M"),
                                end.strftime("%Y-%m-%d-%H-%M"))

    # activity needs to have activity.time_started() and activity.time_done() functions
    # summary_class needs to have a method .add(activity)
    # delta is a time period in minutes
    @staticmethod
    def add_or_update_entry(user_data, activity, summary_class, summary_type, delta=30):

        if user_data is None:
            return

        def txn(name, shard_name, user_data, activities, summary_class, summary_type, delta):
                log_summary = LogSummary.get_by_key_name(shard_name)

                if log_summary is None:
                    activity = activities[0]

                    log_summary = LogSummary(
                        key_name=shard_name,
                        name=name,
                        user=user_data.user,
                        start=LogSummary.get_start_of_period(activity, delta),
                        end=LogSummary.get_end_of_period(activity, delta),
                        summary_type=summary_type)

                    log_summary.summary = summary_class()

                for activity in activities:
                    log_summary.summary.add(user_data, activity)

                log_summary.put()

        # if activities is a list, we assume all activities belong to
        # the same period
        if type(activity) == list:
            activities = activity
            activity = activities[0]
        else:
            activities = [activity]

        name = LogSummary.get_name(user_data, summary_type, activity, delta)
        config = LogSummaryShardConfig.get_or_insert(name, name=name)

        index = random.randrange(config.num_shards)
        shard_name = str(index) + ":" + name

        # running function within a transaction because time might
        # elapse between the get and the put and two processes could
        # get before either puts. Transactions will ensure that its
        # mutually exclusive since they are operating on the same
        # entity
        try:
            db.run_in_transaction(txn, name, shard_name, user_data, activities,
                                  summary_class, summary_type, delta)
        except db.TransactionFailedError:
            # if it is a transaction lock
            logging.info("increasing the number of shards to %i log summary: %s" %
                         (config.num_shards + 1, name))
            LogSummaryShardConfig.increase_shards(name, config.num_shards + 1)
            shard_name = str(config.num_shards) + ":" + name
            db.run_in_transaction(txn, name, shard_name, user_data, activities,
                                  summary_class, summary_type, delta)

    @staticmethod
    def get_by_name(name):
        query = LogSummary.all()
        query.filter('name =', name)
        return query
