"""Holds Topic, UserTopic, TopicVersion, and VersionContentChange

Topic: database entity reflecting a collection of videos into a group;
   topics can also include sub-topics
UserTopic: database entity holding a single user's interaction with a topic
TopicVersion: database entity holding information about a single version
   of a topic-tree.  A topic tree (collection of topics and sub-topics
   starting from the 'root of all knowledge' topic) is versioned; each
   version is entirely independent.
VersionContentChange: database entity holding changes that are to be
   applied to a topic tree.

A 'topic' the stuff after the # in urls like
   http://www.khanacademy.org/#chemistry
"""

import base64
import datetime
import logging
import os
import re

from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.ext import deferred

from api import jsonify
import app
import autocomplete
import backup_model
import badges
import decorators
import exercise_video_model
import exercise_models
import handlebars.render
from knowledgemap import layout
import layer_cache
import library
import object_property
import pickle_util
import request_cache
from third_party import search
import setting_model
import templatetags
import transaction_util
import url_model
import url_util
import user_models
import util
import video_models
import urllib2
# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

class TopicVersion(backup_model.BackupModel):
    """Metadata describing a particular version of the topic-tree data."""
    created_on = db.DateTimeProperty(indexed=False, auto_now_add=True)
    updated_on = db.DateTimeProperty(indexed=False, auto_now=True)
    made_default_on = db.DateTimeProperty(indexed=False)
    copied_from = db.SelfReferenceProperty(indexed=False)
    last_edited_by = db.UserProperty(indexed=False)
    number = db.IntegerProperty(required=True)
    title = db.StringProperty(indexed=False)
    description = db.StringProperty(indexed=False)
    default = db.BooleanProperty(default=False)
    edit = db.BooleanProperty(default=False)

    _serialize_blacklist = ["copied_from"]

    @property
    def copied_from_number(self):
        if self.copied_from:
            return self.copied_from.number

    @staticmethod
    def get_by_id(version_id):
        if version_id is None or version_id == "default":
            return TopicVersion.get_default_version()
        if version_id == "edit":
            return TopicVersion.get_edit_version()
        number = int(version_id)
        return TopicVersion.all().filter("number =", number).get()

    @staticmethod
    def get_by_number(number):
        return TopicVersion.all().filter("number =", number).get()

    @staticmethod
    @layer_cache.cache_with_key_fxn(lambda:
        "TopicVersion.get_all_content_keys_%s" %
        setting_model.Setting.cached_content_add_date())
    def get_all_content_keys():
        ''' used to make get_unused_content_quicker.  The cache will only
        update when new content is added '''
        video_keys = video_models.Video.all(keys_only=True).fetch(100000)
        exercise_keys = (exercise_models.Exercise.all_unsafe(keys_only=True).
                         fetch(100000))
        url_keys = url_model.Url.all(keys_only=True).fetch(100000)

        content = video_keys
        content.extend(exercise_keys)
        content.extend(url_keys)
        return content

    def get_unused_content(self):
        topics = Topic.all().filter("version =", self).run()
        used_content_keys = set()
        for t in topics:
            used_content_keys.update([c for c in t.child_keys
                                      if c.kind() != "Topic"])

        content_keys = set(TopicVersion.get_all_content_keys())

        return db.get(content_keys - used_content_keys)

    @staticmethod
    def get_latest_version():
        return TopicVersion.all().order("-number").get()

    @staticmethod
    def get_latest_version_number():
        latest_version = TopicVersion.all().order("-number").get()
        return latest_version.number if latest_version else 0

    @staticmethod
    def create_new_version():
        new_version_number = TopicVersion.get_latest_version_number() + 1
        if user_models.UserData.current():
            last_edited_by = user_models.UserData.current().user
        else:
            last_edited_by = None
        new_version = TopicVersion(last_edited_by=last_edited_by,
                                   number=new_version_number)
        new_version.put()
        return new_version

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda *args, **kwargs: "topic_models_default_version_%s" %
            setting_model.Setting.topic_tree_version())
    def get_default_version():
        return TopicVersion.all().filter("default = ", True).get()

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda *args, **kwargs: "topic_models_edit_version_%s" %
            setting_model.Setting.topic_tree_version())
    def get_edit_version():
        return TopicVersion.all().filter("edit = ", True).get()

    @staticmethod
    @decorators.synchronized_with_memcache(
        timeout=300)  # takes 70secs on dev 03/2012
    def create_edit_version():
        version = TopicVersion.all().filter("edit = ", True).get()
        if version is None:
            default = TopicVersion.get_default_version()
            version = default.copy_version()
            version.edit = True
            version.put()
            return version
        else:
            logging.warning("Edit version already exists")
            return False

    def copy_version(self):
        version = TopicVersion.create_new_version()

        old_root = Topic.get_root(self)
        old_tree = old_root.make_tree(types=["Topics"], include_hidden=True)
        TopicVersion.copy_tree(old_tree, version)

        version.copied_from = self
        version.put()

        return version

    @staticmethod
    def copy_tree(old_tree, new_version, new_root=None, parent=None):
        parent_keys = []
        ancestor_keys = []
        if parent:
            parent_keys = [parent.key()]
            ancestor_keys = parent_keys[:]
            ancestor_keys.extend(parent.ancestor_keys)

        if new_root:
            key_name = old_tree.key().name()
        else:
            # don't copy key_name of root as it is parentless, and
            # needs its own key
            key_name = Topic.get_new_key_name()

        new_tree = util.clone_entity(old_tree,
                                     key_name=key_name,
                                     version=new_version,
                                     parent=new_root,
                                     parent_keys=parent_keys,
                                     ancestor_keys=ancestor_keys)
        new_tree.put()
        if not new_root:
            new_root = new_tree

        old_key_new_key_dict = {}
        for child in old_tree.children:
            old_key_new_key_dict[child.key()] = TopicVersion.copy_tree(
                child, new_version, new_root, new_tree).key()

        new_tree.child_keys = [c if c not in old_key_new_key_dict
                               else old_key_new_key_dict[c]
                               for c in old_tree.child_keys]
        new_tree.put()
        return new_tree

    def update(self):
        if user_models.UserData.current():
            last_edited_by = user_models.UserData.current().user
        else:
            last_edited_by = None
        self.last_edited_by = last_edited_by
        self.put()

    def find_content_problems(self):
        logging.info("checking for problems")
        version = self

        # find exercises that are overlapping on the knowledge map
        logging.info("checking for exercises that are overlapping on the "
                     "knowledge map")
        exercises = exercise_models.Exercise.all()
        exercise_dict = dict((e.key(), e) for e in exercises)

        location_dict = {}
        duplicate_positions = list()
        changes = VersionContentChange.get_updated_content_dict(version)
        exercise_changes = dict((k, v) for k, v in changes.iteritems()
                                if v.key() in exercise_dict)
        exercise_dict.update(exercise_changes)

        for exercise in [e for e in exercise_dict.values()
                         if e.live and not e.summative]:

            if exercise.h_position not in location_dict:
                location_dict[exercise.h_position] = {}

            if exercise.v_position in location_dict[exercise.h_position]:
                location_dict[exercise.h_position][exercise.v_position].append(
                    exercise)
                duplicate_positions.append(
                    location_dict[exercise.h_position][exercise.v_position])
            else:
                location_dict[exercise.h_position][exercise.v_position] = \
                    [exercise]

        # find videos whose duration is 0
        logging.info("checking for videos with 0 duration")
        zero_duration_videos = (video_models.Video.all()
                                .filter("duration =", 0)
                                .fetch(10000))
        zero_duration_dict = dict((v.key(), v) for v in zero_duration_videos)
        video_changes = dict((k, v) for k, v in changes.iteritems()
                             if k in zero_duration_dict or
                             (type(v) == video_models.Video and
                              v.duration == 0))
        zero_duration_dict.update(video_changes)
        zero_duration_videos = [v for v in zero_duration_dict.values()
                                if v.duration == 0]

        # find videos with invalid youtube_ids that would be marked live
        logging.info("checking for videos with invalid youtube_ids")
        root = Topic.get_root(version)
        videos = root.get_videos(include_descendants=True)
        bad_videos = []
        for video in videos:
            if re.search("_DUP_\d*$", video.youtube_id):
                bad_videos.append(video)
        db.delete(exercise_video_model.ExerciseVideo
                 .get_all_with_topicless_videos(version))
        problems = {
            "ExerciseVideos with topicless videos":
                (exercise_video_model.ExerciseVideo
                 .get_all_with_topicless_videos(version)),
            "Exercises with colliding positions": list(duplicate_positions),
            "Zero duration videos": zero_duration_videos,
            "Videos with bad youtube_ids": bad_videos}

        return problems

    def set_default_version(self):
        logging.info("starting set_default_version")
        setting_model.Setting.topic_admin_task_message("Publish: started")
        run_code = base64.urlsafe_b64encode(os.urandom(30))
        _do_set_default_deferred_step(_check_for_problems,
                                      self.number,
                                      run_code)


