"""Stores a reference to a video when it's not on youtube.

TODO(csilvers): is that right?  Also, is this class obsolete?
"""

from google.appengine.ext import db

import layer_cache
import object_property
import setting_model
import topic_models


class Url(db.Model):
    url = db.StringProperty()
    title = db.StringProperty(indexed=False)
    tags = db.StringListProperty()
    created_on = db.DateTimeProperty(auto_now_add=True)
    updated_on = db.DateTimeProperty(indexed=False, auto_now=True)

    # List of parent topics
    topic_string_keys = object_property.TsvProperty(indexed=False)

    @property
    def id(self):
        return self.key().id()

    # returns the first non-hidden topic
    def first_topic(self):
        if self.topic_string_keys:
            return db.get(self.topic_string_keys[0])
        return None

    @staticmethod
    @layer_cache.cache_with_key_fxn(lambda:
        "Url.get_all_%s" %
        setting_model.Setting.cached_content_add_date(),
        layer=layer_cache.Layers.Memcache)
    def get_all():
        return Url.all().fetch(100000)

    @staticmethod
    def get_all_live(version=None):
        if not version:
            version = topic_models.TopicVersion.get_default_version()

        root = topic_models.Topic.get_root(version)
        urls = root.get_urls(include_descendants=True, include_hidden=False)

        # return only unique urls
        url_dict = dict((u.key(), u) for u in urls)
        return url_dict.values()

    @staticmethod
    def get_by_id_for_version(id, version=None):
        url = Url.get_by_id(id)
        # if there is a version check to see if there are any updates
        # to the video
        if version:
            change = topic_models.VersionContentChange.get_change_for_content(
                url, version)
            if change:
                url = change.updated_content(url)
        return url
