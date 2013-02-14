import os
import datetime
import logging
from itertools import izip
# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

from google.appengine.api import memcache
from third_party.flask import request

import app
import custom_exceptions
import backup_model
import exercise_models
import facebook
import facebook_util
import promo_record_model
import setting_model
import topic_models
import url_model
import video_models
import layer_cache
import templatetags  # Must be imported to register template tags
import exercises.exercise_util
import exercises.stacks
from api.auth import facebook_utils
from avatars import util_avatars
from badges import badges, util_badges, models_badges, profile_badges
from phantom_users.templatetags import login_notifications_html
from phantom_users.phantom_util import api_create_phantom
from discussion import moderation
from discussion import qa
from discussion import voting
from discussion import discussion_models
import notifications
import user_models
import coaches
import gae_bingo.gae_bingo
from autocomplete import video_title_dicts, topic_title_dicts, url_title_dicts
from goals.models import (GoalList, Goal, GoalObjective,
    GoalObjectiveAnyExerciseProficiency, GoalObjectiveAnyVideo)
import profiles.util_profile as util_profile
from profiles import (class_progress_report_graph, recent_activity,
                      suggested_activity)
from knowledgemap.layout import MapLayout
from common_core.models import CommonCoreMap
from youtube_sync import youtube_get_video_data_dict, youtube_get_video_data

from api.route_decorator import route
from api import v1_utils
from api.decorators import jsonify, jsonp, pickle, etag,\
    cacheable, cache_with_key_fxn_and_param
import api.auth.decorators
from api.auth.auth_util import unauthorized_response
from api.api_util import (api_created_response, api_error_response,
                        api_invalid_param_response, api_unauthorized_response,
                        api_opengraph_error_response)

from google.appengine.ext import db, deferred


# add_action_results allows page-specific updatable info to be ferried
# along otherwise plain-jane responses
#
# case in point: /api/v1/user/videos/<youtube_id>/log which adds in
# user-specific video progress info to the response so that we can
# visibly award badges while the page silently posts log info in the
# background.
#
# If you're wondering how this happens, it's add_action_results has
# the side-effect of actually mutating the `obj` passed into it (but,
# i mean, that's what you want here)
#
# but you ask, what matter of client-side code actually takes care of
# doing that?  have you seen javascript/shared-package/api.js ?
def add_action_results(obj, dict_results):

    user_data = user_models.UserData.current()

    if user_data:
        dict_results["user_data"] = user_data

        dict_results["user_info_html"] = templatetags.user_info(user_data,
                # Use ajax referrer, if we have it, for post-login continue url
                continue_url=request.referrer)

        notifications_dict = notifications.Notifier.pop()

        # Add any new badge notifications
        badge_names = [n.badge_name for n in notifications_dict["badges"]]
        if len(badge_names) > 0:
            dict_results["badges_earned"] = {
                    "badges": util_badges.get_badges(badge_names)}

        # Add any new login notifications for phantom users
        phantom_text = [n.text for n in notifications_dict["phantoms"]]
        if len(phantom_text) > 0:
            dict_results["login_notifications_html"] = (
                login_notifications_html(phantom_text[0], user_data))

    if type(obj) == dict:
        obj['action_results'] = dict_results
    else:
        obj.action_results = dict_results


# Return specific user data requests from request
# IFF currently logged in user has permission to view
def get_visible_user_data_from_request(disable_coach_visibility=False,
                                       user_data=None):
    """Return the current user based on the request params, if the actor
    has permissions to view info about that user.

    This will default to the current user, or the user specified in user_data.
    """

    user_data = user_data or user_models.UserData.current()
    if not user_data:
        return None

    user_data_student = request.request_student_user_data()
    if user_data_student:
        if user_data_student.user_email == user_data.user_email:
            # if email in request is that of the current user, simply
            # return the current user_data, no need to check
            # permission to view
            return user_data

        if (user_data.developer or
                (not disable_coach_visibility and
                 (user_data_student.is_coached_by(user_data) or
                  user_data_student.is_coached_by_coworker_of_coach(user_data)
                  ))):
            return user_data_student
        else:
            return None

    else:
        return user_data


def get_user_data_coach_from_request():
    user_data_coach = user_models.UserData.current()
    user_data_override = request.request_user_data("coach_email")

    if (user_data_override and
            user_data_coach and
            (user_data_coach.developer or
             user_data_coach.is_coworker_of(user_data_override))):
        user_data_coach = user_data_override

    return user_data_coach


@route("/api/v1/topicversion/<version_id>/topics/with_content",
       methods=["GET"])
@route("/api/v1/topics/with_content", methods=["GET"])
@route("/api/v1/playlists", methods=["GET"])  # missing "url" and "youtube_id"
                                              # properties that they had before
@api.auth.decorators.open_access
@jsonp
@cache_with_key_fxn_and_param(
    "casing",
    lambda version_id=None:
        "api_content_topics_%s_%s" %
        (version_id, setting_model.Setting.topic_tree_version()),
    layer=layer_cache.Layers.Memcache)
