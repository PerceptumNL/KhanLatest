from __future__ import absolute_import
import datetime

from google.appengine.api import users

from app import App
import request_handler
import user_util
from dashboard.models import DailyStatistic, EntityStatistic
from google.appengine.ext.db import stats
from itertools import groupby
import topic_models
import exercise_models
import url_model
import video_models


class Dashboard(request_handler.RequestHandler):
    """
    Handles request to show the main internal dashboard.
    
    Shows graphs for particular entity counts which may be specified as
    a comma separated URL parameter called "kinds".
    
    """

    DEFAULT_KINDS = ','.join([
            'RegisteredUser',
            'ProblemLog',
    ])

    @user_util.manual_access_checking
    def get(self):
        if not user_util.is_current_user_developer():
            if (App.dashboard_secret and
                    (self.request_string("x", default=None) !=
                     App.dashboard_secret)):
                self.redirect(users.create_login_url(self.request.uri))
                return

        kinds = self.request_string("kinds", Dashboard.DEFAULT_KINDS).split(',')

        graphs = []
        for kind in kinds:
            d = daily_graph_context(EntityStatistic(kind), "data")
            d['kind_name'] = kind
            d['title'] = "%s created per day" % kind
            graphs.append(d)

        self.render_jinja2_template("dashboard/dashboard.html", {'graphs': graphs})


def daily_graph_context(cls, key):
    # Grab last ~4 months
    counts = cls.all().order("-dt").fetch(31 * 4)

    # Flip 'em around
    counts.reverse()

    # Grab deltas
    count_last = None
    for count in counts:
        if count_last:
            count.delta = count.val - count_last.val

        # Better to show date previous to date stat recorded.
        count.dt_display = count.dt - datetime.timedelta(days=1)
        count.js_month = count.dt_display.month - 1
        count_last = count

    return {key: filter(lambda count: hasattr(count, "delta"), counts)}


class RecordStatistics(request_handler.RequestHandler):
    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def get(self):
        return self.post()

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def post(self):
        DailyStatistic.record_all()
        self.response.out.write("Dashboard statistics recorded.")


class EntityCounts(request_handler.RequestHandler):
    @user_util.developer_required
    def get(self):
        kind_stats = [s for s in stats.KindStat.all().fetch(1000)]

        counts = []
        kind_stats.sort(key=lambda s: s.kind_name)
        for key, group in groupby(kind_stats, lambda s: s.kind_name):
            grouped = sorted(group, key=lambda s: s.timestamp, reverse=True)
            counts.append(dict(kind=key, count=grouped[0].count, timestamp=grouped[0].timestamp))

        self.render_jinja2_template("dashboard/entitycounts.html", {'counts': counts})
        

class ContentCountsCSV(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):
        root = topic_models.Topic.get_root()
        tree = root.make_tree()

        def stats(tree, parent):
            title = (tree.title 
                     if parent.id not in topic_models.Topic._super_topic_ids 
                     else parent.title + " : " + tree.title)

            topic_stats = {"title": title,
                           "descendant_video_count": 0,
                           "descendant_exercise_count": 0,
                           "unique_video_count": 0,
                           "unique_exercise_count": 0, 
                           "video_count": 0,
                           "exercise_count": 0,
                           "video_keys": set(),
                           "exercise_keys": set(),
                           "subtopics": []}

            for child in tree.children:
                if type(child) == topic_models.Topic:
                    subtopic_stats = stats(child, tree)
                    topic_stats["video_keys"].update(subtopic_stats["video_keys"])
                    topic_stats["exercise_keys"].update(subtopic_stats["exercise_keys"])
                    topic_stats["subtopics"].append(subtopic_stats)
                    topic_stats["descendant_video_count"] += \
                        subtopic_stats["descendant_video_count"]
                    topic_stats["descendant_exercise_count"] += \
                        subtopic_stats["descendant_exercise_count"]
                                    
                elif type(child) == exercise_models.Exercise and child.live:
                    topic_stats["exercise_keys"].add(child.key())
                    topic_stats["exercise_count"] += 1
                    topic_stats["descendant_exercise_count"] += 1

                elif type(child) == video_models.Video or type(child) == url_model.Url:
                    topic_stats["video_keys"].add((
                        child.key(), 
                        child.views if hasattr(child, "views") else 0))
                    topic_stats["video_count"] += 1
                    topic_stats["descendant_video_count"] += 1

            topic_stats["unique_video_count"] = ( 
                len(topic_stats["video_keys"]))

            topic_stats["view_count"] = (
                sum(map(lambda i: i[1], topic_stats["video_keys"])))

            topic_stats["unique_exercise_count"] = (
                len(topic_stats["exercise_keys"]))

            return topic_stats

        def flatten_stats(stats, topics=None):
            if topics == None:
                topics = []

            topics.append(stats)
            for child in stats["subtopics"]:
                topics += flatten_stats(child)

            del stats["subtopics"]
            return topics

        stats = stats(tree, tree)

        self.response.headers['Content-Type'] = "text/csv"
        self.response.out.write("%s, %s, %s, %s, %s, %s, %s, %s\n" % (
            "Title",
            "Videos in or under Topics",
            "Unique Videos in or under Topic",
            "Videos in Topic",
            "Number of Video Views in or under Topic",
            "Exercises in or under Topic",
            "Unique Exercises in or under Topic",
            "Exercises in Topic"
        ))
        
        for stats in flatten_stats(stats):
            self.response.out.write("%s, %i, %i, %i, %i, %i, %i, %i\n" % (
                stats["title"],
                stats["descendant_video_count"],
                stats["unique_video_count"],
                stats["video_count"], 
                stats["view_count"], 
                stats["descendant_exercise_count"], 
                stats["unique_exercise_count"],
                stats["exercise_count"]
                ))
