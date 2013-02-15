# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

from google.appengine.ext import db

import layer_cache
import logging
import object_property
import topic_models
import urllib2
from api import jsonify

NUM_SUGGESTED_TOPICS = 2


def update_from_live(edit_version):
    """ imports the latest version of the knowledgemap layout from the live
    site into the edit_version
    """
    logging.info("importing knowledge map layout")
    request = urllib2.Request("http://www.khanacademie.nl/api/v1/maplayout")
    try:
        opener = urllib2.build_opener()
        f = opener.open(request)
        map_layout_live = json.load(f)

    except urllib2.URLError:
        logging.exception("Failed to fetch knowledgemap layout from "
                          "khanacademy.org")

    map_layout = MapLayout.get_for_version(edit_version)
    map_layout.layout = map_layout_live
    map_layout.put()
    logging.info("finished putting knowledge map layout")


def topics_layout(user_data, user_exercise_graph):
    """ Return topics layout data with per-user topic completion
    and suggested info already filled in.
    """

    version = topic_models.TopicVersion.get_default_version()
    topics = topic_models.Topic.get_visible_topics(version)
    layout = MapLayout.get_for_version(version).layout
    logging.info("Loading topics layout for version %d" % version.number)

    if not layout:
        raise Exception("Missing map layout for default topic version")

    # Build each topic's completion/suggested status from constituent exercises
    for topic in topics:

        topic_dict = layout["topics"].get(topic.id, None)

        if not topic_dict:
            # Map layout doesn't know about this topic -- skip
            continue

        badge = topic.get_exercise_badge()

        if not badge:
            # Missing TopicExerciseBadge for this topic -- skip
            logging.error("Missing topic exercise badge for topic: %s" %
                    topic.id)
            continue

        proficient, suggested, total = (0, 0, 0)

        for exercise_name in badge.exercise_names_required:
            graph_dict = user_exercise_graph.graph_dict(exercise_name)

            total += 1
            if graph_dict["proficient"]:
                proficient += 1
            if graph_dict["suggested"]:
                suggested += 1

        # Send down the number of suggested exercises as well as
        # the ratio of constituent exercises completed:total
        topic_dict["count_suggested"] = suggested
        topic_dict["count_proficient"] = proficient
        topic_dict["total"] = total

        # Send down proficiency status and badge icon
        if proficient >= total:
            topic_dict["status"] = "proficient"
            topic_dict["icon_url"] = badge.completed_icon_src
        else:
            topic_dict["icon_url"] = badge.icon_src

    # Pick the two "most suggested" topics and highlight them as suggested.
    # "Most suggested" is defined as having the highest number of suggested
    # constituent exercises.
    suggested_candidates = sorted(
            layout["topics"].values(),
            key=lambda t: t.get("count_suggested", 0),
            reverse=True)[:NUM_SUGGESTED_TOPICS]

    for topic_dict in suggested_candidates:
        topic_dict["suggested"] = True

    return layout


class MapLayout(db.Model):
    """ Keep track of topic layout and polyline paths for knowledge
    map rendering.

    TODO: in the future, this can hold the layout for exercises
    and perhaps all sorts of zones of the knowledge map."""

    version = db.ReferenceProperty(indexed=False, required=True)
    layout = object_property.UnvalidatedObjectProperty()

    @property
    def id(self):
        return self.key().name()

    @staticmethod
    def key_for_version(version):
        if(version):
            return "maplayout:%s" % version.number
        else:
            return "maplayout:1"

    @staticmethod
    def from_version(version=None):
        if version == None:
            version = topic_models.TopicVersion.get_edit_version()

        root = topic_models.Topic.get_root(version)
        tree = jsonify.dumps(root.make_tree(["Topics"]))
        #XXX invi: hardcoded math topic for NL version
        # it's needed an option to select the subtopic to create a Map Layout
        subtopics = tree['children'][0]['children']

        #TODO check positions for collitions
        layout_topics = {}
        for topic in subtopics:
            data = {
                    "icon_url" : topic['icon_url'],
                    "id" : topic['id'],
                    "x" :  str(topic['h_position']),
                    "y" :  str(topic['v_position']),
                    "standalone_title" : topic['standalone_title']
            }
            layout_topics[topic['standalone_title']] = data

        layout = {"polylines": [], "topics": layout_topics}
        return layout

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda version: MapLayout.key_for_version(version),
        layer=layer_cache.Layers.Memcache)
    def get_for_version(version):
        #occurs when no previous version
        if version == None:
            return None

        key = MapLayout.key_for_version(version)
        map_layout = MapLayout.get_by_key_name(key)

        if not map_layout:
            logging.info("Creating empty Map Layout")
            map_layout = MapLayout(
                    key_name=key,
                    version=version,
                    layout=None
            )

        return map_layout

    def put(self):
        db.Model.put(self)

        # After a MapLayout put we need to bust any memcached version
        MapLayout.get_for_version(self.version, bust_cache=True)

    @property
    def has_layout(self):
        return bool(self.layout)
