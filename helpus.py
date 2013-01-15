import datetime
import random

from jinja2.utils import escape

import exercise_models
import library
import request_handler
import user_util
import user_models
import video_models
import layer_cache
import setting_model
import templatetags
import topic_models
from app import App
from topics_list import DVD_list
from api.auth.xsrf import ensure_xsrf_cookie
from api import jsonify
import logging


def get_videoless_exercises():
    version = topic_models.TopicVersion.get_latest_version()
    root = topic_models.Topic.get_root(version).make_tree()
    def children_recursive(current, ex_list=None, topics=[]):
        current['topics'] = topics
        if current['kind'] == "Topic":
            topics.append(current['title'])
            for node in current['children']:
                children_recursive(node, ex_list, list(topics))
        elif current['kind'] == "Exercise":
            if len(current['related_video_readable_ids']) == 0:
                ex_list.append(current)
        current['topics'] = " > ".join(current['topics'])
        return ex_list

    exercises = children_recursive(jsonify.dumps(root), [], [])
    return exercises


class ViewMissingVideos(request_handler.RequestHandler):

    @user_util.open_access
    def head(self):
        # Respond to HEAD requests for our homepage so twitter's tweet
        # counter will update:
        # https://dev.twitter.com/docs/tweet-button/faq#count-api-increment
        pass

    # See https://sites.google.com/a/khanacademy.org/forge/for-team-members/how-to-use-new-and-noteworthy-content
    # for info on how to update the New & Noteworthy videos
    @user_util.open_access
    @ensure_xsrf_cookie    # TODO(csilvers): remove this (test w/ autocomplete)
    def get(self):

        #topics = jsonify.dumps(tree)['children']
        #for topic in topics:
        #    template_values = {'tree'}
        #exs = exercise_models.Exercise().all().fetch(20)
        template_values = {'rows' : get_videoless_exercises() }
        self.render_jinja2_template('missingvideos.html', template_values)