class Topic(search.Searchable, backup_model.BackupModel):
    """Information about a single topic (set of videos and sub-topics)."""
    # title used when viewing topic in a tree structure
    title = db.StringProperty(required=True)

    # title used when on its own
    standalone_title = db.StringProperty()

    # this is the slug, or readable_id - the one used to refer to the
    # topic in urls and in the api
    id = db.StringProperty(required=True)
    
    # this is the URI path for this topic, i.e. "math/algebra"
    extended_slug = db.StringProperty(indexed=False)

    description = db.TextProperty(indexed=False)
    
    # to be able to access the parent without having to resort to a
    # query - parent_keys is used to be able to hold more than one
    # parent if we ever want that
    parent_keys = db.ListProperty(db.Key)

    # to be able to quickly get all descendants
    ancestor_keys = db.ListProperty(db.Key)

    # having this avoids having to modify Content entities
    child_keys = db.ListProperty(db.Key)

    version = db.ReferenceProperty(TopicVersion, required=True)
    tags = db.StringListProperty()
    hide = db.BooleanProperty(default=False)
    created_on = db.DateTimeProperty(indexed=False, auto_now_add=True)
    updated_on = db.DateTimeProperty(indexed=False, auto_now=True)
    last_edited_by = db.UserProperty(indexed=False)
    INDEX_ONLY = ['standalone_title', 'description']
    INDEX_TITLE_FROM_PROP = 'standalone_title'
    INDEX_USES_MULTI_ENTITIES = False

    _serialize_blacklist = ["child_keys", "version", "parent_keys",
                            "ancestor_keys", "created_on", "updated_on",
                            "last_edited_by"]
    # the ids of the topic on the homepage in which we will display their first
    # level child topics
    _super_topic_ids = ["algebra", "arithmetic", "art-history", "geometry", 
                        "brit-cruise", "california-standards-test", "gmat",
                        "linear-algebra"]

    @property
    def relative_url(self):
        return '/#%s' % self.id

    @property
    def topic_page_url(self):
        return '/%s' % self.get_extended_slug()

    @property
    def ka_url(self):
        return url_util.absolute_url(self.relative_url)

    def get_visible_data(self, node_dict=None):
        if node_dict:
            children = [node_dict[c] for c in self.child_keys
                        if c in node_dict]
        else:
            children = db.get(self.child_keys)

        if not self.version.default:
            updates = VersionContentChange.get_updated_content_dict(
                self.version)
            children = [c if c.key() not in updates else updates[c.key()]
                        for c in children]

        self.children = []
        for child in children:
            self.children.append({
                "kind": child.__class__.__name__,
                "id": getattr(child, "id",
                              getattr(child, "readable_id",
                                      getattr(child, "name",
                                              child.key().id()))),
                "title": getattr(child, "title",
                                 getattr(child, "display_name", "")),
                "hide": getattr(child, "hide", False),
                "url": getattr(child, "ka_url", getattr(child, "url", ""))
                })
        return self

    def get_library_data(self, node_dict=None):
        from homepage import thumbnail_link_dict

        if node_dict:
            children = [node_dict[c] for c in self.child_keys
                        if c in node_dict]
        else:
            children = db.get(self.child_keys)

        (thumbnail_video, thumbnail_topic) = self.get_first_video_and_topic()

        ret = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "children": [{
                "url": "/%s/v/%s" % (self.get_extended_slug(), v.readable_id),
                "key_id": v.key().id(),
                "title": v.title
            } for v in children if v.__class__.__name__ == "Video"],
            "child_count": len([v for v in children
                                if v.__class__.__name__ == "Video"]),
            "thumbnail_link": thumbnail_link_dict(
                video=thumbnail_video, parent_topic=thumbnail_topic),
        }

        return ret

    @layer_cache.cache_with_key_fxn(lambda self:
        "topic_get_topic_page_data_%s_v3" % self.key(),
        persist_across_app_versions=True,
        layer=(layer_cache.Layers.InAppMemory |
               layer_cache.Layers.Memcache |
               layer_cache.Layers.Datastore))
    def get_topic_page_data(self):
        from homepage import thumbnail_link_dict

        (marquee_video, subtopic) = self.get_first_video_and_topic()

        self.make_tree(types=["Video"])

        # If there are child videos, child topics are ignored.
        # There is no support for mixed topic/video containers.
        video_child_keys = [v for v in self.child_keys if v.kind() == "Video"]
        if not video_child_keys:
            # Fetch child topics
            topic_child_keys = [t for t in self.child_keys
                                if t.kind() == "Topic"]
            topic_children = filter(
                lambda t: t.has_children_of_type(["Video"]),
                db.get(topic_child_keys))

            # Fetch the descendent videos
            node_keys = []
            for subtopic in topic_children:
                videos = filter(lambda v: v.kind() == "Video",
                                subtopic.child_keys)
                if videos:
                    node_keys.extend(videos)

            nodes = db.get(node_keys)
            node_dict = dict((node.key(), node) for node in nodes)

            # Get the subtopic video data
            subtopics = [t.get_library_data(node_dict=node_dict)
                         for t in topic_children]
            child_videos = None
        else:
            # Fetch the child videos
            nodes = db.get(video_child_keys)
            node_dict = dict((node.key(), node) for node in nodes)

            # Get the topic video data
            subtopics = None
            child_videos = self.get_library_data(node_dict=node_dict)

        topic_info = {
            "topic": jsonify.dumps(self),
            "marquee_video": thumbnail_link_dict(video=marquee_video,
                                                 parent_topic=subtopic),
            "subtopics": subtopics,
            "child_videos": child_videos,
            "extended_slug": self.get_extended_slug(),
        }

        return topic_info

    @layer_cache.cache_with_key_fxn(lambda self:
        "topic_get_topic_page_json_%s_v3" % self.key(),
        persist_across_app_versions=True,
        layer=(layer_cache.Layers.InAppMemory |
               layer_cache.Layers.Memcache |
               layer_cache.Layers.Datastore))
    def get_topic_page_json(self):
        topic_info = self.get_topic_page_data()
        return jsonify.jsonify(topic_info, camel_cased=False)

    @layer_cache.cache_with_key_fxn(lambda self:
        "topic_get_topic_page_html_%s_v3" % self.key(),
        persist_across_app_versions=True,
        layer=(layer_cache.Layers.InAppMemory |
               layer_cache.Layers.Memcache |
               layer_cache.Layers.Datastore))
    def get_topic_page_html(self):
        main_topic = self
        if self.parent_keys:
            parent_topic = db.get(self.parent_keys[0])
        else:
            parent_topic = main_topic

        # If the parent is a supertopic, use that instead
        if parent_topic.id in Topic._super_topic_ids:
            main_topic = parent_topic

        topic_info = main_topic.get_topic_page_data()

        if self == main_topic:
            if topic_info["child_videos"]:
                topic_child_videos = topic_info["child_videos"]["children"]
                list_length = int((len(topic_child_videos) + 1) / 2)
                children_col1 = topic_child_videos[0:list_length]
                children_col2 = topic_child_videos[list_length:]

                html = handlebars.render.handlebars_template(
                    "topic", "content-topic-videos",
                    {
                        "topic": topic_info["child_videos"],
                        "childrenCol1": children_col1,
                        "childrenCol2": children_col2,
                    })
            else:
                list_length = int((len(topic_info["subtopics"]) + 1) / 2)
                children_col1 = topic_info["subtopics"][0:list_length]
                children_col2 = topic_info["subtopics"][list_length:]

                for subtopic in topic_info["subtopics"]:
                    subtopic["description_truncate_length"] = (
                        38 if len(subtopic["title"]) > 28 else 68)

                html = handlebars.render.handlebars_template(
                    "topic", "root-topic-view",
                    {
                        "topic_info": topic_info,
                        "subtopicsA": children_col1,
                        "subtopicsB": children_col2,
                    })
        elif topic_info["subtopics"]:
            subtopic = [t for t in topic_info["subtopics"]
                        if t["id"] == self.id]
            if subtopic:
                subtopic = subtopic[0]

                list_length = int((len(subtopic["children"]) + 1) / 2)
                children_col1 = subtopic["children"][0:list_length]
                children_col2 = subtopic["children"][list_length:]

                html = handlebars.render.handlebars_template(
                    "topic", "content-topic-videos",
                    {
                        "topic": subtopic,
                        "childrenCol1": children_col1,
                        "childrenCol2": children_col2,
                    })
            else:
                logging.info("Skipping hidden subtopic: %s" %
                             self.standalone_title)
                html = ""
        else:
            logging.info("Skipping hidden subtopic: %s" %
                         self.standalone_title)
            html = ""

        return html

    @layer_cache.cache_with_key_fxn(lambda self:
        "topic_get_topic_page_nav_html_%s_v3" % self.key(),
        persist_across_app_versions=True,
        layer=(layer_cache.Layers.InAppMemory |
               layer_cache.Layers.Memcache |
               layer_cache.Layers.Datastore))
    def get_topic_page_nav_html(self):
        main_topic = self
        if self.parent_keys:
            parent_topic = db.get(self.parent_keys[0])
        else:
            parent_topic = main_topic

        # If the parent is a supertopic, use that instead
        if parent_topic.id in Topic._super_topic_ids:
            main_topic = parent_topic

        topic_info = main_topic.get_topic_page_data()

        html = handlebars.render.handlebars_template("topic", "subtopic-nav", {
            "topic_info": topic_info,
        })

        return html

    def get_child_order(self, child_key):
        return self.child_keys.index(child_key)

    def has_content(self):
        for child_key in self.child_keys:
            if child_key.kind() != "Topic":
                return True
        return False

    def has_children_of_type(self, types):
        """ Return true if this Topic has at least one child of
        any of the passed in types.

        Types should be an array of type strings:
            has_children_of_type(["Topic", "Video"])
        """
        return any(child_key.kind() in types for child_key in self.child_keys)

    # Gets the slug path of this topic, including parents,
    # i.e. math/arithmetic/fractions
    def get_extended_slug(self, bust_cache=False):
        if self.extended_slug and not bust_cache:
            return self.extended_slug

        parent_ids = [topic.id for topic in db.get(self.ancestor_keys)]
        parent_ids.reverse()
        if len(parent_ids) > 1:
            slug = "%s/%s" % ('/'.join(parent_ids[1:]), self.id)
        else:
            slug = self.id

        self.extended_slug = slug
        self.put()

        return slug

    # Gets the data we need for the video player
    @layer_cache.cache_with_key_fxn(lambda self:
        "topic_get_play_data_%s" % self.key(),
        layer=layer_cache.Layers.Memcache)
    def get_play_data(self):

        # Find last video in the previous topic
        previous_video = None
        previous_video_topic = None
        previous_topic = self

        while not previous_video:
            previous_topic = previous_topic.get_previous_topic()
            # Don't iterate past the end of the current top-level topic
            if previous_topic and len(previous_topic.ancestor_keys) > 1:
                (previous_video, previous_video_topic) = (
                    previous_topic.get_last_video_and_topic())
            else:
                break

        # Find first video in the next topic
        next_video = None
        next_video_topic = None
        next_topic = self

        while not next_video:
            next_topic = next_topic.get_next_topic()
            # Don't iterate past the end of the current top-level topic
            if next_topic and len(next_topic.ancestor_keys) > 1:
                (next_video, next_video_topic) = (
                    next_topic.get_first_video_and_topic())
            else:
                break

        # List all the videos in this topic
        videos_dict = [{
            "readable_id": v.readable_id,
            "key_id": v.key().id(),
            "title": v.title
        } for v in Topic.get_cached_videos_for_topic(self)]

        ancestor_topics = [{
            "title": topic.title, 
            "url": (topic.topic_page_url if topic.id in Topic._super_topic_ids 
                    or topic.has_content() else None)
            }
            for topic in db.get(self.ancestor_keys)][0:-1]
        ancestor_topics.reverse()

        return {
            'id': self.id,
            'title': self.title,
            'url': self.topic_page_url,
            'extended_slug': self.get_extended_slug(),
            'ancestor_topics': ancestor_topics,
            'top_level_topic': (db.get(self.ancestor_keys[-2]).id
                                if len(self.ancestor_keys) > 1
                                else self.id),
            'videos': videos_dict,
            'previous_topic_title': (previous_topic.standalone_title
                                     if previous_topic else None),
            'previous_topic_video': (previous_video.readable_id
                                     if previous_video else None),
            'previous_topic_subtopic_slug': (
                    previous_video_topic.get_extended_slug()
                    if previous_video_topic else None),
            'next_topic_title': (next_topic.standalone_title
                                 if next_topic else None),
            'next_topic_video': (next_video.readable_id
                                 if next_video else None),
            'next_topic_subtopic_slug': (next_video_topic.get_extended_slug()
                                         if next_video_topic else None)
        }

    # get the topic by the url slug/readable_id
    @staticmethod
    def get_by_id(id, version=None):
        if version is None:
            version = TopicVersion.get_default_version()
            if version is None:
                logging.info("No default version has been set, getting latest "
                             "version instead")
                version = TopicVersion.get_latest_version()

        return (Topic.all()
                .filter("id =", id)
                .filter("version =", version)
                .get())

    # title is not necessarily unique - this function is needed for
    # the old playl1st api to return a best guess
    @staticmethod
    def get_by_title(title, version=None):
        if version is None:
            version = TopicVersion.get_default_version()
            if version is None:
                logging.info("No default version has been set, getting latest "
                             "version instead")
                version = TopicVersion.get_latest_version()

        return (Topic.all()
                .filter("title =", title)
                .filter("version =", version)
                .get())

    @staticmethod
    # parent specifies version
    def get_by_title_and_parent(title, parent):
        return (Topic.all()
                .filter("title =", title)
                .filter("parent_keys =", parent.key())
                .get())

    @staticmethod
    def get_root(version=None):
        if not version:
            version = TopicVersion.get_default_version()
        return (Topic.all()
                .filter('id =', 'root')
                .filter('version =', version)
                .get())

    @staticmethod
    def get_new_id(parent, title, version):
        potential_id = title.lower()
        potential_id = re.sub('[^a-z0-9]', '-', potential_id)
        # remove any trailing dashes (see issue 1140)
        potential_id = re.sub('-+$', '', potential_id)
        # remove any leading dashes (see issue 1526)
        potential_id = re.sub('^-+', '', potential_id)

        if potential_id[0].isdigit():
            potential_id = parent.id + "-" + potential_id

        number_to_add = 0
        current_id = potential_id
        while True:
            # need to make this an ancestor query to make sure that it
            # can be used within transactions
            matching_topic = (Topic.all()
                              .filter('id =', current_id)
                              .filter('version =', version)
                              .get())

            if matching_topic is None:  # id is unique so use it and break out
                return current_id
            else:  # id is not unique so will have to go through loop again
                number_to_add += 1
                current_id = '%s-%s' % (potential_id, number_to_add)

    @staticmethod
    def get_new_key_name():
        return base64.urlsafe_b64encode(os.urandom(30))

    @layer_cache.cache_with_key_fxn(lambda self:
        "topic_get_previous_topic_%s_v%s" % (
            self.key(), setting_model.Setting.topic_tree_version()),
        layer=layer_cache.Layers.Memcache)
    def get_previous_topic(self):
        if self.parent_keys:
            parent_topic = db.get(self.parent_keys[0])
            prev_index = parent_topic.child_keys.index(self.key()) - 1

            while prev_index >= 0:
                prev_topic = db.get(parent_topic.child_keys[prev_index])
                if not prev_topic.hide:
                    return prev_topic

                prev_index -= 1

            return parent_topic.get_previous_topic()

        return None

    @layer_cache.cache_with_key_fxn(lambda self:
        "topic_get_next_topic_%s_v%s" % (
            self.key(), setting_model.Setting.topic_tree_version()),
        layer=layer_cache.Layers.Memcache)
    def get_next_topic(self):
        if self.parent_keys:
            parent_topic = db.get(self.parent_keys[0])
            next_index = parent_topic.child_keys.index(self.key()) + 1

            while next_index < len(parent_topic.child_keys):
                next_topic = db.get(parent_topic.child_keys[next_index])
                if not next_topic.hide:
                    return next_topic

                next_index += 1

            return parent_topic.get_next_topic()

        return None

    @layer_cache.cache_with_key_fxn(lambda self:
        "topic_get_first_video_%s_v%s" % (
            self.key(), setting_model.Setting.topic_tree_version()),
        layer=layer_cache.Layers.Memcache)
    def get_first_video_and_topic(self):
        videos = Topic.get_cached_videos_for_topic(self)
        if videos:
            return (videos[0], self)

        for key in self.child_keys:
            if key.kind() == 'Topic':
                topic = db.get(key)
                if not topic.hide:
                    ret = topic.get_first_video_and_topic()
                    if ret != (None, None):
                        return ret

        return (None, None)

    @layer_cache.cache_with_key_fxn(lambda self:
        "topic_get_last_video_%s_v%s" % (
            self.key(), setting_model.Setting.topic_tree_version()),
        layer=layer_cache.Layers.Memcache)
    def get_last_video_and_topic(self):
        videos = Topic.get_cached_videos_for_topic(self)
        if videos:
            return (videos[-1], self)

        for key in reversed(self.child_keys):
            if key.kind() == 'Topic':
                topic = db.get(key)
                if not topic.hide:
                    ret = topic.get_last_video_and_topic()
                    if ret != (None, None):
                        return ret

        return (None, None)

    def update_ancestor_keys(self, topic_dict=None):
        """Update the ancestor_keys by using the parents' ancestor_keys.

        Furthermore updates the ancestors of all the descendants.
        
        Returns:
            The list of entities updated. Note that they still need to be put
            into the datastore.
        """

        # topic_dict keeps a dict of all descendants and all parent's
        # of those descendants so we don't have to get them from the
        # datastore again
        if topic_dict is None:
            descendants = Topic.all().filter("ancestor_key =", self)
            topic_dict = dict((d.key(), d) for d in descendants)
            topic_dict[self.key()] = self

            # as topics in the tree may have more than one parent we
            # need to add their other parents to the dict
            unknown_parent_dict = {}
            for topic_key, topic in topic_dict.iteritems():
                # add each parent_key that is not already in the
                # topic_dict to the unknown_parents that we still need
                # to get
                unknown_parent_dict.update(dict((p, True)
                                                for p in topic.parent_keys
                                                if p not in topic_dict))

            if unknown_parent_dict:
                # get the unknown parents from the database and then
                # update the topic_dict to include them
                unknown_parent_dict.update(
                    dict((p.key(), p)
                         for p in db.get(unknown_parent_dict.keys())))
                topic_dict.update(unknown_parent_dict)

        # calculate the new ancestor keys for self
        ancestor_keys = set()
        for parent_key in self.parent_keys:
            ancestor_keys.update(topic_dict[parent_key].ancestor_keys)
            ancestor_keys.add(parent_key)

        # update the ancestor_keys and keep track of the entity if we
        # have changed it
        changed_entities = set()
        if set(self.ancestor_keys) != ancestor_keys:
            self.ancestor_keys = list(ancestor_keys)
            changed_entities.add(self)

            # recursively look at the child entries and update their
            # ancestors, keeping track of which entities ancestors
            # changed
            for child_key in self.child_keys:
                if child_key.kind == "Topic":
                    child = topic_dict[child_key]
                    changed_entities.update(child.update_ancestors(topic_dict))

        return changed_entities

    def move_child(self, child, new_parent, new_parent_pos):
        if new_parent.version.default:
            raise Exception("You can't edit the default version")

        # remove the child
        old_index = self.child_keys.index(child.key())
        del self.child_keys[old_index]
        updated_entities = set([self])

        # check to make sure the new parent is different than the old one
        if new_parent.key() != self.key():
            # add the child to the new parent's children list
            new_parent.child_keys.insert(int(new_parent_pos), child.key())
            updated_entities.add(new_parent)

            if isinstance(child, Topic):
                # if the child is a topic make sure to update its parent list
                old_index = child.parent_keys.index(self.key())
                del child.parent_keys[old_index]
                child.parent_keys.append(new_parent.key())
                updated_entities.add(child)
                # now that the child's parent has changed, go to the
                # child all of the child's descendants and update
                # their ancestors
                updated_entities.update(child.update_ancestor_keys())

        else:
            # they are moving the item within the same node, so just
            # update self with the new position
            self.child_keys.insert(int(new_parent_pos), child.key())

        def move_txn():
            db.put(updated_entities)

        self.version.update()
        return transaction_util.ensure_in_transaction(move_txn)

    # Ungroup takes all of a topics children, moves them up a level, then
    # deletes the topic
    def ungroup(self):
        parent = db.get(self.parent_keys[0])
        pos = parent.child_keys.index(self.key())
        children = db.get(self.child_keys)
        for i, child in enumerate(children):
            self.move_child(child, parent, pos + i)
        parent.delete_child(self)

    def copy(self, title, parent=None, **kwargs):
        if "version" not in kwargs and parent is not None:
            kwargs["version"] = parent.version

        if kwargs["version"].default:
            raise Exception("You can't edit the default version")

        if self.parent():
            kwargs["parent"] = Topic.get_root(kwargs["version"])

        if "id" not in kwargs:
            kwargs["id"] = Topic.get_new_id(parent, title, kwargs["version"])

        kwargs["key_name"] = Topic.get_new_key_name()

        topic = Topic.get_by_key_name(kwargs["key_name"])
        if topic is not None:
            raise Exception("Trying to insert a topic with the duplicate "
                            "key_name '%s'" % kwargs["key_name"])

        kwargs["title"] = title
        kwargs["parent_keys"] = [parent.key()] if parent else []
        kwargs["ancestor_keys"] = kwargs["parent_keys"][:]
        kwargs["ancestor_keys"].extend(parent.ancestor_keys if parent else [])

        new_topic = util.clone_entity(self, **kwargs)

        return transaction_util.ensure_in_transaction(Topic._insert_txn,
                                                      new_topic)

    def add_child(self, child, pos=None):
        if self.version.default:
            raise Exception("You can't edit the default version")

        if child.key() in self.child_keys:
            raise Exception("The child %s already appears in %s" % (
                getattr(child, "id", getattr(child, "readable_id", 
                    getattr(child, "name", child.key().id()))), 
                self.title))

        if pos is None:
            self.child_keys.append(child.key())
        else:
            self.child_keys.insert(int(pos), child.key())

        entities_updated = set([self])

        if isinstance(child, Topic):
            child.parent_keys.append(self.key())
            entities_updated.add(child)
            entities_updated.update(child.update_ancestor_keys())

        def add_txn():
            db.put(entities_updated)

        self.version.update()
        return transaction_util.ensure_in_transaction(add_txn)

    def delete_child(self, child):
        if self.version.default:
            raise Exception("You can't edit the default version")

        # remove the child key from self
        self.child_keys = [c for c in self.child_keys if c != child.key()]

        # remove self from the child's parents
        if isinstance(child, Topic):
            child.parent_keys = [p for p in child.parent_keys
                                 if p != self.key()]
            num_parents = len(child.parent_keys)
            descendants = (Topic.all()
                           .filter("ancestor_keys =", child.key())
                           .fetch(10000))

            # if there are still other parents
            if num_parents:
                changed_descendants = child.update_ancestor_keys()
            else:
                #TODO: If the descendants still have other parents we
                #shouldn't be deleting them - if we are sure we want
                #multiple parents will need to implement this
                descendants.append(child)

        def delete_txn():
            self.put()
            if isinstance(child, Topic):
                if num_parents:
                    db.put(changed_descendants)
                else:
                    db.delete(descendants)

        self.version.update()
        transaction_util.ensure_in_transaction(delete_txn)

    def delete_tree(self):
        parents = db.get(self.parent_keys)
        for parent in parents:
            parent.delete_child(self)

    @staticmethod
    def _insert_txn(new_topic):
        new_topic.put()
        parents = db.get(new_topic.parent_keys)
        for parent in parents:
            parent.child_keys.append(new_topic.key())
            parent.put()

        if new_topic.child_keys:
            # Children should be added after the parent topic is
            # already added to the topic tree
            raise Exception("Should not insert a new topic with children into "
                            "the tree.")

        return new_topic

    @staticmethod
    def insert(title, parent=None, **kwargs):
        if "version" in kwargs:
            version = kwargs["version"]
            del kwargs["version"]
        else:
            if parent is not None:
                version = parent.version
            else:
                version = TopicVersion.get_edit_version()

        if version.default:
            raise Exception("You can't edit the default version")

        if "id" in kwargs and kwargs["id"]:
            id = kwargs["id"]
            del kwargs["id"]
        else:
            id = Topic.get_new_id(parent, title, version)
            logging.info("created a new id %s for %s" % (id, title))

        if "standalone_title" not in kwargs:
            kwargs["standalone_title"] = title

        key_name = Topic.get_new_key_name()

        topic = Topic.get_by_key_name(key_name)
        if topic is not None:
            raise Exception("Trying to insert a topic with the duplicate "
                            "key_name '%s'" % key_name)

        if parent:
            root = Topic.get_root(version)
            parent_keys = [parent.key()]
            ancestor_keys = parent_keys[:]
            ancestor_keys.extend(parent.ancestor_keys)

            new_topic = Topic(parent=root,  # setting the root to be the parent
                                            # so that inserts and deletes can
                                            # be done in a transaction
                              key_name=key_name,
                              version=version,
                              id=id,
                              title=title,
                              parent_keys=parent_keys,
                              ancestor_keys=ancestor_keys)

        else:
            root = Topic.get_root(version)

            new_topic = Topic(parent=root,
                              key_name=key_name,
                              version=version,
                              id=id,
                              title=title)

        for key in kwargs:
            setattr(new_topic, key, kwargs[key])

        version.update()
        return transaction_util.ensure_in_transaction(Topic._insert_txn,
                                                      new_topic)

    def update(self, **kwargs):
        if self.version.default:
            raise Exception("You can't edit the default version")

        if "put" in kwargs:
            put = kwargs["put"]
            del kwargs["put"]
        else:
            put = True

        changed = False
        if "id" in kwargs and kwargs["id"] != self.id:

            existing_topic = Topic.get_by_id(kwargs["id"], self.version)
            if not existing_topic:
                self.id = kwargs["id"]
                changed = True
            else:
                # don't allow people to change the slug to a different
                # nodes slug
                pass
            del kwargs["id"]

        for attr, value in kwargs.iteritems():
            if getattr(self, attr) != value:
                setattr(self, attr, value)
                changed = True

        if changed:
            if put:
                self.put()
                self.version.update()
            return self

    @layer_cache.cache_with_key_fxn(
    lambda self, types=[], include_hidden=False:
            "topic.make_tree_%s_%s_%s" % (
            self.key(), types, include_hidden),
            layer=layer_cache.Layers.Memcache)
    def make_tree(self, types=[], include_hidden=False):
        if include_hidden:
            nodes = Topic.all().filter("ancestor_keys =", self.key()).run()
        else:
            nodes = (Topic.all()
                     .filter("ancestor_keys =", self.key())
                     .filter("hide = ", False)
                     .run())

        node_dict = dict((node.key(), node) for node in nodes)
        # in case the current node is hidden (like root is)
        node_dict[self.key()] = self

        contentKeys = []
        # cycle through the nodes adding its children to the
        # contentKeys that need to be gotten
        for key, descendant in node_dict.iteritems():
            contentKeys.extend([c for c in descendant.child_keys
                                if c not in node_dict and
                                (c.kind() in types or
                                 (len(types) == 0 and c.kind() != "Topic"))])

        # get all content that belongs in this tree
        contentItems = db.get(contentKeys)
        content_dict = dict((content.key(), content)
                            for content in contentItems)

        if "Exercise" in types or len(types) == 0:
            evs = exercise_video_model.ExerciseVideo.all().fetch(10000)
            exercise_dict = dict((k, v) for k, v in content_dict.iteritems() if
                          (k.kind() == "Exercise"))
            video_dict = dict((k, v) for k, v in content_dict.iteritems() if
                          (k.kind() == "Video"))

            exercise_models.Exercise.add_related_video_readable_ids_prop(
                exercise_dict, evs, video_dict)

        # make any content changes for this version
        changes = VersionContentChange.get_updated_content_dict(self.version)
        type_changes = dict((k, c) for k, c in changes.iteritems() if
                       (k.kind() in types or len(types) == 0))
        content_dict.update(type_changes)

        node_dict.update(content_dict)

        # cycle through the nodes adding each to its parent's children list
        for key, descendant in node_dict.iteritems():
            if hasattr(descendant, "child_keys"):
                descendant.children = [node_dict[c]
                                       for c in descendant.child_keys
                                       if c in node_dict]

        # return the entity that was passed in, now with its children,
        # and its descendants children all added
        return node_dict[self.key()]

    def search_tree_traversal(self, query, node_dict, path, matching_paths,
                              matching_nodes):
        match = False

        if self.title.lower().find(query) > -1:
            match_path = path[:]
            match_path.append('Topic')
            matching_paths.append(match_path)
            match = True

        for child_key in self.child_keys:
            if child_key in node_dict:
                child = node_dict[child_key]

                if child_key.kind() == 'Topic':
                    sub_path = path[:]
                    sub_path.append(child.id)
                    if child.search_tree_traversal(query, node_dict, sub_path,
                                                   matching_paths,
                                                   matching_nodes):
                        match = True

                else:
                    title = getattr(child, "title",
                                    getattr(child, "display_name", ""))
                    id = getattr(child, "id",
                                 getattr(child, "readable_id",
                                         getattr(child, "name",
                                                 child.key().id())))
                    if (title.lower().find(query) > -1 or
                            str(id).lower().find(query) > -1):
                        match_path = path[:]
                        match_path.append(id)
                        match_path.append(child_key.kind())
                        matching_paths.append(match_path)
                        match = True
                        matching_nodes.append(child)

        if match:
            matching_nodes.append(self.get_visible_data(node_dict))

        return match

    def search_tree(self, query):
        query = query.strip().lower()

        nodes = Topic.all().filter("ancestor_keys =", self.key()).run()

        node_dict = dict((node.key(), node) for node in nodes)
        node_dict[self.key()] = self  # in case the current node is
                                      # hidden (like root is)

        contentKeys = []
        # cycle through the nodes adding its children to the
        # contentKeys that need to be gotten
        for key, descendant in node_dict.iteritems():
            contentKeys.extend([c for c in descendant.child_keys
                                if c not in node_dict and c.kind() != "Topic"])

        # get all content that belongs in this tree
        contentItems = db.get(contentKeys)
        # add the content to the node dict
        for content in contentItems:
            node_dict[content.key()] = content

        matching_paths = []
        matching_nodes = []

        self.search_tree_traversal(query, node_dict, [], matching_paths,
                                   matching_nodes)

        return {
            "paths": matching_paths,
            "nodes": matching_nodes
        }

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda version=None, include_hidden=False:
        "topic.get_all_topic_%s_%s" % (
            (str(version.number) + str(version.updated_on)) if version
            else setting_model.Setting.topic_tree_version(),
            include_hidden),
        layer=layer_cache.Layers.Memcache)
    def get_all_topics(version=None, include_hidden=False):
        if not version:
            version = TopicVersion.get_default_version()

        query = Topic.all().filter("version =", version)
        if not include_hidden:
            query.filter("hide =", False)

        return query.fetch(10000)

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda version=None:
        "topic.get_visible_topics_%s" % (
            version.key() if version
            else setting_model.Setting.topic_tree_version()),
        layer=layer_cache.Layers.Memcache)
    def get_visible_topics(version=None):
        topics = Topic.get_all_topics(version, False)
        return [t for t in topics]

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda version=None, include_hidden=False:
        "topic.get_super_topics_%s_%s" % (
            (str(version.number) + str(version.updated_on))  if version
            else setting_model.Setting.topic_tree_version(),
            include_hidden),
        layer=layer_cache.Layers.Memcache)
    def get_super_topics(version=None):
        topics = Topic.get_visible_topics()
        return [t for t in topics if t.id in Topic._super_topic_ids]

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda version=None, include_hidden=False:
        "topic.get_rolled_up_top_level_topics_%s_%s" % (
            (str(version.number) + str(version.updated_on))  if version
            else setting_model.Setting.topic_tree_version(),
            include_hidden),
        layer=layer_cache.Layers.Memcache)
    def get_rolled_up_top_level_topics(version=None, include_hidden=False):
        topics = Topic.get_all_topics(version, include_hidden)

        super_topics = Topic.get_super_topics()
        super_topic_keys = [t.key() for t in super_topics]

        rolled_up_topics = super_topics[:]
        for topic in topics:
            # if the topic is a subtopic of a super topic
            if set(super_topic_keys) & set(topic.ancestor_keys):
                continue

            for child_key in topic.child_keys:
                if child_key.kind() != "Topic":
                    rolled_up_topics.append(topic)
                    break

        return rolled_up_topics

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda types=None, version=None, include_hidden=False:
        "topic.get_filled_rolled_up_top_level_topics_%s_%s" % (
            (str(version.number) + str(version.updated_on))  if version
            else setting_model.Setting.topic_tree_version(),
            include_hidden),
        layer=layer_cache.Layers.Memcache)
    def get_filled_rolled_up_top_level_topics(types=None, version=None,
                                              include_hidden=False):
        if types is None:
            types = []

        topics = Topic.get_all_topics(version, include_hidden)
        topic_dict = dict((t.key(), t) for t in topics)

        super_topics = Topic.get_super_topics()

        def rolled_up_child_content_keys(topic):
            child_keys = []
            for key in topic.child_keys:
                if key.kind() == "Topic":
                    child_keys += rolled_up_child_content_keys(topic_dict[key])
                elif (len(types) == 0) or key.kind() in types:
                    child_keys.append(key)

            return child_keys

        for topic in super_topics:
            topic.child_keys = rolled_up_child_content_keys(topic)

        super_topic_keys = [t.key() for t in super_topics]

        rolled_up_topics = super_topics[:]
        for topic in topics:
            # if the topic is a subtopic of a super topic
            if set(super_topic_keys) & set(topic.ancestor_keys):
                continue

            for child_key in topic.child_keys:
                if child_key.kind() != "Topic":
                    rolled_up_topics.append(topic)
                    break

        child_dict = {}
        for topic in rolled_up_topics:
            child_dict.update(dict((key, True) for key in topic.child_keys
                                   if key.kind() in types or
                                   (len(types) == 0 and
                                    key.kind() != "Topic")))

        child_dict.update(dict((e.key(), e)
                               for e in db.get(child_dict.keys())))

        for topic in rolled_up_topics:
            topic.children = [child_dict[key] for key in topic.child_keys
                              if key in child_dict]

        return rolled_up_topics

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        lambda version=None, include_hidden=False:
        "topic.get_content_topics_%s_%s" % (
            (str(version.number) + str(version.updated_on))  if version
            else setting_model.Setting.topic_tree_version(),
            include_hidden),
        layer=layer_cache.Layers.Memcache)
    def get_content_topics(version=None, include_hidden=False):
        topics = Topic.get_all_topics(version, include_hidden)

        content_topics = []
        for topic in topics:
            for child_key in topic.child_keys:
                if child_key.kind() != "Topic":
                    content_topics.append(topic)
                    break

        content_topics.sort(key=lambda topic: topic.standalone_title)
        return content_topics

    @staticmethod
    def get_filled_content_topics(types=None, version=None,
                                  include_hidden=False):
        if types is None:
            types = []

        topics = Topic.get_content_topics(version)

        child_dict = {}
        for topic in topics:
            child_dict.update(dict((key, True) for key in topic.child_keys
                                   if key.kind() in types or
                                   (len(types) == 0 and
                                    key.kind() != "Topic")))
        child_dict.update(dict((e.key(), e)
                               for e in db.get(child_dict.keys())))

        for topic in topics:
            topic.children = [child_dict[key] for key in topic.child_keys
                              if key in child_dict]

        return topics

    @staticmethod
    def get_exercise_topics(version=None):
        """ Get all topics containing live exercises as direct children.
        
        This does *not* currently return topics with exercise-containing
        subtopics.
        """
        # TODO: when we want this to support multiple layers of topics, we'll
        # need a different interaction w/ Topic.
        topics = Topic.get_filled_content_topics(types=["Exercise"],
                                                 version=version)

        # Topics in ignored_topics will not show up on the knowledge map,
        # have topic exercise badges created for them, etc.
        ignored_topics = [
            "New and Noteworthy",
        ]

        # Filter out New and Noteworthy special-case topic. It might
        # have exercises, but we don't want it to own a badge.
        topics = [t for t in topics if t.title not in ignored_topics]

        # Remove non-live exercises
        for topic in topics:
            topic.children = [exercise for exercise in topic.children
                              if exercise.live]

        # Filter down to only topics that have live exercises
        return [topic for topic in topics if len(topic.children) > 0]

    @staticmethod
    def _get_children_of_kind(topic, kind, include_descendants=False,
                              include_hidden=False):
        keys = [child_key for child_key in topic.child_keys
                if not kind or child_key.kind() == kind]
        if include_descendants:

            subtopics = Topic.all().filter("ancestor_keys =", topic.key())
            if not include_hidden:
                subtopics.filter("hide =", False)
            subtopics.run()

            for subtopic in subtopics:
                keys.extend([key for key in subtopic.child_keys
                             if not kind or key.kind() == kind])

        nodes = db.get(keys)
        if not kind:
            nodes.extend(subtopics)

        return nodes

    def get_urls(self, include_descendants=False, include_hidden=False):
        return Topic._get_children_of_kind(self, "Url", include_descendants,
                                           include_hidden)

    def get_exercises(self, include_descendants=False, include_hidden=False):
        exercises = Topic._get_children_of_kind(self, "Exercise",
                                           include_descendants, include_hidden)

        # Topic.get_exercises should only return live exercises for
        # now, as its results are cached and should never show users
        # unpublished exercises.
        return [ex for ex in exercises if ex.live]

    def get_videos(self, include_descendants=False, include_hidden=False):
        return Topic._get_children_of_kind(self, "Video", include_descendants,
                                           include_hidden)

    def get_child_topics(self, include_descendants=False,
                         include_hidden=False):
        return Topic._get_children_of_kind(self, "Topic", include_descendants,
                                           include_hidden)

    def get_descendants(self, include_hidden=False):
        subtopics = Topic.all().filter("ancestor_keys =", self.key())
        if not include_hidden:
            subtopics.filter("hide =", False)
        return subtopics.fetch(10000)

    def delete_descendants(self):
        query = Topic.all(keys_only=True)
        descendants = query.filter("ancestor_keys =", self.key()).fetch(10000)
        db.delete(descendants)

    def get_exercise_badge(self):
        """ Returns the TopicExerciseBadge associated with this topic
        """
        badge_name = (badges.topic_exercise_badges.TopicExerciseBadge
                      .name_for_topic_key_name(self.key().name()))
        return badges.util_badges.all_badges_dict().get(badge_name, None)

    @staticmethod
    @layer_cache.cache_with_key_fxn(lambda
        topic, include_descendants=False, version=None:
        "%s_videos_for_topic_%s_v%s" % (
            "descendant" if include_descendants else "child",
            topic.key(),
            (version.key() if version
             else setting_model.Setting.topic_tree_version())),
        layer=layer_cache.Layers.Memcache)
    def get_cached_videos_for_topic(topic, include_descendants=False,
                                    version=None):
        return Topic._get_children_of_kind(topic, "Video", include_descendants)

    @staticmethod
    def reindex(version):
        items = search.StemmedIndex.all().filter("parent_kind", "Topic").run()
        db.delete(items)

        topics = Topic.get_content_topics(version)
        num_topics = len(topics)
        for i, topic in enumerate(topics):
            logging.info("Indexing topic %i/%i: %s (%s)" % 
                         (i, num_topics, topic.title, topic.key()))
            topic.index()
            topic.indexed_title_changed()

    def get_user_progress(self, user_data, flatten=True):

        def get_user_video_progress(video_id, user_video_dict):
            status_flags = {}

            id = '.v%d' % video_id

            if id in user_video_dict['completed']:
                status_flags["VideoCompleted"] = 1
                status_flags["VideoStarted"] = 1

            if id in user_video_dict['started']:
                status_flags["VideoStarted"] = 1

            if status_flags != {}:
                return {
                    "kind": "Video",
                    "id": video_id,
                    "status_flags": status_flags
                }

            return None

        def get_user_exercise_progress(exercise_id, user_exercise_dict):
            status_flags = {}

            if exercise_id in user_exercise_dict:
                exercise_dict = user_exercise_dict[exercise_id]

                if exercise_dict["proficient"]:
                    status_flags["ExerciseProficient"] = 1

                if exercise_dict["struggling"]:
                    status_flags["ExerciseStruggling"] = 1

                if exercise_dict["total_done"] > 0:
                    status_flags["ExerciseStarted"] = 1

            if status_flags != {}:
                return {
                    "kind": "Exercise",
                    "id": exercise_id,
                    "status_flags": status_flags
                }

            return None

        def get_user_progress_recurse(flat_output, topic, topics_dict,
                                      user_video_dict, user_exercise_dict):

            children = []
            status_flags = {}
            aggregates = {
                "video": {},
                "exercise": {},
                "topic": {}
            }
            counts = {
                "video": 0,
                "exercise": 0,
                "topic": 0
            }

            for child_key in topic.child_keys:
                if child_key.kind() == "Topic":
                    if child_key in topics_dict:
                        child_topic = topics_dict[child_key]
                        progress = get_user_progress_recurse(
                            flat_output, child_topic, topics_dict,
                            user_video_dict, user_exercise_dict)
                        if progress:
                            children.append(progress)
                            if flat_output:
                                flat_output["topic"][child_topic.id] = progress
                        counts["topic"] += 1

                elif child_key.kind() == "Video":
                    video_id = child_key.id()
                    progress = get_user_video_progress(video_id,
                                                       user_video_dict)
                    if progress:
                        children.append(progress)
                        if flat_output:
                            flat_output["video"][video_id] = progress
                    counts["video"] += 1

                elif child_key.kind() == "Exercise":
                    exercise_id = child_key.id()
                    progress = get_user_exercise_progress(exercise_id,
                                                          user_exercise_dict)
                    if progress:
                        children.append(progress)
                        if flat_output:
                            flat_output["exercise"][exercise_id] = progress
                    counts["exercise"] += 1
                    pass

            for child_stat in children:
                kind = child_stat["kind"].lower()
                for flag, value in child_stat["status_flags"].iteritems():
                    if flag not in aggregates[kind]:
                        aggregates[kind][flag] = 0
                    aggregates[kind][flag] += value

            for kind, aggregate in aggregates.iteritems():
                for flag, value in aggregate.iteritems():
                    if value >= counts[kind]:
                        status_flags[flag] = 1

            if children != [] or status_flags != {}:
                stats = {
                    "kind": "Topic",
                    "id": topic.id,
                    "status_flags": status_flags,
                    "aggregates": aggregates,
                    "counts": counts
                }
                if not flat_output:
                    stats["children"] = children
                return stats
            else:
                return None

        user_video_css = video_models.UserVideoCss.get_for_user_data(user_data)
        if user_video_css:
            user_video_dict = pickle_util.load(user_video_css.pickled_dict)
        else:
            user_video_dict = {}

        user_exercise_graph = exercise_models.UserExerciseGraph.get(user_data)
        user_exercise_dict = dict((exdict["id"], exdict)
                                  for name, exdict
                                  in user_exercise_graph.graph.iteritems())

        topics = Topic.get_visible_topics()
        topics_dict = dict((topic.key(), topic) for topic in topics)

        flat_output = None
        if flatten:
            flat_output = {
                "topic": {},
                "video": {},
                "exercise": {}
            }

        progress_tree = get_user_progress_recurse(
            flat_output, self, topics_dict, user_video_dict,
            user_exercise_dict)

        if flat_output:
            flat_output["topic"][self.id] = progress_tree
            return flat_output
        else:
            return progress_tree

    def get_search_data(self, topics_cache):
        child_topics = [topics_cache[str(k)] for k in self.child_keys
                        if k.kind() == "Topic" and str(k) in topics_cache]
        child_list = [{"title": t.title, "url": t.topic_page_url}
                      for t in child_topics]
        return {
            "kind": "Topic",
            "id": self.id,
            "title": self.standalone_title,
            "description": self.description,
            "ka_url": self.topic_page_url,
            "parent_topic": (unicode(self.parent_keys[0])
                             if self.parent_keys else None),
            "child_topics": jsonify.jsonify(child_list)
        }

    @staticmethod
    def cache_search_data():
        """ Store search data in KeyValueCache for later querying. """

        topic_search_data = []
        version = TopicVersion.get_default_version()

        topics = (Topic.all()
                  .filter('version =', version)
                  .filter("hide =", False))
        topics_cache = {}
        for topic in topics:
            topics_cache[str(topic.key())] = topic

        for topic in topics:
            topic_data = topic.get_search_data(topics_cache)
            topic_data["version"] = version.number

            topic_search_data.append(topic_data)

        layer_cache.KeyValueCache.set("Topic.search_data_cache",
                                      topic_search_data, time=0,
                                      namespace=None)

    @staticmethod
    def get_cached_search_data():
        """ Retrieve the static search data from the KeyValueCache. """

        data_cache = layer_cache.KeyValueCache.get("Topic.search_data_cache",
                                                   namespace=None)
        if data_cache:
            return data_cache

        raise Exception("Topic search data cache is missing")