@jsonify
def content_topics(version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    return topic_models.Topic.get_content_topics(version)


# private api call used only by ajax homepage ... can remove once we
# remake the homepage with the topic tree
@route("/api/v1/topics/library/compact", methods=["GET"])
@api.auth.decorators.open_access
@cacheable(caching_age=(60 * 60 * 24 * 60))
@etag(lambda: setting_model.Setting.topic_tree_version())
@jsonp
@layer_cache.cache_with_key_fxn(
    lambda: "api_topics_library_compact_%s" %
            setting_model.Setting.topic_tree_version(),
    layer=layer_cache.Layers.Memcache)
@jsonify
def topics_library_compact():
    topics = topic_models.Topic.get_filled_content_topics(types=["Video",
                                                                 "Url"])

    def trimmed_item(item, topic):
        trimmed_item_dict = {}
        if item.kind() == "Video":
            trimmed_item_dict['url'] = "/%s/v/%s" % (topic.get_extended_slug(),
                                                     item.readable_id)
            trimmed_item_dict['key_id'] = item.key().id()
        elif item.kind() == "Url":
            trimmed_item_dict['url'] = item.url
        trimmed_item_dict['title'] = item.title
        return trimmed_item_dict

    topic_dict = {}
    for topic in topics:
        # special cases
        if ((topic.id == "new-and-noteworthy") or
            (topic.standalone_title == "California Standards Test: Geometry"
             and topic.id != "geometry-2")):
            continue

        trimmed_info = {}
        trimmed_info['id'] = topic.id
        trimmed_info['children'] = [trimmed_item(v, topic)
                                    for v in topic.children]
        topic_dict[topic.id] = trimmed_info

    return topic_dict


@route("/api/v1/topicversion/<version_id>/changelist", methods=["GET"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def topic_version_change_list(version_id):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    changes = (topic_models.VersionContentChange.all().
               filter("version =", version).fetch(10000))

    # add the related_video_readable_ids of ExerciseVideos to the
    # change.content
    exercise_dict = dict((change.content.key(), change.content)
                         for change in changes
                         if type(change.content) == exercise_models.Exercise)
    exercise_models.Exercise.add_related_video_readable_ids_prop(exercise_dict)

    return changes


@route("/api/v1/topicversion/<version_id>/deletechange", methods=["POST"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def topic_version_delete_change(version_id):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)

    kind = request.request_string("kind")
    id = request.request_string("id")

    content = get_content_entity(kind, id, version)
    if content:
        query = topic_models.VersionContentChange.all()
        query.filter("version =", version)
        query.filter("content =", content)
        change = query.get()

        if change:
            change.delete()
            return True

    return False


@route("/api/v1/topicversion/<version_id>/topic/<topic_id>/videos",
       methods=["GET"])
@route("/api/v1/topic/<topic_id>/videos", methods=["GET"])
@route("/api/v1/playlists/<topic_id>/videos", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@cache_with_key_fxn_and_param(
    "casing",
    (lambda topic_id, version_id=None: "api_topic_videos_%s_%s_%s" % (
        topic_id,
        version_id,
        setting_model.Setting.topic_tree_version())
        if version_id is None or version_id == "default" else None),
    layer=layer_cache.Layers.Memcache)
@jsonify
def topic_videos(topic_id, version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    topic = topic_models.Topic.get_by_id(topic_id, version)
    if topic is None:
        # needed for people who were using the playlists api
        topic = topic_models.Topic.get_by_title(topic_id, version)
        if topic is None:
            return api_invalid_param_response(
                "Could not find topic with ID %s" % topic_id)

    videos = topic_models.Topic.get_cached_videos_for_topic(topic, False,
                                                            version)
    for i, video in enumerate(videos):
        video.position = i + 1
    return videos


@route("/api/v1/topicversion/<version_id>/topic/<topic_id>/exercises",
       methods=["GET"])
@route("/api/v1/topic/<topic_id>/exercises", methods=["GET"])
@route("/api/v1/playlists/<topic_id>/exercises", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@cache_with_key_fxn_and_param(
    "casing",
    (lambda topic_id, version_id=None: "api_topic_exercises_%s_%s_%s" % (
        topic_id, version_id, setting_model.Setting.topic_tree_version())
        if version_id is None or version_id == "default" else None),
    layer=layer_cache.Layers.Memcache)
@jsonify
def topic_exercises(topic_id, version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    topic = topic_models.Topic.get_by_id(topic_id, version)
    if topic is None:
        # needed for people who were using the playlists api
        topic = topic_models.Topic.get_by_title(topic_id, version)
        if topic is None:
            return api_invalid_param_response(
                "Could not find topic with ID %s" % topic_id)

    exercises = topic.get_exercises()
    return exercises


@route("/api/v1/topic/<topic_id>/progress", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def topic_progress(topic_id):
    user_data = user_models.UserData.current()
    if not user_data:
        user_data = user_models.UserData.pre_phantom()

    topic = topic_models.Topic.get_by_id(topic_id)
    if not topic:
        raise ValueError("Invalid topic id.")

    return topic.get_user_progress(user_data)


@route("/api/v1/topicversion/<version_id>/topictree", methods=["GET"])
@route("/api/v1/topictree", methods=["GET"])
@api.auth.decorators.open_access
@etag(lambda version_id=None: version_id)
@jsonp
@layer_cache.cache_with_key_fxn(
    (lambda version_id=None: "api_topictree_%s_%s" % (version_id,
        setting_model.Setting.topic_tree_version())
        if version_id is None or version_id == "default" else None),
    layer=layer_cache.Layers.Memcache)
@jsonify
def topictree(version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    return topic_models.Topic.get_by_id("root", version).make_tree()


@route("/api/v1/dev/topictree/problems", methods=["GET"])
# TODO(james): change to @developer_required once Tom creates interface
@api.auth.decorators.open_access
@jsonp
@jsonify
def topic_tree_problems(version_id="edit"):
    return layer_cache.KeyValueCache.get(
        "set_default_version_content_problem_details")


@route("/api/v1/dev/topicversion/<version_id>/topic/<topic_id>/topictree",
       methods=["GET"])
@route("/api/v1/dev/topicversion/<version_id>/topictree", methods=["GET"])
@route("/api/v1/dev/topictree", methods=["GET"])
@api.auth.decorators.developer_required
@jsonp
@layer_cache.cache_with_key_fxn(
    (lambda version_id=None, topic_id="root": "api_topictree_export_%s_%s" % (
        version_id,
        setting_model.Setting.topic_tree_version())
        if version_id is None or version_id == "default" else None),
    layer=layer_cache.Layers.Memcache)
@jsonify
def topictree_export(version_id=None, topic_id="root"):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    topic = topic_models.Topic.get_by_id(topic_id, version)
    if topic is None:
        return api_invalid_param_response("Could not find topic-id %s "
                                          "for version_id %s"
                                          % (topic_id, version_id))
    return topic.make_tree(include_hidden=True)


@route("/api/v1/dev/topicversion/<version_id>/topic/<topic_id>/topictree",
       methods=["PUT"])
@route("/api/v1/dev/topicversion/<version_id>/topictree", methods=["PUT"])
@route("/api/v1/dev/topictree/init/<publish>", methods=["PUT"])
@route("/api/v1/dev/topictree", methods=["PUT"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def topictree_import(version_id="edit", topic_id="root", publish=False):
    import zlib
    import pickle_util
    logging.info("calling /_ah/queue/deferred_import")

    # importing the full topic tree can be too large so pickling and
    # compressing
    deferred.defer(v1_utils.topictree_import_task, version_id, topic_id,
                   publish,
                   zlib.compress(pickle_util.dump(request.json)),
                   _queue="import-queue",
                   _url="/_ah/queue/deferred_import")


@route("/api/v1/topicversion/<version_id>/search/<query>", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def topictreesearch(version_id, query):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    return topic_models.Topic.get_by_id("root", version).search_tree(query)


@route("/api/v1/topicversion/<version_id>/topic/<topic_id>", methods=["GET"])
@route("/api/v1/topic/<topic_id>", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@layer_cache.cache_with_key_fxn(
    (lambda topic_id, version_id=None: ("api_topic_%s_%s_%s" % (
        topic_id,
        version_id,
        setting_model.Setting.topic_tree_version())
        if version_id is None or version_id == "default" else None)),
    layer=layer_cache.Layers.Memcache)
@jsonify
def topic(topic_id, version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    topic = topic_models.Topic.get_by_id(topic_id, version)

    if not topic:
        return api_invalid_param_response("Could not find topic with ID %s" %
                                          topic_id)

    return topic.get_visible_data()


@route("/api/v1/topicversion/<version_id>/topic/<topic_id>", methods=["PUT"])
@route("/api/v1/topic/<topic_id>", methods=["PUT"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def put_topic(topic_id, version_id="edit"):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)

    topic_json = request.json

    topic = topic_models.Topic.get_by_id(topic_id, version)

    if not topic:
        kwargs = dict((str(key), value)
                      for key, value in topic_json.iteritems()
                      if key in ['standalone_title', 'description', 'tags'])
        kwargs["version"] = version
        topic = topic_models.Topic.insert(title=topic_json['title'],
                                          parent=None, **kwargs)
    else:
        kwargs = dict((str(key), value)
                      for key, value in topic_json.iteritems()
                      if key in ['id', 'title', 'standalone_title',
                                 'description', 'tags', 'hide', 'x', 'y', 'icon_name'])
        kwargs["version"] = version
        topic.update(**kwargs)
        topic.get_extended_slug(bust_cache=True)

    return {
        "id": topic.id
    }


# Note on @etag: we don't want to set the etag if the topic-version is
# the current edit-version, since that can change without warning.
# Unfortunately, it's slow to check if version_id is the current
# edit-version or not.  Instead we do the fast check of whether
# version_id is None (None == active version which is never the
# edit-version).  We disable etag caching in all other cases by having
# the etag functor return None.
@route("/api/v1/topicversion/<version_id>/topic/<topic_id>/topic-page",
       methods=["GET"])
@route("/api/v1/topic/<topic_id>/topic-page", methods=["GET"])
@api.auth.decorators.open_access
@cacheable(caching_age=(60 * 60 * 24 * 60))
@etag(lambda topic_id, version_id=None:
      "%s_v%s" % (topic_id, setting_model.Setting.topic_tree_version())
      if version_id is None else None)
@jsonp
def get_topic_page_data(topic_id, version_id="default"):
    """ Retrieve the listing of subtopics and videos for this topic.
        Used on the topic page. """
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)

    topic = topic_models.Topic.get_by_id(topic_id, version)

    if not topic:
        return u"{}"

    return topic.get_topic_page_json()


@route("/api/v1/topicversion/<version_id>/maplayout", methods=["GET"])
@route("/api/v1/maplayout", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_maplayout(version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    logging.info("get maplayout:" + str(version.number))
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    return MapLayout.get_for_version(version).layout


@route("/api/v1/topicversion/<version_id>/maplayout", methods=["PUT"])
@route("/api/v1/maplayout", methods=["PUT"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def put_maplayout(version_id="edit"):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)

    map_layout = MapLayout.get_for_version(version)

    topics = topic_models.Topic.get_all_topics(version, True)
    updated_topics = []
    for request_topic in request.json['topics'].values():
        logging.info(request_topic)
        #TODO: update by id instead of display_name to avoid possible conflicts
        #needs to hold the id of the topic in the Map Layout layout version.
        topic = next(i for i in topics if i.standalone_title == request_topic['standalone_title'])
        topic.h_position = int(request_topic['x'])
        topic.v_position = int(request_topic['y'])
        updated_topics.append(topic)

    db.put(updated_topics)

    map_layout.layout = request.json
    map_layout.put()

    return {"id": map_layout.id}


@route("/api/v1/topicversion/default/id", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_default_topic_version_id():
    default_version = topic_models.TopicVersion.get_default_version()
    return default_version.number if default_version else None


@route("/api/v1/dev/task_message", methods=["GET"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def get_topic_admin_task_message():
    return setting_model.Setting.topic_admin_task_message()


def topic_find_child(parent_id, version_id, kind, id):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)

    parent_topic = topic_models.Topic.get_by_id(parent_id, version)
    if not parent_topic:
        return ["Could not find topic with ID %s" % str(parent_id),
                None, None, None]

    child = get_content_entity(kind, id, version)
    if child == "Invalid kind":
        return ["Invalid kind: %s" % kind, None, None, None]

    if not child:
        return ["Could not find a %s with ID %s " % (kind, id),
                None, None, None]

    return [None, child, parent_topic, version]


def get_content_entity(kind, id, version):
    if kind == "Topic":
        return topic_models.Topic.get_by_id(id, version)
    elif kind == "Exercise":
        return exercise_models.Exercise.get_by_name(id, version)
    elif kind == "Video":
        return video_models.Video.get_for_readable_id(id, version)
    elif kind == "Url":
        return url_model.Url.get_by_id_for_version(int(id), version)
    else:
        return "Invalid kind"


@route("/api/v1/topicversion/<version_id>/topic/<parent_id>/addchild",
       methods=["POST"])
@route("/api/v1/topic/<parent_id>/addchild", methods=["POST"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def topic_add_child(parent_id, version_id="edit"):
    kind = request.request_string("kind")
    id = request.request_string("id")

    [error, child, parent_topic, _] = topic_find_child(parent_id, version_id,
                                                       kind, id)
    if error:
        return api_invalid_param_response(error)

    pos = request.request_int("pos", default=0)

    parent_topic.add_child(child, pos)

    return parent_topic.get_visible_data()


@route("/api/v1/topicversion/<version_id>/topic/<parent_id>/deletechild",
       methods=["POST"])
@route("/api/v1/topic/<parent_id>/deletechild", methods=["POST"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def topic_delete_child(parent_id, version_id="edit"):

    kind = request.request_string("kind")
    id = request.request_string("id")

    [error, child, parent_topic, _] = topic_find_child(parent_id, version_id,
                                                       kind, id)
    if error:
        return api_invalid_param_response(error)

    parent_topic.delete_child(child)

    return parent_topic.get_visible_data()


@route("/api/v1/topicversion/<version_id>/topic/<old_parent_id>/movechild",
       methods=["POST"])
@route("/api/v1/topic/<old_parent_id>/movechild", methods=["POST"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def topic_move_child(old_parent_id, version_id="edit"):

    kind = request.request_string("kind")
    id = request.request_string("id")

    [error, child, old_parent_topic, version] = topic_find_child(
        old_parent_id, version_id, kind, id)

    if error:
        return api_invalid_param_response(error)

    if child.key() not in old_parent_topic.child_keys:
        return api_invalid_param_response(
            "%s with ID %s does not exist in topic %s" %
            (kind, id, old_parent_id))

    new_parent_id = request.request_string("new_parent_id")
    new_parent_topic = topic_models.Topic.get_by_id(new_parent_id, version)

    if not new_parent_topic:
        return api_invalid_param_response(
            "Could not find topic with ID %s " % new_parent_id)

    if (child.key() in new_parent_topic.child_keys) and (
            old_parent_id != new_parent_id):
        return api_invalid_param_response(
            "%s with ID %s already exists in topic %s" %
            (kind, id, new_parent_id))

    new_parent_pos = request.request_string("new_parent_pos")

    old_parent_topic.move_child(child, new_parent_topic, new_parent_pos)

    return True


@route("/api/v1/topicversion/<version_id>/topic/<topic_id>/ungroup",
       methods=["POST"])
@route("/api/v1/topic/<topic_id>/ungroup", methods=["POST"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def topic_ungroup(topic_id, version_id="edit"):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response(
            "Could not find version_id %s" % version_id)

    topic = topic_models.Topic.get_by_id(topic_id, version)
    if not topic:
        return api_invalid_param_response(
            "Could not find topic with ID %s" % topic_id)

    topic.ungroup()

    return True


@route("/api/v1/topicversion/<version_id>/topic/<topic_id>/children",
       methods=["GET"])
@route("/api/v1/topic/<topic_id>/children", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@layer_cache.cache_with_key_fxn(
    (lambda topic_id, version_id=None: "api_topic_children_%s_%s_%s" % (
        topic_id, version_id, setting_model.Setting.topic_tree_version())
        if version_id is None or version_id == "default" else None),
    layer=layer_cache.Layers.Memcache)
@jsonify
def topic_children(topic_id, version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response(
            "Could not find version_id %s" % version_id)

    topic = topic_models.Topic.get_by_id(topic_id, version)
    if not topic:
        return api_invalid_param_response(
            "Could not find topic with ID %s" % topic_id)

    return db.get(topic.child_keys)


@route("/api/v1/topicversion/<version_id>/setdefault", methods=["GET"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def set_default_topic_version(version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    version.set_default_version()
    # creates a new edit version if one does not already exists
    topic_models.TopicVersion.get_edit_version()
    return version


@route("/api/v1/topicversion/<version_id>", methods=["GET"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def topic_version(version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    return version


@route("/api/v1/topicversion/<version_id>", methods=["PUT"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def update_topic_version(version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)

    version_json = request.json

    changed = False
    for key in ["title", "description"]:
        if getattr(version, key) != version_json[key]:
            setattr(version, key, version_json[key])
            changed = True

    if changed:
        version.put()

    return {}


@route("/api/v1/topicversions/", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def topic_versions():
    versions = topic_models.TopicVersion.all().order("-number").fetch(10000)
    return versions


@route("/api/v1/topicversion/<version_id>/unused_content", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def topic_version_unused_content(version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    return version.get_unused_content()


@route("/api/v1/topicversion/<version_id>/url/<int:url_id>", methods=["GET"])
@route("/api/v1/url/<int:url_id>", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_url(url_id, version_id=None):
    if version_id:
        version = topic_models.TopicVersion.get_by_id(version_id)
        if version is None:
            return api_invalid_param_response("Could not find version_id %s"
                                              % version_id)
    else:
        version = None
    return url_model.Url.get_by_id_for_version(url_id, version)


@route("/api/v1/topicversion/<version_id>/url/", methods=["PUT"])
@route("/api/v1/topicversion/<version_id>/url/<int:url_id>", methods=["PUT"])
@route("/api/v1/url/", methods=["PUT"])
@route("/api/v1/url/<int:url_id>", methods=["PUT"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def save_url(url_id=None, version_id=None):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    changeable_props = ["tags", "title", "url"]

    if url_id is None:
        return topic_models.VersionContentChange.add_new_content(url_model.Url,
                                                           version,
                                                           request.json,
                                                           changeable_props)
    else:
        url = url_model.Url.get_by_id_for_version(url_id, version)
        if url is None:
            return api_invalid_param_response(
                "Could not find a Url with ID %s " % (url_id))
        return topic_models.VersionContentChange.add_content_change(
            url,
            version,
            request.json,
            changeable_props)


@route("/api/v1/searchindex", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_topictree_search_index():
    search_data = []

    search_data.extend(video_models.Video.get_cached_search_data())
    search_data.extend(topic_models.Topic.get_cached_search_data())

    return search_data


@route("/api/v1/videos/<video_id>/explore_url", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_explore_url(video_id):
    video = video_models.Video.all().filter("youtube_id =", video_id).get()
    if video and video.extra_properties:
        return video.extra_properties.get('explore_url')
    return None


@route("/api/v1/videos/<video_id>/explore_url", methods=["PUT"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def set_explore_url(video_id):
    video = video_models.Video.all().filter("youtube_id =", video_id).get()
    if video:
        if video.extra_properties is None:
            video.extra_properties = {}
        video.extra_properties['explore_url'] = request.request_string('url',
                                                                       None)
        video.put()
        return video.extra_properties['explore_url']
    return None


@route("/api/v1/videos/<readable_id>/questions", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_questions_for_video(readable_id):
    """Return a list of Feedback entity dicts corresponding to the questions
    and answers below the specified video.

    The following URL parameters may be specified:
        qa_expand_key: the key of a question to be included in the response
        page: the desired page number
        sort: one of possible sort orders in voting.VotingSortOrder
    """
    qa_expand_key = request.request_string('qa_expand_key')
    page = request.request_int('page', default=0)
    sort = request.request_int('sort',
            default=voting.VotingSortOrder.HighestPointsFirst)
    return qa.get_questions_for_video(readable_id, qa_expand_key, page, sort)


@route("/api/v1/videos/<readable_id>/questions", methods=["POST"])
@api.auth.decorators.login_required_and(phantom_user_allowed=False)
@jsonp
@jsonify
def add_question_for_video(readable_id):
    """Add a question below the specified video.

    The posted data should be JSON with "text" specified. Returns a dict of the
    added Feedback entity if successful,
    or None.
    """
    question_json = request.json

    if not question_json or ('text' not in question_json):
        return api_invalid_param_response("Question data expected")

    return qa.add_feedback(question_json['text'],
        discussion_models.FeedbackType.Question, readable_id)


@route("/api/v1/videos/<readable_id>/questions/<question_key>",
       methods=["PUT"])
@api.auth.decorators.login_required_and(phantom_user_allowed=False)
@jsonp
@jsonify
def update_question_for_video(readable_id, question_key):
    """Update the text of a question on a video.

    Returns a dict of the updated Feedback entity if successful, or None.
    """
    question_json = request.json

    if not question_json or ('text' not in question_json):
        return api_invalid_param_response("Question data expected")

    return qa.update_feedback(question_key, question_json['text'],
        discussion_models.FeedbackType.Question, readable_id)


@route("/api/v1/questions/<question_key>/answers", methods=["POST"])
@api.auth.decorators.login_required_and(phantom_user_allowed=False)
@jsonp
@jsonify
def add_answer_to_question(question_key):
    """Add an answer to a question.

    The posted data should be JSON with "text" specified. Returns a dict of the
    added Feedback entity if successful, or None.
    """
    answer_json = request.json

    if not answer_json or ('text' not in answer_json):
        return api_invalid_param_response("Answer data expected")

    return qa.add_feedback(answer_json['text'],
        discussion_models.FeedbackType.Answer, question_key)


@route("/api/v1/questions/<question_key>/answers/<answer_key>",
       methods=["PUT"])
@api.auth.decorators.login_required_and(phantom_user_allowed=False)
@jsonp
@jsonify
def update_answer_for_question(question_key, answer_key):
    """Update the text of a particular answer."""
    answer_json = request.json
    if not answer_json or ('text' not in answer_json):
        return api_invalid_param_response("Answer data expected")

    return qa.update_feedback(answer_key, answer_json['text'],
        discussion_models.FeedbackType.Answer)


@route("/api/v1/feedback/<feedback_key>/<mod_action>", methods=["PUT"])
@api.auth.decorators.moderator_required
@jsonp
@jsonify
def perform_mod_action(feedback_key, mod_action):
    """Perform a moderator action, such as clearing a feedback entity's flags
    or changing its type."""
    if mod_action == moderation.ModAction.CLEAR_FLAGS:
        return qa.clear_feedback_flags(feedback_key)
    elif mod_action == moderation.ModAction.UNDELETE:
        return qa.undelete(feedback_key)
    elif mod_action == moderation.ModAction.CHANGE_TYPE:
        json = request.json
        if not json or ('type' not in json):
            return api_invalid_param_response("Target type expected")

        qa.change_feedback_type(feedback_key, json['type'])


@route("/api/v1/feedback/<feedback_key>", methods=["DELETE"])
@api.auth.decorators.login_required_and(phantom_user_allowed=False)
@jsonp
@jsonify
def hide_feedback(feedback_key):
    """Hide the specified feedback entity from the general public.
    If initiated by the entity author, this will delete the entity.
    """
    return qa.hide_feedback(feedback_key)


@route("/api/v1/moderation/feedback", methods=["GET"])
@api.auth.decorators.moderator_required
@jsonp
@jsonify
def get_flagged_feedback():
    """Return a list of Feedback entities that have been flagged or have
    automatically been identified as low quality (using heuristics).

    Deleted posts and posts that have already been approved by the moderator
    will not be present.

    URL parameters:
        type: the desired Feedback type; by default, Question
        offset: the desired offset; by default, 0
        sort: one of possible sort orders in moderation.ModerationSortOrder
    """
    feedback_type = request.request_string('type',
        default=discussion_models.FeedbackType.Question)
    offset = request.request_int('offset', default=0)
    sort = request.request_int('sort',
        default=moderation.ModerationSortOrder.LowQualityFirst)
    return moderation.get_flagged_feedback(feedback_type, offset, sort)


@route("/api/v1/playlists/library", methods=["GET"])
@api.auth.decorators.open_access
@etag(lambda: setting_model.Setting.topic_tree_version())
@jsonp
@cache_with_key_fxn_and_param(
    "casing",
    lambda: "api_library_%s" % setting_model.Setting.topic_tree_version(),
    layer=layer_cache.Layers.Memcache)
@jsonify
def playlists_library():
    tree = topic_models.Topic.get_by_id("root").make_tree()

    def convert_tree(tree):
        topics = []
        for child in tree.children:

            if hasattr(child, "id"):
                # special cases
                if child.id == "new-and-noteworthy":
                    continue
                elif (child.standalone_title ==
                        "California Standards Test: Algebra I" and
                      child.id != "algebra-i"):
                    child.id = "algebra-i"
                elif (child.standalone_title ==
                        "California Standards Test: Geometry" and
                      child.id != "geometry-2"):
                    child.id = "geometry-2"

            if child.kind() == "Topic":
                topic = {}
                topic["name"] = child.title
                videos = []

                for grandchild in child.children:
                    if (grandchild.kind() == "Video" or
                            grandchild.kind() == "Url"):
                        videos.append(grandchild)

                if len(videos):
                    child.videos = videos
                    child.url = ""
                    child.youtube_id = ""
                    del child.children
                    topic["playlist"] = child
                else:
                    topic["items"] = convert_tree(child)

                topics.append(topic)
        return topics

    return convert_tree(tree)


# We expose the following "fresh" route but don't publish the URL for
# internal services that don't want to deal w/ cached values
# ie. youtube-export script
@route("/api/v1/playlists/library/list/fresh", methods=["GET"],
                                               defaults={"fresh": True})
@route("/api/v1/playlists/library/list", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@cache_with_key_fxn_and_param(
    "casing",
    lambda fresh=False: (
        None if fresh else
        "api_library_list_%s" % setting_model.Setting.topic_tree_version()),
    layer=layer_cache.Layers.Memcache)
@jsonify
def playlists_library_list(fresh=False):
    topics = topic_models.Topic.get_filled_content_topics(types=["Video",
                                                                 "Url"])

    topics_list = [t for t in topics if not (
        (t.standalone_title == "California Standards Test: Algebra I" and
         t.id != "algebra-i") or
        (t.standalone_title == "California Standards Test: Geometry" and
         t.id != "geometry-2"))
        ]

    for topic in topics_list:
        topic.videos = topic.children
        topic.title = topic.standalone_title
        del topic.children

    return topics_list


@route("/api/v1/exercises", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_exercises():
    return exercise_models.Exercise.get_all_use_cache()


@route("/api/v1/topicversion/<version_id>/exercises/<exercise_name>",
       methods=["GET"])
@route("/api/v1/exercises/<exercise_name>", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_exercise(exercise_name, version_id=None):
    if version_id:
        version = topic_models.TopicVersion.get_by_id(version_id)
        if version is None:
            return api_invalid_param_response("Could not find version_id %s"
                                              % version_id)
    else:
        version = None
    exercise = exercise_models.Exercise.get_by_name(exercise_name, version)

    # if the exercise has been modified then related_video_readable_ids may
    # already be set
    if exercise and not hasattr(exercise, "related_video_readable_ids"):
        exercise_videos = exercise.related_videos_query()
        exercise.related_videos = (
            map(lambda exercise_video: exercise_video.video.youtube_id,
                exercise_videos))
        exercise.related_video_readable_ids = (
            map(lambda exercise_video: exercise_video.video.readable_id,
                exercise_videos))
    return exercise


@route("/api/v1/exercises/recent", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def exercise_recent_list():
    return exercise_models.Exercise.all().order('-creation_date').fetch(20)


@route("/api/v1/exercises/<exercise_name>/followup_exercises", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def exercise_info(exercise_name):
    exercise = exercise_models.Exercise.get_by_name(exercise_name)
    return exercise.followup_exercises() if exercise else []


@route("/api/v1/exercises/<exercise_name>/videos", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def exercise_videos(exercise_name):
    exercise = exercise_models.Exercise.get_by_name(exercise_name)
    if exercise:
        exercise_videos = exercise.related_videos_query()
        return map(lambda exercise_video: exercise_video.video,
                   exercise_videos)
    return []


@route("/api/v1/topicversion/<version_id>/exercises/<exercise_name>",
       methods=["POST", "PUT"])
@route("/api/v1/exercises/<exercise_name>", methods=["PUT", "POST"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def exercise_save(exercise_name=None, version_id="edit"):
    request.json["name"] = exercise_name
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    query = exercise_models.Exercise.all()
    query.filter('name =', exercise_name)
    exercise = query.get()
    return v1_utils.exercise_save_data(version, request.json, exercise)


@route("/api/v1/topicversion/<version_id>/videos/<video_id>", methods=["GET"])
@route("/api/v1/videos/<video_id>", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def video(video_id, version_id=None):
    if version_id:
        version = topic_models.TopicVersion.get_by_id(version_id)
        if version is None:
            return api_invalid_param_response("Could not find version_id %s"
                                              % version_id)
    else:
        version = None

    video = video_models.Video.get_for_readable_id(video_id, version)
    if video is None:
        video = video_models.Video.all().filter("youtube_id =", video_id).get()

    return video


@route("/api/v1/videos/recent", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def video_recent_list():
    return video_models.Video.all().order('-date_added').fetch(20)


@route("/api/v1/videos/<video_id>/download_available", methods=["POST"])
@api.auth.decorators.developer_required
@api.auth.decorators.oauth_consumers_must_be_anointed
@jsonp
@jsonify
def video_download_available(video_id):

    video = None
    formats = request.request_string("formats", default="")
    allowed_formats = ["mp4", "png", "m3u8"]

    # If for any crazy reason we happen to have multiple entities for
    # a single youtube id, make sure they all have the same
    # downloadable_formats so we don't keep trying to export them.
    for video in video_models.Video.all().filter("youtube_id =", video_id):

        modified = False

        for downloadable_format in formats.split(","):
            if (downloadable_format in allowed_formats and
                    downloadable_format not in video.downloadable_formats):
                video.downloadable_formats.append(downloadable_format)
                modified = True

        if modified:
            video.put()

    return video


@route("/api/v1/videos/<video_id>/exercises", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def video_exercises(video_id):
    video = video_models.Video.get_for_readable_id(video_id)
    if video is None:
        video = video_models.Video.all().filter("youtube_id =", video_id).get()
    if video:
        return video.related_exercises(bust_cache=True)
    return []


@route("/api/v1/videos/<topic_id>/<video_id>/play", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def video_play_data(topic_id, video_id):
    topic = topic_models.Topic.get_by_id(topic_id)
    if topic is None:
        return api_invalid_param_response("Could not find topic with ID %s" %
                                          topic_id)

    get_topic_data = request.request_bool('topic', default=False)

    discussion_options = {
        "comments_page": 0,
        "qa_page": 0,
        "qa_expand_key": "",
        "sort": -1
    }
    ret = {
        "video": video_models.Video.get_play_data(video_id, topic,
                                                  discussion_options)
    }

    if get_topic_data:
        ret["topic"] = topic.get_play_data()

    return ret


@route("/api/v1/commoncore", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_cc_map():
    lightweight = request.request_bool('lightweight', default=False)
    structured = request.request_bool('structured', default=False)
    return CommonCoreMap.get_all(lightweight, structured)


# Fetches data from YouTube if we don't have it already in the datastore
@route("/api/v1/videos/<youtube_id>/youtubeinfo", methods=["GET"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def get_youtube_info(youtube_id):
    video_data = \
        video_models.Video.all().filter("youtube_id =", youtube_id).get()
    if video_data:
        setattr(video_data, "existing", True)
        return video_data

    video_data = video_models.Video(youtube_id=youtube_id)
    return youtube_get_video_data(video_data)


@route("/api/v1/topicversion/<version_id>/videos/", methods=["POST", "PUT"])
@route("/api/v1/topicversion/<version_id>/videos/<video_id>",
       methods=["POST", "PUT"])
@route("/api/v1/videos/", methods=["POST", "PUT"])
@route("/api/v1/videos/<video_id>", methods=["POST", "PUT"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def save_video(video_id="", version_id="edit"):
    version = topic_models.TopicVersion.get_by_id(version_id)
    if version is None:
        return api_invalid_param_response("Could not find version_id %s"
                                          % version_id)
    video = video_models.Video.get_for_readable_id(video_id, version)

    def check_duplicate(new_data, video=None):
        # make sure we are not changing the video's readable_id to
        # another one's
        query = video_models.Video.all()
        query = query.filter("readable_id =", new_data["readable_id"])
        if video:
            query = query.filter("__key__ !=", video.key())
        other_video = query.get()

        if other_video:
            return api_invalid_param_response(
                "Video with readable_id %s already exists" %
                (new_data["readable_id"]))

        # make sure we are not changing the video's youtube_id to another one's
        query = video_models.Video.all()
        query = query.filter("youtube_id =", new_data["youtube_id"])
        if video:
            query = query.filter("__key__ !=", video.key())
        other_video = query.get()

        if other_video:
            return api_invalid_param_response(
                "Video with youtube_id %s already appears with readable_id %s for video %s"
                % (new_data["youtube_id"], video.readable_id, other_video.title))

        # make sure we are not changing the video's readable_id to an
        # updated one in the Version's Content Changes
        changes = topic_models.VersionContentChange.get_updated_content_dict(
            version)
        for key, content in changes.iteritems():
            if type(content) == video_models.Video and (video is None or
                                                        key != video.key()):

                if content.readable_id == new_data["readable_id"]:
                    return api_invalid_param_response(
                        "Video with readable_id %s already exists" %
                        (new_data["readable_id"]))

                elif content.youtube_id == new_data["youtube_id"]:
                    return api_invalid_param_response(
                        "Video with youtube_id %s already appears with "
                        "readable_id %s" %
                        (new_data["youtube_id"], content.readable_id))

    if video:
        error = check_duplicate(request.json, video)
        if error:
            return error
        return topic_models.VersionContentChange.add_content_change(video,
            version,
            request.json,
            ["readable_id", "title", "youtube_id", "description", "keywords"])

    # handle making a new video
    else:
        # make sure video doesn't already exist
        error = check_duplicate(request.json)
        if error:
            return error

        video_data = youtube_get_video_data_dict(request.json["youtube_id"])
        if video_data is None:
            return None
        return topic_models.VersionContentChange.add_new_content(
                video_models.Video,
                version,
                video_data)


def get_students_data_from_request(user_data):
    return util_profile.get_students_data(user_data,
                                          request.request_string("list_id"))


@route("/api/v1/user", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def user_data_other():
    user_data_student = get_visible_user_data_from_request()
    return user_data_student    # may be None


@route("/api/v1/user/deletion_code", methods=["GET"])
@api.auth.decorators.admin_required
@jsonp
@jsonify
def user_data_deletion_code():
    """Return a temporary deletion code that can be used to delete an account.

    The deletion code returned will be accepted by a DELETE request sent to
    /api/v1/user. The code is only valid for 60 seconds.

    For obvious reasons, both this method and the DELETE sent to /api/v1/user
    are as restricted as possible. Currently, that means only administrators
    (not devs) can permanently delete accounts.

    This expects an ?email= parameter to target a specific user, because we do
    not let users delete their own accounts.
    """
    user_data_student = request.request_student_user_data()

    if not user_data_student:
        raise Exception("No student found")

    if user_data_student.key() == user_models.UserData.current().key():
        raise Exception("Cannot delete yourself.")

    deletion_code_key = "deletion_code:%s" % user_data_student.user_id
    deletion_code = os.urandom(8).encode("hex")

    # Store deletion code in memcache for 60 seconds
    memcache.set(deletion_code_key, deletion_code, time=60)

    return {"deletion_code": deletion_code, "user_data": user_data_student}


@route("/api/v1/user", methods=["DELETE"])
@api.auth.decorators.admin_required
@jsonp
@jsonify
def user_data_delete():
    """Permanently delete a user's account and return the deleted UserData.

    This expects an ?email= parameter to target a specific user, because we do
    not let users delete their own accounts.

    This also expects a ?deletion_code= parameter as supplied by
    /api/v1/user/deletion_code.
    """
    user_data_student = request.request_student_user_data()

    if user_data_student.key() == user_models.UserData.current().key():
        raise Exception("Cannot delete yourself.")

    deletion_code_key = "deletion_code:%s" % user_data_student.user_id
    deletion_code_client = request.request_string("deletion_code")
    deletion_code_server = memcache.get(deletion_code_key)

    if not deletion_code_client:
        raise Exception("Missing deletion code.")

    if deletion_code_client != deletion_code_server:
        raise Exception("Mismatched deletion code.")

    # Admin supplied valid confirmation code. Delete the user.
    user_data_student.delete()

    return user_data_student


@route("/api/v1/user/username_available", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def is_username_available():
    """ Return whether username is available.
    """
    username = request.request_string('username')
    if not username:
        return False
    else:
        return user_models.UniqueUsername.is_available_username(username)


@route("/api/v1/user/promo/<promo_name>", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def has_seen_promo(promo_name):
    user_data = user_models.UserData.current()
    return (promo_record_model.PromoRecord.
            has_user_seen_promo(promo_name, user_data.user_id))


@route("/api/v1/user/promo/<promo_name>", methods=["POST"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def mark_promo_as_seen(promo_name):
    user_data = user_models.UserData.current()
    return (promo_record_model.PromoRecord.
            record_promo(promo_name, user_data.user_id))


@route("/api/v1/user/profile", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_user_profile():
    current_user_data = (user_models.UserData.current() or
                         user_models.UserData.pre_phantom())
    # TODO(marcia): This uses user_id, as opposed to email...
    # which means that the GET and POST are not symmetric...
    user_data = request.request_student_user_data()
    return util_profile.UserProfile.from_user(user_data, current_user_data)


@route("/api/v1/user/profile", methods=["POST", "PUT"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def update_user_profile():
    """Update public information about a user.

    The posted data should be JSON, with fields representing the values that
    needs to be changed. Supports "user_nickname", "avatar_name",
    "username", and "isPublic".
    """
    user_data = user_models.UserData.current()

    profile_json = request.json
    if not profile_json:
        return api_invalid_param_response("Profile data expected")

    if profile_json['nickname'] is not None:

        # Probably they won't update the nickname more than once that often
        if profile_json['nickname'] != user_data.nickname:
            gae_bingo.gae_bingo.bingo([
                'nickname_update_binary',  # Core metric
                ])
        user_data.update_nickname(profile_json['nickname'])

    badge_awarded = False
    if profile_json['avatarName'] is not None:
        avatar_name = profile_json['avatarName']
        name_dict = util_avatars.avatars_by_name()

        # Ensure that the avatar is actually valid and that the user can
        # indeed earn it.
        if (avatar_name in name_dict
                and user_data.avatar_name != avatar_name
                and name_dict[avatar_name].is_satisfied_by(user_data)):
            user_data.avatar_name = avatar_name

            gae_bingo.gae_bingo.bingo([
                   'avatar_update_binary',  # Core metric
                   'avatar_update_count',  # Core metric
                  ])

            if (profile_badges.ProfileCustomizationBadge.mark_avatar_changed(
                    user_data)):
                profile_badges.ProfileCustomizationBadge().award_to(user_data)
                badge_awarded = True

    if profile_json['isPublic'] is not None:

        if user_data.is_profile_public != profile_json['isPublic']:
            gae_bingo.gae_bingo.bingo([
                    'public_update_binary',  # Core metric
                  ])

        user_data.is_profile_public = profile_json['isPublic']

    if profile_json['username']:
        username = profile_json['username']
        if ((username != user_data.username) and
                not user_data.claim_username(username)):
            # TODO: How much do we want to communicate to the user?
            return api_invalid_param_response("Error!")

    user_data.put()

    result = util_profile.UserProfile.from_user(user_data, user_data)
    if badge_awarded:
        result = {
            'payload': result,
            'action_results': None,
        }
        add_action_results(result, {})

    gae_bingo.gae_bingo.bingo([
        'profile_update_binary',  # Core metric
        'profile_update_count',  # Core metric
    ])

    return result


@route("/api/v1/user/discussion/summary", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_user_summary():
    """Get the discussion summary for a user."""
    user_data = request.request_student_user_data()
    current = user_models.UserData.current()

    page = 1
    sort = voting.VotingSortOrder.HighestPointsFirst
    limit = 3

    questions = qa.get_user_questions(user_data, current, page, sort, limit)
    answers = qa.get_user_answers(user_data, current, page, sort, limit)
    comments = qa.get_user_comments(user_data, current, page, sort, limit)

    statistics = qa.get_user_discussion_statistics(user_data, current)
    badges = util_badges.get_user_discussion_badges(user_data)

    return {
        "questions": questions,
        "answers": answers,
        "comments": comments,
        "badges": badges,
        "statistics": statistics
    }


@route("/api/v1/user/questions", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_user_questions():
    """Get data associated with a user's questions and unread answers."""
    user_data = request.request_student_user_data()
    current = user_models.UserData.current()

    page = request.request_int('page', default=1)
    sort = request.request_int('sort',
            default=voting.VotingSortOrder.HighestPointsFirst)
    limit = request.request_int('limit', default=-1)

    return qa.get_user_questions(user_data, current, page, sort, limit)


@route("/api/v1/user/answers", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_user_answers():
    """Get data associated with a user's answers."""
    user_data = request.request_student_user_data()
    current = user_models.UserData.current()

    page = request.request_int('page', default=1)
    sort = request.request_int('sort',
            default=voting.VotingSortOrder.HighestPointsFirst)
    limit = request.request_int('limit', default=-1)

    return qa.get_user_answers(user_data, current, page, sort, limit)


@route("/api/v1/user/comments", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_user_comments():
    """Get data associated with a user's comments."""
    user_data = request.request_student_user_data()
    current = user_models.UserData.current()

    page = request.request_int('page', default=1)
    sort = request.request_int('sort',
            default=voting.VotingSortOrder.HighestPointsFirst)
    limit = request.request_int('limit', default=-1)

    return qa.get_user_comments(user_data, current, page, sort, limit)


@route("/api/v1/user/discussion/badges", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_user_discussion_badges():
    """Get the discussion badges earned by a user."""
    user_data = request.request_student_user_data()
    return util_badges.get_user_discussion_badges(user_data)


@route("/api/v1/user/discussion/statistics", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_user_discussion_statistics():
    """Get the discussion statistics for a user."""
    user_data = request.request_student_user_data()
    current = user_models.UserData.current()
    return qa.get_user_discussion_statistics(user_data, current)


@route("/api/v1/user/notifications", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def get_user_notifications():
    """Get data associated with a user's notifications."""
    user_data = request.request_visible_student_user_data()
    page = request.request_int('page', default=1)
    limit = request.request_int('limit', default=-1)
    return qa.get_user_notifications(user_data, page, limit)


@route("/api/v1/user/questions/suggestions", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def get_user_question_suggestions():
    """Get suggestions for videos in which user can ask questions."""
    user_data = request.request_visible_student_user_data()
    return qa.get_user_question_suggestions(user_data)


@route("/api/v1/user/answers/suggestions", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def get_user_answer_suggestions():
    """Get suggestions for videos in which user can answer questions"""
    user_data = request.request_visible_student_user_data()
    return qa.get_user_answer_suggestions(user_data)


@route("/api/v1/user/coaches", methods=["GET"])
@api.auth.decorators.login_required_and(phantom_user_allowed=False)
@jsonp
@jsonify
def get_coaches_and_requesters():
    """ Return list of UserProfiles corresponding to the student's
        coaches and coach requesters
    """
    user_data = request.request_visible_student_user_data()
    current_user_data = user_models.UserData.current()

    if not current_user_data:
        return api_unauthorized_response("Unable to see coaches")

    # Note that parents can see coach lists, but regular coaches cannot.
    if (current_user_data.user_id != user_data.user_id and
            not user_models.ParentChildPair.is_pair(
                    parent_user_data=current_user_data,
                    child_user_data=user_data)):
        return api_unauthorized_response("Only parents can see coaches")

    return (util_profile.UserProfile
            .get_coach_and_requester_profiles_for_student(user_data))


@route("/api/v1/user/coaches", methods=["PUT"])
@api.auth.decorators.login_required_and(phantom_user_allowed=False)
@jsonp
@jsonify
def update_coaches_and_requesters():
    """ Update the student's list of coaches and coach requesters
    """
    # TODO(marcia): what is the deal with coach_email.lower() in coaches.py
    user_data = user_models.UserData.current()

    if not user_data.can_modify_coaches():
        return api_unauthorized_response("Unable to modify coach list")

    try:
        profiles = coaches.update_coaches_and_requests(user_data, request.json)
    except custom_exceptions.InvalidEmailException:
        return api_invalid_param_response("Received an invalid email.")

    return profiles


@route("/api/v1/user/capabilities", methods=["PUT"])
@api.auth.decorators.login_required_and(phantom_user_allowed=False)
@jsonp
@jsonify
def update_user_capabilities():
    """A request to modify the capabilities of a child account."""
    user_data = user_models.UserData.current()
    target = request.request_visible_student_user_data()
    if (not target or
            not user_models.ParentChildPair.is_pair(parent_user_data=user_data,
                                                    child_user_data=target)):
        return api_unauthorized_response("Can't modify capabilities unless "
                                         "you're a parent")

    add = request.request_string("add")
    remove = request.request_string("remove")

    # Right now we only support modifying coach list mutations.
    if add:
        add = add.split(',')
        if user_models.Capabilities.MODIFY_COACHES in add:
            target.set_can_modify_coaches(allow=True)
    elif remove:
        remove = remove.split(',')
        if user_models.Capabilities.MODIFY_COACHES in remove:
            target.set_can_modify_coaches(allow=False)


@route("/api/v1/user/students", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def user_data_student():
    user_data_student = get_visible_user_data_from_request(
        disable_coach_visibility=True)
    if user_data_student:
        return get_students_data_from_request(user_data_student)

    return None


@route("/api/v1/user/studentlists", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def get_user_studentlists():
    user_data_student = get_visible_user_data_from_request()
    if user_data_student:
        student_lists_model = user_models.StudentList.get_for_coach(
            user_data_student.key())
        student_lists = []
        for student_list in student_lists_model:
            student_lists.append({
                'key': str(student_list.key()),
                'name': student_list.name,
            })
        return student_lists

    return None


@route("/api/v1/user/studentlists", methods=["POST"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def create_user_studentlist():
    coach_data = user_models.UserData.current()

    list_name = request.request_string('list_name').strip()
    if not list_name:
        raise Exception('Invalid list name')

    student_list = user_models.StudentList(coaches=[coach_data.key()],
        name=list_name)
    student_list.put()

    student_list_json = {
        'name': student_list.name,
        'key': str(student_list.key())
    }
    return student_list_json


@route("/api/v1/user/studentlists/<list_key>", methods=["DELETE"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def delete_user_studentlist(list_key):
    coach_data = user_models.UserData.current()

    student_list = util_profile.get_student_list(coach_data, list_key)
    student_list.delete()
    return True


def filter_query_by_request_dates(query, property):

    if request.request_string("dt_start"):
        try:
            dt_start = request.request_date_iso("dt_start")
            query.filter("%s >=" % property, dt_start)
        except ValueError:
            raise ValueError("Invalid date format sent to dt_start, use "
                             "ISO 8601 Combined.")

    if request.request_string("dt_end"):
        try:
            dt_end = request.request_date_iso("dt_end")
            query.filter("%s <" % property, dt_end)
        except ValueError:
            raise ValueError("Invalid date format sent to dt_end, use "
                             "ISO 8601 Combined.")


@route("/api/v1/user/videos", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def user_videos_all():
    user_data_student = get_visible_user_data_from_request()

    if user_data_student:
        user_videos_query = video_models.UserVideo.all().filter(
            "user =", user_data_student.user)

        try:
            filter_query_by_request_dates(user_videos_query, "last_watched")
        except ValueError, e:
            return api_error_response(e)

        return user_videos_query.fetch(10000)

    return None


@route("/api/v1/user/videos/<youtube_id>", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def user_videos_specific(youtube_id):
    user_data_student = get_visible_user_data_from_request()
    video = video_models.Video.all().filter("youtube_id =", youtube_id).get()

    if user_data_student and video:
        user_videos = (video_models.UserVideo.all()
                       .filter("user =", user_data_student.user)
                       .filter("video =", video))
        return user_videos.get()

    return None


# Can specify video using "video_key" parameter instead of youtube_id.
# Supports a GET request to solve the IE-behind-firewall issue with
# occasionally stripped POST data.
# See http://code.google.com/p/khanacademy/issues/detail?id=3098
# and http://stackoverflow.com/questions/328281/why-content-length-0-in-post-requests
@route("/api/v1/user/videos/<youtube_id>/log", methods=["POST"])
@route("/api/v1/user/videos/<youtube_id>/log_compatability", methods=["GET"])
# @open_access + @create_phantom will log in the user if appropriate
# (either the cookie or oauth map is set), or else create a phantom user.
@api.auth.decorators.open_access
@api.auth.decorators.oauth_consumers_must_be_anointed
@api_create_phantom
@jsonp
@jsonify
def log_user_video(youtube_id):
    if (not request.request_string("seconds_watched") or
            not request.request_string("last_second_watched")):
        logging.critical("Video log request with no parameters received.")
        return api_invalid_param_response("Must supply seconds_watched and" +
            "last_second_watched")

    user_data = user_models.UserData.current()

    video_key_str = request.request_string("video_key")

    if not youtube_id and not video_key_str:
        return api_invalid_param_response(
            "Must supply youtube_id or video_key")

    if video_key_str:
        key = db.Key(video_key_str)
        video = db.get(key)
    else:
        video = (video_models.Video.
                 all().
                 filter("youtube_id =", youtube_id).
                 get())

    if not video:
        logging.error("Could not find video for %s" % (video_key_str or
                                                       youtube_id))
        return api_invalid_param_response("Could not find video for %s" %
                                          (video_key_str or youtube_id))

    seconds_watched = int(request.request_float("seconds_watched", default=0))
    last_second = int(request.request_float("last_second_watched", default=0))

    user_video, video_log, _, goals_updated = video_models.VideoLog.add_entry(
        user_data, video, seconds_watched, last_second)

    if video_log:
        action_results = {}

        # this UserVideo is being included purely because client code needs
        # access to UserVideo.{points, completed}
        action_results['user_video'] = user_video

        if goals_updated:
            action_results['updateGoals'] = [g.get_visible_data(None)
                for g in goals_updated]

        add_action_results(video_log, action_results)

    return video_log


@route("/api/v1/user/topic/<topic_id>/cards/next", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def topic_next_cards(topic_id):
    """Retrieves the next few suggested cards in a specific topic, as well as
    any additional information required to render those cards
    """

    user_data = user_models.UserData.current()

    # Be forgiving in the event that a user asks for next exercises even when
    # they're not logged in. There's little reason to fail here, so we just
    # use a pre_phantom user to return the next exercises that would be
    # handed out if a new user tackled this topic.
    if not user_data:
        user_data = user_models.UserData.pre_phantom()

    topic = topic_models.Topic.get_by_id(topic_id)
    if not topic:
        return api_invalid_param_response(
            "Could not find topic with id: %s " % topic_id)

    # TODO(david): Refactor this bit of code into stacks.py:ProblemStack
    next_user_exercises = exercise_models.UserExercise.next_in_topic(
        user_data, topic, queued=request.values.getlist("queued[]"))

    return exercises.stacks.ProblemStack(next_user_exercises)


@route("/api/v1/user/exercises", methods=["GET"])
@route("/api/v1/user/topic/<topic_id>/exercises", methods=["GET"])
@api.auth.decorators.login_required_and(demo_user_allowed=True)
@jsonp
@jsonify
def user_exercises_list(topic_id=None):
    """ Retrieves the list of exercise models wrapped inside of an object that
    gives information about what sorts of progress and interaction the current
    user has had with it.

    If topic_id is supplied, limits the list to the topic's subset of
    exercises.

    Defaults to a pre-phantom users, in which case the encasing object is
    skeletal and contains little information.

    """
    student = get_visible_user_data_from_request()

    if not student:
        student = user_models.UserData.pre_phantom()

    exercises = None

    if topic_id:

        # Grab all exercises within a specific topic
        topic = topic_models.Topic.get_by_id(topic_id)

        if not topic:
            return api_invalid_param_response(
                "Could not find topic with id: %s " % topic_id)

        exercises = topic.get_exercises(include_descendants=True)

    else:

        # Grab all exercises
        exercises = exercise_models.Exercise.get_all_use_cache()

    user_exercise_graph = exercise_models.UserExerciseGraph.get(
        student, exercises_allowed=exercises)

    user_exercises_dict = {}

    if not student.is_pre_phantom:
        user_exercises_dict = dict(
            (attrs["name"], exercise_models.UserExercise.from_dict(attrs,
                                                                   student))
            for attrs in user_exercise_graph.graph_dicts()
        )

    results = []

    for exercise in exercises:

        name = exercise.name

        if name not in user_exercises_dict:
            user_exercise = exercise_models.UserExercise()
            user_exercise.exercise = name
            user_exercise.user = student.user
        else:
            user_exercise = user_exercises_dict[name]

        user_exercise.exercise_model = exercise
        user_exercise._user_data = student
        user_exercise._user_exercise_graph = user_exercise_graph

        results.append(user_exercise)

    return results


@route("/api/v1/user/students/progress/summary", methods=["GET"])
@api.auth.decorators.login_required_and(demo_user_allowed=True)
@jsonp
@jsonify
def get_students_progress_summary():
    user_data_coach = get_user_data_coach_from_request()

    try:
        list_students = get_students_data_from_request(user_data_coach)
    except Exception, e:
        return api_invalid_param_response(e.message)

    list_students = sorted(list_students, key=lambda student: student.nickname)
    user_exercise_graphs = exercise_models.UserExerciseGraph.get(list_students)

    student_review_exercise_names = []
    for user_exercise_graph in user_exercise_graphs:
        student_review_exercise_names.append(
            user_exercise_graph.review_exercise_names())

    exercises = exercise_models.Exercise.get_all_use_cache()
    exercise_data = []

    for exercise in exercises:
        progress_buckets = {
            'review': [],
            'proficient': [],
            'struggling': [],
            'started': [],
            'not-started': [],
        }

        for (student, user_exercise_graph, review_exercise_names) in izip(
                list_students, user_exercise_graphs,
                student_review_exercise_names):
            graph_dict = user_exercise_graph.graph_dict(exercise.name)

            if graph_dict['proficient']:
                if exercise.name in review_exercise_names:
                    status = 'review'
                else:
                    status = 'proficient'
            elif graph_dict['struggling']:
                status = 'struggling'
            elif graph_dict['total_done'] > 0:
                status = 'started'
            else:
                status = 'not-started'

            progress_buckets[status].append({
                    'nickname': student.nickname,
                    'email': student.email,
                    'profile_root': student.profile_root,
            })

        progress = [dict([('status', status),
                        ('students', progress_buckets[status])])
                        for status in progress_buckets]

        exercise_data.append({
            'name': exercise.name,
            'display_name': exercise.display_name,
            'progress': progress,
        })

    return {'exercises': exercise_data,
            'num_students': len(list_students)}

@route("/api/v1/user/exercises/<exercise_name>/request_video", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def user_exercises_request_video(exercise_name):
    exercise = exercise_models.Exercise.get_by_name(exercise_name)
    try:
        exercise.request_video()
        return {'rc': True}
    except:
        return {'rc': False}

@route("/api/v1/user/exercises/<exercise_name>", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def user_exercises_specific(exercise_name):
    user_data_student = get_visible_user_data_from_request()
    exercise = exercise_models.Exercise.get_by_name(exercise_name)

    if user_data_student and exercise:
        user_exercise = (exercise_models.UserExercise.all()
                         .filter("user =", user_data_student.user)
                         .filter("exercise =", exercise_name)
                         .get())

        if not user_exercise:
            user_exercise = exercise_models.UserExercise()
            user_exercise.exercise_model = exercise
            user_exercise.exercise = exercise_name
            user_exercise.user = user_data_student.user

        # Cheat and send back related videos when grabbing a single
        # UserExercise for ease of exercise integration
        user_exercise.exercise_model.related_videos = map(
            lambda exercise_video: exercise_video.video,
            user_exercise.exercise_model.related_videos_fetch())
        return user_exercise

    return None


def user_followup_exercises(exercise_name):
    user_data = user_models.UserData.current()

    if user_data and exercise_name:

        user_data_student = get_visible_user_data_from_request()
        user_exercise_graph = exercise_models.UserExerciseGraph.get(user_data)

        user_exercises = (exercise_models.UserExercise.
                          all().
                          filter("user =", user_data_student.user).
                          fetch(10000))
        followup_exercises = (exercise_models.Exercise
                              .get_by_name(exercise_name)
                              .followup_exercises())

        followup_exercises_dict = dict((exercise.name, exercise)
                                       for exercise in followup_exercises)
        user_exercises_dict = dict((user_exercise.exercise, user_exercise)
                                   for user_exercise in user_exercises
                                   if user_exercise in followup_exercises)

        # create user_exercises that haven't been attempted yet
        for exercise_name in followup_exercises_dict:
            if not exercise_name in user_exercises_dict:
                user_exercise = exercise_models.UserExercise()
                user_exercise.exercise = exercise_name
                user_exercise.user = user_data_student.user
                user_exercises_dict[exercise_name] = user_exercise

        for exercise_name in user_exercises_dict:
            if exercise_name in followup_exercises_dict:
                user_exercises_dict[exercise_name].exercise_model = (
                    followup_exercises_dict[exercise_name])
                user_exercises_dict[exercise_name]._user_data = (
                    user_data_student)
                user_exercises_dict[exercise_name]._user_exercise_graph = (
                    user_exercise_graph)

        return user_exercises_dict.values()

    return None


@route("/api/v1/user/exercises/<exercise_name>/followup_exercises",
       methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def api_user_followups(exercise_name):
    return user_followup_exercises(exercise_name)


@route("/api/v1/user/topics", methods=["GET"])
@route("/api/v1/user/playlists", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def user_playlists_all():
    user_data_student = get_visible_user_data_from_request()

    if user_data_student:
        user_playlists = (topic_models.UserTopic.all()
                          .filter("user =", user_data_student.user))
        return user_playlists.fetch(10000)

    return None


@route("/api/v1/user/exercises/reviews/count", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def reviews_count():
    user_data = user_models.UserData.current()
    user_exercise_graph = exercise_models.UserExerciseGraph.get(user_data)
    return len(user_exercise_graph.review_exercise_names())


@route("/api/v1/user/exercises/<exercise_name>/log", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def user_problem_logs(exercise_name):
    user_data = user_models.UserData.current()

    if user_data and exercise_name:
        user_data_student = get_visible_user_data_from_request()
        exercise = exercise_models.Exercise.get_by_name(exercise_name)

        if user_data_student and exercise:

            problem_log_query = exercise_models.ProblemLog.all()
            problem_log_query.filter("user =", user_data_student.user)
            problem_log_query.filter("exercise =", exercise.name)

            try:
                filter_query_by_request_dates(problem_log_query, "time_done")
            except ValueError, e:
                return api_error_response(e)

            problem_log_query.order("time_done")

            return problem_log_query.fetch(500)

    return None


# TODO(david): Factor out duplicated code between attempt_problem_number and
#     hint_problem_number. (+1 David again.)
@route("/api/v1/user/exercises/<exercise_name>/problems"
           "/<int:problem_number>/attempt",
       methods=["POST"])
# @open_access + @create_phantom will log in the user if appropriate
# (either the cookie or oauth map is set), or else create a phantom user.
@api.auth.decorators.open_access
@api_create_phantom
@jsonp
@jsonify
def attempt_problem_number(exercise_name, problem_number):
    user_data = user_models.UserData.current()

    exercise = exercise_models.Exercise.get_by_name(exercise_name)
    user_exercise = user_data.get_or_insert_exercise(exercise)

    if user_exercise and problem_number:

        review_mode = request.request_bool("review_mode", default=False)
        card_json = request.request_string("card")
        cards_done = request.request_int("cards_done", default=-1)
        cards_left = request.request_int("cards_left", default=-1)

        if cards_done == -1 or cards_left == -1 or not card_json:
            return api_invalid_param_response("Missing request params:" +
                    " cards_done, cards_left, or card")

        user_exercise, user_exercise_graph, goals_updated = (
            exercises.exercise_util.attempt_problem(
                user_data,
                user_exercise,
                problem_number,
                request.request_int("attempt_number"),
                request.request_string("attempt_content"),
                request.request_string("sha1"),
                request.request_string("seed"),
                request.request_bool("complete"),
                request.request_int("count_hints", default=0),
                int(request.request_float("time_taken")),
                review_mode,
                request.request_bool("topic_mode", default=False),
                request.request_string("problem_type"),
                request.remote_addr,
                json.loads(card_json),
                request.request_string("stack_uid"),
                request.request_string("topic_id"),
                cards_done,
                cards_left,
                ))

        # this always returns a delta of points earned each attempt
        points_earned = user_data.points - user_data.original_points()
        if(user_exercise.streak == 0):
            # never award points for a zero streak
            points_earned = 0
        if(user_exercise.streak == 1):
            # award points for the first correct exercise done, even
            # if no prior history exists and the above pts-original
            # points gives a wrong answer
            points_earned = (user_data.points
                             if (user_data.points == points_earned)
                             else points_earned)

        user_states = user_exercise_graph.states(exercise.name)
        correct = request.request_bool("complete")

        # Avoid an extra user exercise graph lookup during serialization
        user_exercise._user_exercise_graph = user_exercise_graph

        action_results = {
            "exercise_state": {
                "state": [state for state in user_states
                          if user_states[state]],
                "template": templatetags.exercise_message(exercise,
                    user_exercise_graph, review_mode=review_mode),
            },
            "points_earned": {"points": points_earned},
            "attempt_correct": correct,
        }

        if goals_updated:
            action_results['updateGoals'] = [g.get_visible_data(None)
                                             for g in goals_updated]

        add_action_results(user_exercise, action_results)
        return user_exercise


@route("/api/v1/user/exercises/<exercise_name>/problems"
           "/<int:problem_number>/hint",
       methods=["POST"])
# @open_access + @create_phantom will log in the user if appropriate
# (either the cookie or oauth map is set), or else create a phantom user.
@api.auth.decorators.open_access
@api_create_phantom
@jsonp
@jsonify
def hint_problem_number(exercise_name, problem_number):

    user_data = user_models.UserData.current()

    exercise = exercise_models.Exercise.get_by_name(exercise_name)
    user_exercise = user_data.get_or_insert_exercise(exercise)

    if user_exercise and problem_number:

        attempt_number = request.request_int("attempt_number")
        count_hints = request.request_int("count_hints")
        review_mode = request.request_bool("review_mode", default=False)
        card_json = request.request_string("card")
        cards_done = request.request_int("cards_done", default=-1)
        cards_left = request.request_int("cards_left", default=-1)

        if cards_done == -1 or cards_left == -1 or not card_json:
            return api_invalid_param_response("Missing request params:" +
                    " cards_done, cards_left, or card")

        user_exercise, user_exercise_graph, _ = (
            exercises.exercise_util.attempt_problem(
                user_data,
                user_exercise,
                problem_number,
                attempt_number,
                request.request_string("attempt_content"),
                request.request_string("sha1"),
                request.request_string("seed"),
                request.request_bool("complete"),
                count_hints,
                int(request.request_float("time_taken")),
                review_mode,
                request.request_bool("topic_mode", default=False),
                request.request_string("problem_type"),
                request.remote_addr,
                json.loads(card_json),
                request.request_string("stack_uid"),
                request.request_string("topic_id"),
                cards_done,
                cards_left,
                ))

        # TODO: this exercise_message_html functionality is currently hidden
        # from power-mode. Restore it.
        # https://trello.com/card/restore-you-re-ready-to-move-on-and-struggling-in-action-messages/4f3f43cd45533a1b3a065a1d/34
        user_states = user_exercise_graph.states(exercise.name)
        exercise_message_html = templatetags.exercise_message(exercise,
                user_exercise_graph, review_mode=review_mode)

        add_action_results(user_exercise, {
            "exercise_message_html": exercise_message_html,
            "exercise_state": {
                "state": [state for state in user_states
                          if user_states[state]],
                "template": exercise_message_html,
            }
        })

        return user_exercise


# TODO: Remove this route in v2
@route("/api/v1/user/exercises/<exercise_name>/reset_streak", methods=["POST"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def reset_problem_streak(exercise_name):
    return _attempt_problem_wrong(exercise_name)


@route("/api/v1/user/exercises/<exercise_name>/wrong_attempt",
       methods=["POST"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def attempt_problem_wrong(exercise_name):
    return _attempt_problem_wrong(exercise_name)


def _attempt_problem_wrong(exercise_name):
    user_data = user_models.UserData.current()

    if user_data and exercise_name:
        user_exercise = user_data.get_or_insert_exercise(
            exercise_models.Exercise.get_by_name(exercise_name))
        return exercises.exercise_util.make_wrong_attempt(user_data,
                                                          user_exercise)

    return unauthorized_response()


@route("/api/v1/user/videos/<youtube_id>/log", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def user_video_logs(youtube_id):
    user_data_student = get_visible_user_data_from_request()
    video = video_models.Video.all().filter("youtube_id =", youtube_id).get()

    if user_data_student and video:

        video_log_query = video_models.VideoLog.all()
        video_log_query.filter("user =", user_data_student.user)
        video_log_query.filter("video =", video)

        try:
            filter_query_by_request_dates(video_log_query, "time_watched")
        except ValueError, e:
            return api_error_response(e)

        video_log_query.order("time_watched")

        return video_log_query.fetch(500)

    return None


# TODO: this should probably not return user data in it.
@route("/api/v1/badges", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def badges_list():
    badges_dict = util_badges.all_badges_dict()

    user_data = user_models.UserData.current()
    if user_data:

        user_data_student = get_visible_user_data_from_request()
        if user_data_student:

            user_badges = models_badges.UserBadge.get_for(user_data_student)

            for user_badge in user_badges:

                badge = badges_dict.get(user_badge.badge_name)

                if badge:
                    if not hasattr(badge, "user_badges"):
                        badge.user_badges = []
                    badge.user_badges.append(user_badge)
                    badge.is_owned = True

    return sorted(filter(lambda badge: not badge.is_hidden(),
                         badges_dict.values()),
                  key=lambda badge: badge.name)


@route("/api/v1/badges/categories", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def badge_categories():
    return badges.BadgeCategory.all()


@route("/api/v1/badges/categories/<category>", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def badge_category(category):
    return filter(
        lambda badge_category: str(badge_category.category) == category,
        badges.BadgeCategory.all())


# TODO: the "GET" version of this.
@route("/api/v1/user/badges/public", methods=["POST", "PUT"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def update_public_user_badges():
    user_data = user_models.UserData.current()

    owned_badges = set([badges.Badge.remove_target_context(name_with_context)
                        for name_with_context in user_data.badges])
    badges_dict = util_badges.all_badges_dict()
    updated_badge_list = []
    empty_name = util_badges.EMPTY_BADGE_NAME
    for name in request.json or []:
        if name in owned_badges:
            updated_badge_list.append(badges_dict[name])

            gae_bingo.gae_bingo.bingo([
                'edited_display_case_binary',  # Core metric
                'edited_display_case_count',  # Core metric
            ])

        elif name == empty_name:
            updated_badge_list.append(None)

    badge_awarded = False
    if (len(updated_badge_list) == util_badges.NUM_PUBLIC_BADGE_SLOTS
            and not any([badge is None for badge in updated_badge_list])):
        if (profile_badges.ProfileCustomizationBadge.mark_display_case_filled(
                user_data)):
            profile_badges.ProfileCustomizationBadge().award_to(user_data)
            badge_awarded = True

    user_data.public_badges = [(badge.name if badge else empty_name)
                               for badge in updated_badge_list]
    user_data.put()

    result = updated_badge_list
    if badge_awarded:
        result = {
            'payload': result,
            'api_action_results': None
        }
        add_action_results(result, {})
    return result


@route("/api/v1/user/badges", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_user_badges():
    user_data = (get_visible_user_data_from_request() or
                 user_models.UserData.pre_phantom())
    grouped_badges = util_badges.get_grouped_user_badges(user_data)

    user_badges_by_category = {
        badges.BadgeCategory.BRONZE: grouped_badges["bronze_badges"],
        badges.BadgeCategory.SILVER: grouped_badges["silver_badges"],
        badges.BadgeCategory.GOLD: grouped_badges["gold_badges"],
        badges.BadgeCategory.PLATINUM: grouped_badges["platinum_badges"],
        badges.BadgeCategory.DIAMOND: grouped_badges["diamond_badges"],
        badges.BadgeCategory.MASTER: grouped_badges["user_badges_master"],
    }

    user_badge_dicts_by_category = {}

    for category, user_badge_bucket in user_badges_by_category.iteritems():
        user_badge_dicts_by_category[category] = user_badge_bucket

    badge_collections = []

    # Iterate over the set of all possible badges.
    for collection in grouped_badges["badge_collections"]:
        if len(collection):
            first_badge = collection[0]
            badge_collections.append({
                "category": first_badge.badge_category,
                "category_description": first_badge.category_description(),
                "badges": collection,
                "user_badges": user_badge_dicts_by_category[
                        first_badge.badge_category],
            })

    return {
            "badge_collections": badge_collections,
        }


# private api call used only by client-side badge share request
@route("/api/v1/user/badges/<badge_slug>/opengraph-earn", methods=["POST"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def opengraph_earn(badge_slug):
    """ Publish the user badge on Facebook using the Open Graph 'earn' action.

    Args:
        badge_slug: The slug of the badge object to publish. For example, the
            slug for the badge with name "fivedayconsecutiveactivitybadge" is
            "good-habits".

    Returns:
        A Flask Response object.
        http://flask.pocoo.org/docs/api/#flask.Response

    NOTE: Please read https://sites.google.com/a/khanacademy.org/forge/technical/facebook-open-graph-sharing-issues for fixit TODOs.
    """

    FB_APP_ACCESS_TOKEN = facebook_utils.get_facebook_app_access_token()

    badges_dict = util_badges.all_badges_slug_dict()
    if not badge_slug in badges_dict:
        return api_invalid_param_response(
            "Badge with slug '%s' not in util_badges.all_badges." % badge_slug)

    # retrieve badge
    badge = badges_dict[badge_slug]

    # check that current user owns badge
    user_data = user_models.UserData.current()
    if not user_data.has_badge(badge.name, ignore_target_context=True):
        return api_unauthorized_response(
            "Badge with slug '%s' is not owned by user." % badge_slug)

    # attempt to send POST request to FB using Facebook ID
    try:
        graph = facebook.GraphAPI(access_token=FB_APP_ACCESS_TOKEN)

        # get Facebook ID of current logged in Facebook user
        facebook_id = facebook_util.get_current_facebook_id_from_cookies()
        action = "%s:earn" % app.App.facebook_app_namespace
        url = badge.opengraph_url

        response = graph.put_object(facebook_id, action, badge=url)

    except Exception, e:
        return api_opengraph_error_response(e)

    return api_created_response(
        "Successfully published Earn action. Response: %s" % response)


@route("/api/v1/user/activity", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def get_activity():
    student = request.request_visible_student_user_data()

    recent_activities = recent_activity.recent_activity_list(student)
    recent_completions = filter(
            lambda activity: activity.is_complete(),
            recent_activities)

    return {
        "suggested": suggested_activity.SuggestedActivity.get_for(
                student, recent_activities),
        "recent": recent_completions[:recent_activity.MOST_RECENT_ITEMS],
    }


# TODO in v2: imbue with restfulness
@route("/api/v1/developers/add", methods=["POST"])
@api.auth.decorators.admin_required
@jsonp
@jsonify
def add_developer():
    user_data_developer = request.request_user_data("email")

    if not user_data_developer:
        return False

    user_data_developer.developer = True
    user_data_developer.put()

    return True


@route("/api/v1/developers/remove", methods=["POST"])
@api.auth.decorators.admin_required
@jsonp
@jsonify
def remove_developer():
    user_data_developer = request.request_user_data("email")

    if not user_data_developer:
        return False

    user_data_developer.developer = False
    user_data_developer.put()

    return True


@route("/api/v1/coworkers/add", methods=["POST"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def add_coworker():
    user_data_coach = request.request_user_data("coach_email")
    user_data_coworker = request.request_user_data("coworker_email")

    if user_data_coach and user_data_coworker:
        if not user_data_coworker.key_email in user_data_coach.coworkers:
            user_data_coach.coworkers.append(user_data_coworker.key_email)
            user_data_coach.put()

        if not user_data_coach.key_email in user_data_coworker.coworkers:
            user_data_coworker.coworkers.append(user_data_coach.key_email)
            user_data_coworker.put()

    return True


@route("/api/v1/coworkers/remove", methods=["POST"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def remove_coworker():
    user_data_coach = request.request_user_data("coach_email")
    user_data_coworker = request.request_user_data("coworker_email")

    if user_data_coach and user_data_coworker:
        if user_data_coworker.key_email in user_data_coach.coworkers:
            user_data_coach.coworkers.remove(user_data_coworker.key_email)
            user_data_coach.put()

        if user_data_coach.key_email in user_data_coworker.coworkers:
            user_data_coworker.coworkers.remove(user_data_coach.key_email)
            user_data_coworker.put()

    return True


@route("/api/v1/autocomplete", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def autocomplete():

    video_results = []

    query = request.request_string("q", default="").strip().lower()
    if query:

        max_results_per_type = 10

        exercise_results = filter(
                lambda exercise: query in exercise.display_name.lower(),
                exercise_models.Exercise.get_all_use_cache())
        video_results = filter(
                lambda video_dict: query in video_dict["title"].lower(),
                video_title_dicts())
        topic_results = filter(
                lambda topic_dict: query in topic_dict["title"].lower(),
                topic_title_dicts())
        url_results = filter(
                lambda url_dict: query in url_dict["title"].lower(),
                url_title_dicts())

        exercise_results = sorted(
                exercise_results,
                key=lambda v: v.display_name.lower().index(query))
        video_results = sorted(
                video_results + url_results,
                key=lambda v: v["title"].lower().index(query))
        topic_results = sorted(
                topic_results,
                key=lambda t: t["title"].lower().index(query))

        exercise_results = exercise_results[:max_results_per_type]
        video_results = video_results[:max_results_per_type]
        topic_results = topic_results[:max_results_per_type]

    else:
        video_results = {}
        topic_results = {}
        exercise_results = {}

    return {
            "query": query,
            "videos": video_results,
            "topics": topic_results,
            "exercises": exercise_results
    }


@route("/api/v1/dev/backupmodels", methods=["GET"])
@api.auth.decorators.developer_required
@jsonify
def backupmodels():
    """Return the names of all models that inherit from
    backup_model.BackupModel."""
    return map(lambda x: x.__name__, backup_model.BackupModel.__subclasses__())


@route("/api/v1/dev/protobuf/<entity>", methods=["GET"])
@api.auth.decorators.developer_required
@pickle
def protobuf_entities(entity):
    """Return up to 'max' entities last altered between 'dt_start' and 'dt_end'

    Notes: 'entity' should either be a subclass of 'backup_model.BackupModel',
            or else a valid 'index' property should also be provided.
           'dt{start,end}' must be in ISO 8601 format.
           'max' defaults to 500
           'index' optionally specifies the property to filter on.
    Example:
        http://www.khanacademy.org/api/v1/dev/protobuf/ProblemLog?dt_start=2012-02-11T20%3A07%3A49Z&dt_end=2012-02-11T21%3A07%3A49Z
        Returns up to 500 problem_logs from between 'dt_start' and 'dt_end'
    """
    try:
        entity_class = db.class_for_kind(entity)
    except db.KindError, why:
        return api_error_response(ValueError("Invalid class '%s': %s" %
                (entity, why)))
    if not issubclass(entity_class, backup_model.BackupModel):
        return api_error_response(ValueError("Invalid class '%s' (must be a \
                subclass of backup_model.BackupModel)" % entity))

    query = entity_class.all()
    index_name = request.request_string("index", default="backup_timestamp")
    filter_query_by_request_dates(query, index_name)
    query.order(index_name)

    return map(lambda entity: db.model_to_protobuf(entity).Encode(),
               query.fetch(request.request_int("max", default=500)))


@route("/api/v1/dev/problems", methods=["GET"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def problem_logs():
    problem_log_query = exercise_models.ProblemLog.all()
    filter_query_by_request_dates(problem_log_query, "time_done")
    problem_log_query.order("time_done")
    return problem_log_query.fetch(request.request_int("max", default=500))


@route("/api/v1/dev/videos", methods=["GET"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def video_logs():
    video_log_query = video_models.VideoLog.all()
    filter_query_by_request_dates(video_log_query, "time_watched")
    video_log_query.order("time_watched")
    return video_log_query.fetch(request.request_int("max", default=500))


@route("/api/v1/dev/users", methods=["GET"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def user_data():
    user_data_query = user_models.UserData.all()
    filter_query_by_request_dates(user_data_query, "joined")
    user_data_query.order("joined")
    return user_data_query.fetch(request.request_int("max", default=500))


@route("/api/v1/user/students/progressreport", methods=["GET"])
@api.auth.decorators.login_required_and(demo_user_allowed=True)
@jsonp
@jsonify
def get_student_progress_report():
    user_data_coach = get_user_data_coach_from_request()

    if not user_data_coach:
        return api_invalid_param_response("User is not logged in.")

    try:
        students = get_students_data_from_request(user_data_coach)
    except Exception, e:
        return api_invalid_param_response(e.message)

    return class_progress_report_graph.class_progress_report_graph_context(
        user_data_coach, students)


@route("/api/v1/user/goals", methods=["GET"])
@api.auth.decorators.login_required_and(demo_user_allowed=True)
@jsonp
@jsonify
def get_user_goals():
    student = request.request_visible_student_user_data()

    goals = GoalList.get_all_goals(student)
    return [g.get_visible_data() for g in goals]


@route("/api/v1/user/goals/current", methods=["GET"])
@api.auth.decorators.login_required_and(demo_user_allowed=True)
@jsonp
@jsonify
def get_user_current_goals():
    student = request.request_visible_student_user_data()

    goals = GoalList.get_current_goals(student)
    return [g.get_visible_data() for g in goals]


@route("/api/v1/user/students/goals", methods=["GET"])
@api.auth.decorators.login_required_and(demo_user_allowed=True)
@jsonp
@jsonify
def get_student_goals():
    user_data_coach = get_user_data_coach_from_request()

    try:
        students = get_students_data_from_request(user_data_coach)
    except Exception, e:
        return api_invalid_param_response(e.message)

    dt_end = datetime.datetime.now()
    days = request.request_int("days", 7)
    dt_start = dt_end - datetime.timedelta(days=days)

    students = sorted(students, key=lambda student: student.nickname)
    user_exercise_graphs = exercise_models.UserExerciseGraph.get(students)

    return_data = []
    for student, uex_graph in izip(students, user_exercise_graphs):
        goals = GoalList.get_modified_between_dts(student, dt_start, dt_end)
        goals = [g.get_visible_data(uex_graph) for g in goals
                 if not g.abandoned]

        return_data.append({
            'email': student.email,
            'profile_root': student.profile_root,
            'goals': goals,
            'nickname': student.nickname,
        })

    return return_data


@route("/api/v1/user/goals", methods=["POST"])
# @open_access + @create_phantom will log in the user if appropriate
# (either the cookie or oauth map is set), or else create a phantom user.
@api.auth.decorators.open_access
@api_create_phantom
@jsonp
@jsonify
def create_user_goal():
    user_data = user_models.UserData.current()

    user_override = request.request_user_data("email")
    if (user_data.developer and
            user_override and
            user_override.key_email != user_data.key_email):
        user_data = user_override

    json = request.json
    title = json.get('title')
    if not title:
        return api_invalid_param_response('Title is invalid.')

    objective_descriptors = []

    goal_videos = GoalList.videos_in_current_goals(user_data)
    current_goals = GoalList.get_current_goals(user_data)

    if json:
        for obj in json['objectives']:
            if obj['type'] == 'GoalObjectiveAnyExerciseProficiency':
                for goal in current_goals:
                    for o in goal.objectives:
                        if isinstance(o, GoalObjectiveAnyExerciseProficiency):
                            return api_invalid_param_response(
                                "User already has a current exercise "
                                "process goal.")
                objective_descriptors.append(obj)

            if obj['type'] == 'GoalObjectiveAnyVideo':
                for goal in current_goals:
                    for o in goal.objectives:
                        if isinstance(o, GoalObjectiveAnyVideo):
                            return api_invalid_param_response(
                                "User already has a current video "
                                "process goal.")
                objective_descriptors.append(obj)

            if obj['type'] == 'GoalObjectiveExerciseProficiency':
                obj['exercise'] = exercise_models.Exercise.get_by_name(
                    obj['internal_id'])
                if (not obj['exercise'] or
                        not obj['exercise'].is_visible_to_current_user()):
                    return api_invalid_param_response(
                        "Internal error: Could not find exercise.")
                objective_descriptors.append(obj)

            if obj['type'] == 'GoalObjectiveWatchVideo':
                obj['video'] = video_models.Video.get_for_readable_id(
                    obj['internal_id'])
                if not obj['video']:
                    return api_invalid_param_response(
                        "Internal error: Could not find video.")
                user_video = (video_models.UserVideo
                              .get_for_video_and_user_data(obj['video'],
                                                           user_data))
                if user_video and user_video.completed:
                    return api_invalid_param_response(
                        "Video has already been watched.")
                if obj['video'].readable_id in goal_videos:
                    return api_invalid_param_response(
                        "Video is already an objective in a current goal.")
                objective_descriptors.append(obj)

    if objective_descriptors:
        objectives = GoalObjective.from_descriptors(objective_descriptors,
            user_data)

        goal = Goal(parent=user_data, title=title, objectives=objectives)
        user_data.save_goal(goal)

        return goal.get_visible_data(None)
    else:
        return api_invalid_param_response("No objectives specified.")


@route("/api/v1/user/goals/<int:id>", methods=["GET"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def get_user_goal(id):
    user_data = user_models.UserData.current()
    goal = Goal.get_by_id(id, parent=user_data)

    if not goal:
        return api_invalid_param_response(
            "Could not find goal with ID %s" % id)

    return goal.get_visible_data(None)


@route("/api/v1/user/goals/<int:id>", methods=["PUT"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def put_user_goal(id):
    user_data = user_models.UserData.current()
    goal = Goal.get_by_id(id, parent=user_data)

    if not goal:
        return api_invalid_param_response(
            "Could not find goal with ID %s" % id)

    goal_json = request.json

    # currently all you can modify is the title
    if goal_json['title'] != goal.title:
        goal.title = goal_json['title']
        goal.put()

    # or abandon something
    if goal_json.get('abandoned') and not goal.abandoned:
        goal.abandon()

        # if this is the last active goal, set has_current_goals to false.
        # note that equating one active goal with not having current goals
        # once we abandon this one assumes that there is no way to abandon
        # a completed goal.
        goals = GoalList.get_current_goals(user_data)
        user_data.has_current_goals = len([g.completed for g in goals]) > 1

        db.put([goal, user_data])

    return goal.get_visible_data(None)


@route("/api/v1/user/goals/<int:id>", methods=["DELETE"])
@api.auth.decorators.login_required
@jsonp
@jsonify
def delete_user_goal(id):
    user_data = user_models.UserData.current()
    goal = Goal.get_by_id(id, parent=user_data)

    if not goal:
        return api_invalid_param_response(
            "Could not find goal with ID %s" % id)

    goal.delete()

    return {}


@route("/api/v1/user/goals", methods=["DELETE"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def delete_user_goals():
    user_data = user_models.UserData.current()
    user_override = request.request_user_data("email")
    if user_override and user_override.key_email != user_data.key_email:
        user_data = user_override

    GoalList.delete_all_goals(user_data)

    return "Goals deleted"


@route("/api/v1/avatars", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_avatars():
    """ Returns the list of all avatars bucketed by categories.
    If this is an authenticated request and user-info is available, the
    avatars will be annotated with whether or not they're available.
    """
    user_data = user_models.UserData.current()
    result = util_avatars.avatars_by_category()
    if user_data:
        for category in result:
            for avatar in category['avatars']:
                avatar.is_available = avatar.is_satisfied_by(user_data)
    return result


@route("/api/v1/dev/version", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_version_id():
    version_id = None
    if 'CURRENT_VERSION_ID' in os.environ:
        version_id = os.environ['CURRENT_VERSION_ID']
    return {'version_id': version_id}


@route("/api/v1/dev/videorec_matrix", methods=["POST"])
@api.auth.decorators.developer_required
@jsonp
@jsonify
def update_video_recommendation_matrix():
    matrix_data = json.loads(request.request_string('data'))
    # TODO(benkomalo): actually store in DB once model is fleshed out
    logging.error(matrix_data)


#{
#            "timestamp": "2013-02-12 13:34:24+00:00",
#                "object": {
#                            "definition": {
#                                            "type": "media",
#                                                        "name": {
#                                                                            "en-US": "Js Tetris - Tin Can Prototype"
#                                                                                        },
#                                                                    "description": {
#                                                                                        "en-US": "A game of tetris."
#                                                                                                    }
#                                                                            },
#                                    "id": "adlnet.gov/JsTetris_TCAPI",
#                                            "objectType": "Activity"
#                                                },
#                    "actor": {
#                                "mbox": "mailto:sergio@perceptum.nl",
#                                        "name": "sergio",
#                                                "objectType": "Agent"
#                                                    },
#                        "voided": false,
#                            "stored": "2013-02-12 13:34:24+00:00",
#                                "verb": {
#                                            "id": "http://adlnet.gov/xapi/verbs/attempted",
#                                                    "display": {
#                                                                    "en-US": "started"
#                                                                            }
#                                                        },
#                                    "authority": {
#                                                "mbox": "sergio@perceptum.nl",
#                                                        "name": "sergio",
#                                                                "objectType": "Agent"
#                                                                    },
#                                        "context": {
#                                                    "contextActivities": {
#                                                                    "grouping": {
#                                                                                        "id": "adlnet.gov/JsTetris_TCAPI"
#                                                                                                    }
#                                                                            },
#                                                            "registration": "1200c45f-feb5-4724-bf21-49b71cfcb330"
#                                                                },
#                                            "id": "a1a7511c-927b-409c-906b-c4c2ecf122f3"
#                                            }
@route("/api/v1/lrs", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
@jsonify
def get_lrs():
    #user_data = request.request_student_user_data()
    email = "jaime@example.com"
    username = "jaime"
    user_data = user_models.UserData.all().filter("user_email = ", email).fetch(1)[0]
    problem_log_query = exercise_models.ProblemLog.all()
    problem_log_query.filter("user =", user_data.user)
    problems = problem_log_query.fetch(99999)
    activity = []
    for problem in problems:
        time_done = datetime.datetime.strptime("2013-02-14T12:52:51Z", "%Y-%m-%dT%H:%M:%SZ")
        start_time = time_done - datetime.timedelta(0, problem.time_taken)

        entry = {
                    "timestamp" : start_time,
                    "object" : {
                        "definition": {
                            "type": "media",
                            "name": {
                                "en-US": "Khan Academie",
                                "description": {
                                   "en-US": problem.exercise
                                }
                            },
                            "id": "adlnet.gov/KhanAcademie_TCAPI",
                            "objectType": "Activity"
                        },
                        "actor": {
                            "mbox": "mailto:%s" % email,
                            "name": username,
                            "objectType": "Agent"
                        },
                        "voided": False,
                        "stored": start_time,
                        "verb": {
                            "id": "http://adlnet.gov/xapi/verbs/attempted",
                            "display": {
                                "en-US": "started"
                            }
                        },
                        "verb": {
                        	"id": "http://adlnet.gov/xapi/verbs/passed"
							"number_attemps" : problem.count_hints,
                            "display": {
                                "en-US": "passed"
                             }
                        },
                        "result": {
                        	"score": {
                            	"raw": 726,
                                 "min": 0
                                 },
                                 "extensions": {
                                 "time": "4",
                                 "lines": "0",
                                 "apm": "1680"
                                 }
                            },
                       #---- oto verbo

                      # "verb": {
                      #             "id": "http://adlnet.gov/xapi/verbs/completed",
                      #                     "display": {
                      #                                     "en-US": "finished"
                      #                                             }
                      #                         },
                      #     "result": {
                      #                     "score": {
                      #                                     "raw": 740,
                      #                                                 "min": 0
                      #                                                         },
                      #                             "extensions": {
                      #                                             "level": "2",
                      #                                                         "time": "4",
                      #                                                                     "lines": "0",
                      #                                                                                 "apm": "1680"
                      #                                                                                         }
                      #                                 },

                        "authority": {
                            "mbox": email,
                            "name": username,
                            "objectType": "Agent"
                        },
                        "context": {
                            "contextActivities": {
                                "grouping": {
                                    "id": "adlnet.gov/KhanAcademie_TCAPI"
                                }
                            },
                            "registration": "1200c45f-feb5-4724-bf21-49b71cfcb330"
                        },
                        "id": "a1a7511c-927b-409c-906b-c4c2ecf122f3"
                    }
                }
        activity.append(entry)
    return activity


