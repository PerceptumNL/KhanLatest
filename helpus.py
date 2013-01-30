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
    root = topic_models.Topic.get_root(version).make_tree([], False)
    exercises = exercise_models.Exercise.all().fetch(1000)

    def children_recursive(current, ex_list=None, topics=[]):
        current['topics'] = topics[1:]
        if current['kind'] == "Topic":
            topics.append(current['title'])
            for node in current['children']:
                children_recursive(node, ex_list, list(topics))
        elif current['kind'] == "Exercise":
            try:
                exercise = next(i for i in exercises if i.name == current['name'])
                current['video_requests_count'] = exercise.video_requests_count
                if len(current['related_video_readable_ids']) == 0:
                    ex_list.append(current)
            except StopIteration:
                logging.info("Exercise from topic tree '%s' couldn't be found" % current['name'])
                pass

        return ex_list

    return children_recursive(jsonify.dumps(root), [], [])


class ViewMissingVideos(request_handler.RequestHandler):

    @user_util.open_access
    def get(self):
        template_values = {'rows' : get_videoless_exercises() }
        self.render_jinja2_template('missingvideos.html', template_values)