class UserTopic(backup_model.BackupModel):
    user = db.UserProperty()
    seconds_watched = db.IntegerProperty(default=0)
    # can remove seconds_migrated after migration
    seconds_migrated = db.IntegerProperty(default=0)
    last_watched = db.DateTimeProperty(auto_now_add=True)
    topic_key_name = db.StringProperty()
    title = db.StringProperty(indexed=False)

    @staticmethod
    def get_for_user_data(user_data):
        return UserTopic.all().filter('user =', user_data.user)

    @staticmethod
    def get_key_name(topic, user_data):
        return user_data.key_email + ":" + topic.key().name()

    @staticmethod
    def get_for_topic_and_user_data(topic, user_data, insert_if_missing=False):
        if not user_data:
            return None

        key = UserTopic.get_key_name(topic, user_data)

        if insert_if_missing:
            return UserTopic.get_or_insert(
                        key_name=key,
                        title=topic.standalone_title,
                        topic_key_name=topic.key().name(),
                        user=user_data.user)
        else:
            return UserTopic.get_by_key_name(key)

    # temporary function used for backfill
    @staticmethod
    def get_for_topic_and_user(topic, user, insert_if_missing=False):
        if not user:
            return None

        key = user.email() + ":" + topic.key().name()

        if insert_if_missing:
            return UserTopic.get_or_insert(
                        key_name=key,
                        title=topic.standalone_title,
                        topic_key_name=topic.key().name(),
                        user=user)
        else:
            return UserTopic.get_by_key_name(key)


def _do_set_default_deferred_step(func, version_number, run_code):
    taskname = "v%i_run_%s_%s" % (version_number, run_code, func.__name__)
    try:
        deferred.defer(func,
                       version_number,
                       run_code,
                       _queue="topics-set-default-queue",
                       _name=taskname,
                       _url="/_ah/queue/deferred_topics-set-default-queue")
    except (taskqueue.TaskAlreadyExistsError, taskqueue.TombstonedTaskError):
        logging.info("deferred task %s already exists" % taskname)


# These all run in order -- they form a deferred-execution chain.

def _check_for_problems(version_number, run_code):
    setting_model.Setting.topic_admin_task_message("Publish: checking for "
                                                   "content problems")
    version = TopicVersion.get_by_id(version_number)
    content_problems = version.find_content_problems()
    for problem_type, problems in content_problems.iteritems():
        if len(problems):
            content_problems["Version"] = version_number
            content_problems["Date detected"] = datetime.datetime.now()
            layer_cache.KeyValueCache.set(
                "set_default_version_content_problem_details",
                content_problems)
            setting_model.Setting.topic_admin_task_message(
                ("Error - content problems found: %s. <a target=_blank "
                 "href='/api/v1/dev/topictree/problems'>"
                 "Click here to see problems.</a>") %
                (problem_type))

            raise deferred.PermanentTaskFailure

    _do_set_default_deferred_step(_apply_version_content_changes,
                                  version_number,
                                  run_code)


def _apply_version_content_changes(version_number, run_code):
    setting_model.Setting.topic_admin_task_message("Publish: applying version "
                                                   "content changes")
    version = TopicVersion.get_by_id(version_number)
    changes = (VersionContentChange.all()
               .filter('version =', version)
               .fetch(10000))
    changes = util.prefetch_refprops(changes, VersionContentChange.content)
    num_changes = len(changes)
    for i, change in enumerate(changes):
        change.apply_change()
        logging.info("applied change %i of %i" % (i, num_changes))
    logging.info("applied content changes")
    _do_set_default_deferred_step(_preload_default_version_data,
                                  version_number,
                                  run_code)


def preload_library_homepage(version):
    library.library_content_html(False, version.number)
    logging.info("preloaded library_content_html")

    library.library_content_html(True, version.number)
    logging.info("preloaded ajax library_content_html")


def preload_topic_pages(version):
    for topic in Topic.get_all_topics(version=version):
        topic.get_topic_page_json()
        topic.get_topic_page_html()
        topic.get_topic_page_nav_html()
    logging.info("preloaded topic pages")


def preload_topic_browsers(version):
    templatetags.topic_browser("browse", version.number)
    templatetags.topic_browser("browse-fixed", version.number)
    templatetags.topic_browser_data(version_number=version.number)
    logging.info("preloaded topic_browsers")


def _preload_default_version_data(version_number, run_code):
    setting_model.Setting.topic_admin_task_message("Publish: preloading cache")
    version = TopicVersion.get_by_id(version_number)

    # Preload library for upcoming version
    preload_library_homepage(version)

    # Preload topic pages
    preload_topic_pages(version)

    # Preload topic browsers
    preload_topic_browsers(version)

    # Preload autocomplete cache
    autocomplete.video_title_dicts(version.number)
    logging.info("preloaded video autocomplete")

    autocomplete.topic_title_dicts(version.number)
    logging.info("preloaded topic autocomplete")

    # Sync all topic exercise badges with upcoming version
    badges.topic_exercise_badges.sync_with_topic_version(version)
    logging.info("synced topic exercise badges")

    map_layout = layout.MapLayout.get_for_version(version)

    if not map_layout.has_layout:
        # Copy the previous maplayout to current version's maplayout
        # if it doesn't already exist.
        # TODO: this is temporary. Eventually this should be generated
        # correctly, once the topics admin UI can send maplayout info.

        previous_version = TopicVersion.get_by_id(version.copied_from_number)
        map_layout_previous = layout.MapLayout.get_for_version(
            previous_version)

    	# Khan NL
        if not map_layout_previous:
            map_layout_previous = layout.MapLayout(
                    key_name="maplayout:0",
                    version=map_layout.version,
                    layout=None
            )
            setting_model.Setting.topic_admin_task_message(
                " Khan NL : Importing maplayout from Khanacademy.org ")
            logging.info("importing knowledge map layout")
            request = urllib2.Request("http://www.khanacademy.org/api/v1/maplayout")
            opener = urllib2.build_opener()
            f = opener.open(request)
            map_layout_previous.layout = json.load(f)

        if not map_layout_previous.has_layout:
            setting_model.Setting.topic_admin_task_message(
                "Error - missing map layout and no previous version to "
                "copy from.")
            raise deferred.PermanentTaskFailure

        map_layout.layout = map_layout_previous.layout
        map_layout.put()

    _do_set_default_deferred_step(_change_default_version,
                                  version_number,
                                  run_code)


def _change_default_version(version_number, run_code):
    setting_model.Setting.topic_admin_task_message(
        "Publish: changing default version")
    version = TopicVersion.get_by_id(version_number)

    default_version = TopicVersion.get_default_version()

    def update_txn():

        if default_version:
            default_version.default = False
            default_version.put()

        version.default = True
        version.made_default_on = datetime.datetime.now()
        version.edit = False

        setting_model.Setting.topic_tree_version(version.number)
        setting_model.Setting.cached_content_add_date(datetime.datetime.now())

        version.put()

    transaction_util.ensure_in_transaction(update_txn, xg_on=True)

    # setting the topic tree version in the transaction won't update
    # memcache as the new values for the setting are not complete till the
    # transaction finishes ... so updating again outside the txn
    setting_model.Setting.topic_tree_version(version.number)

    logging.info("done setting new default version")

    # reindexing takes too long, and is only used for search, no need to do it
    # for dev unless working on the search page
    if not app.App.is_dev_server:
        rebuild_search_index(version, default_version)

    # update the new number of videos on the homepage
    logging.info("Updating the new video count")
    setting_model.Setting.topic_admin_task_message(
        "Publish: updating video count")  

    vids = video_models.Video.get_all_live()
    urls = url_model.Url.get_all_live()
    setting_model.Setting.count_videos(len(vids) + len(urls))
    video_models.Video.approx_count(bust_cache=True)

    setting_model.Setting.topic_admin_task_message(
        "Publish: creating new edit version")

    logging.info("creating a new edit version")
    TopicVersion.create_edit_version()
    logging.info("done creating new edit version")

    _do_set_default_deferred_step(_rebuild_content_caches,
                                  version_number,
                                  run_code)


def rebuild_search_index(new_version, old_version=None):
    # set a message for publishers that we are reindexing topics
    setting_model.Setting.topic_admin_task_message(
        "Publish: reindexing topics")
    
    Topic.reindex(new_version)
    logging.info("done fulltext reindexing topics")
    
    # set a message for publishers that we are reindexing videos
    setting_model.Setting.topic_admin_task_message(
        "Publish: reindexing videos")
    
    if old_version:
        # get all the changed videos
        query = VersionContentChange.all().filter('version =', new_version)
        changes = query.fetch(10000)
        updated_videos = [c.content for c in changes 
                          if isinstance(c.content, video_models.Video)]
        updated_video_keys = [v.key() for v in updated_videos]

        # get the video keys in the old tree 
        old_topics = Topic.get_all_topics(old_version)
        old_video_keys = set()
        for topic in old_topics:
            old_video_keys.update([k for k in topic.child_keys 
                                   if k.kind() == "Video" and 
                                   k not in updated_video_keys])

        # get the video keys in the latest tree
        new_topics = Topic.get_all_topics(new_version)
        latest_video_keys = set()
        for topic in new_topics:
            latest_video_keys.update([k for k in topic.child_keys 
                                      if k.kind() == "Video" and
                                      k not in updated_video_keys])

        # add the videos that are in the latest tree but not the old tree
        new_videos = db.get(list(latest_video_keys - old_video_keys))
        updated_videos.extend(new_videos)
        
        video_models.Video.reindex(updated_videos)
    else:
        video_models.Video.reindex()

    logging.info("done reindexing videos")


def _rebuild_content_caches(version_number, run_code):
    """ Uses existing Topic structure to rebuild and recache topic_string_keys
    properties in Video, Url, and Exercise entities for easy parental Topic
    lookups.
    """
    setting_model.Setting.topic_admin_task_message(
        "Publish: rebuilding content caches")

    version = TopicVersion.get_by_id(version_number)

    topics = Topic.get_all_topics(version)  # does not include hidden topics!

    videos = [v for v in video_models.Video.all()]
    video_dict = dict((v.key(), v) for v in videos)

    for video in videos:
        video.topic_string_keys = []

    urls = [u for u in url_model.Url.all()]
    url_dict = dict((u.key(), u) for u in urls)

    for url in urls:
        url.topic_string_keys = []

    # Grab all Exercise objects, even those that are hidden
    exercises = list(exercise_models.Exercise.all_unsafe())
    exercise_dict = dict((e.key(), e) for e in exercises)

    for exercise in exercises:
        exercise.topic_string_keys = []

    found_videos = 0

    for topic in topics:

        logging.info("Rebuilding content cache for topic " + topic.title)
        topic_key_str = str(topic.key())

        for child_key in topic.child_keys:

            if child_key.kind() == "Video":

                if child_key in video_dict:
                    video_dict[child_key].topic_string_keys.append(
                        topic_key_str)
                    found_videos += 1
                else:
                    logging.info("Failed to find video " + str(child_key))

            elif child_key.kind() == "Url":

                if child_key in url_dict:
                    url_dict[child_key].topic_string_keys.append(topic_key_str)
                    found_videos += 1
                else:
                    logging.info("Failed to find URL " + str(child_key))

            elif child_key.kind() == "Exercise":

                if child_key in exercise_dict:
                    exercise_dict[child_key].topic_string_keys.append(
                        topic_key_str)
                else:
                    logging.info("Failed to find exercise " + str(child_key))

    setting_model.Setting.topic_admin_task_message(
        "Publish: putting all content caches")
    logging.info("About to put content caches for all videos, urls, and "
                 "exercises.")
    db.put(list(videos) + list(urls) + list(exercises))
    logging.info("Finished putting videos, urls, and exercises.")

    # Wipe the Exercises cache key
    setting_model.Setting.cached_exercises_date(str(datetime.datetime.now()))

    logging.info("Rebuilt content topic caches. (%s videos)" % found_videos)

    # Preload the search index (accessed via the API /api/v1/searchindex)
    refresh_topictree_search_index_deferred()

    logging.info("set_default_version complete")
    setting_model.Setting.topic_admin_task_message(
        "Publish: finished successfully")


# version is not used but the RefreshCaches handler assumes a version argument
def refresh_topictree_search_index_deferred(version=None):
    video_models.Video.cache_search_data()
    Topic.cache_search_data()
    logging.info("Refreshed search index cache.")


class VersionContentChange(db.Model):
    """ This class keeps track of changes made in the admin/content editor.

    The changes will be applied when the version is set to default.
    """

    version = db.ReferenceProperty(TopicVersion, collection_name="changes")
    # content is the video/exercise/url that has been changed
    content = db.ReferenceProperty()
    # indexing updated_on as it may be needed for rolling back
    updated_on = db.DateTimeProperty(auto_now=True)
    last_edited_by = db.UserProperty(indexed=False)
    # content_changes is a dict of the properties that have been changed
    content_changes = object_property.UnvalidatedObjectProperty()

    def put(self):
        last_edited_by = (user_models.UserData.current().user
                          if user_models.UserData.current() else None)
        self.last_edited_by = last_edited_by
        db.Model.put(self)

    def apply_change(self):
        # exercises imports from request_handler which imports from models,
        # meaning putting this import at the top creates a import loop
        content = self.updated_content()
        content.put()

        if (content.key().kind() == "Exercise" and 
                hasattr(content, "related_video_readable_ids")):
            exercise_video_model.ExerciseVideo.update_related_videos(
                    content,
                    content.related_video_readable_ids)

        return content

    # if content is passed as an argument it saves a reference lookup
    def updated_content(self, content=None):
        if content is None:
            content = self.content
        elif content.key() != self.content.key():
            raise Exception("key of content passed in does not match "
                            "self.content")

        for prop, value in self.content_changes.iteritems():
            try:
                setattr(content, prop, value)
            except AttributeError:
                logging.info("cant set %s on a %s" %
                             (prop, content.__class__.__name__))

        return content

    @staticmethod
    @request_cache.cache()
    def get_updated_content_dict(version):
        query = VersionContentChange.all().filter("version =", version)
        return dict((c.key(), c) for c in
                    [u.updated_content(u.content) for u in query])

    @staticmethod
    def get_change_for_content(content, version):
        query = VersionContentChange.all().filter("version =", version)
        query.filter("content =", content)
        change = query.get()

        if change:
            # since we have the content already, updating the property may save
            # a reference lookup later
            change.content = content

        return change

    @staticmethod
    def add_new_content(klass, version, new_props, changeable_props=None,
                        put_change=True):
        filtered_props = dict((str(k), v) for k, v in new_props.iteritems()
                         if changeable_props is None or k in changeable_props)
        content = klass(**filtered_props)
        content.put()

        if (type(content) == exercise_models.Exercise 
                and "related_video_readable_ids" in new_props):

            if "related_video_keys" in new_props:
                related_video_keys = new_props["related_video_keys"]
                logging.info("related video keys already added")
            else:
                related_video_keys = []
                for readable_id in new_props["related_video_readable_ids"]:
                    video = video_models.Video.get_for_readable_id(readable_id, 
                                                                   version)
                    logging.info("doing get for readable_id")
                    related_video_keys.append(video.key())

            for i, video_key in enumerate(related_video_keys):
                exercise_video_model.ExerciseVideo(
                    exercise=content,
                    video=video_key,
                    exercise_order=i
                    ).put()

        if put_change:
            change = VersionContentChange(parent=version)
            change.version = version
            change.content_changes = filtered_props
            change.content = content
            setting_model.Setting.cached_content_add_date(
                datetime.datetime.now())
            change.put()
        return content

    @staticmethod
    def add_content_change(content, version, new_props, changeable_props=None):
        if changeable_props is None:
            changeable_props = new_props.keys()

        change = VersionContentChange.get_change_for_content(content, version)

        if change:
            previous_changes = True
        else:
            previous_changes = False
            change = VersionContentChange(parent=version)
            change.version = version
            change.content = content

        change.content_changes = {}

        if content and content.is_saved():

            for prop in changeable_props:
                if (prop in new_props and
                    new_props[prop] is not None and (
                        not hasattr(content, prop) or 
                        new_props[prop] != getattr(content, prop)
                        )
                    ):
                    
                    # add new changes for all props that are different
                    # from what is currently in content
                    change.content_changes[prop] = new_props[prop]
        else:
            raise Exception("content does not exit yet, call add_new_content "
                            "instead")

        # only put the change if we have actually changed any props
        if change.content_changes:
            change.put()

        # delete the change if we are back to the original values
        elif previous_changes:
            change.delete()

        return change.content_changes
