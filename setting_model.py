"""Stores per-application key-value pairs for app-wide settings.

These are settings that must be synchronized across all GAE instances.
"""

from google.appengine.ext import db

import layer_cache
import request_cache


class Setting(db.Model):
    value = db.StringProperty(indexed=False)

    @staticmethod
    def entity_group_key():
        return db.Key.from_path('Settings', 'default_settings')

    @staticmethod
    def _get_or_set_with_key(key, val=None):
        if val is None:
            return Setting._cache_get_by_key_name(key)
        else:
            setting = Setting(Setting.entity_group_key(), key, value=str(val))
            db.put(setting)
            Setting._get_settings_dict(bust_cache=True)
            return setting.value

    @staticmethod
    def _cache_get_by_key_name(key):
        setting = Setting._get_settings_dict().get(key)
        if setting is not None:
            return setting.value
        return None

    @staticmethod
    @request_cache.cache()
    @layer_cache.cache(layer=layer_cache.Layers.Memcache)
    def _get_settings_dict():
        # ancestor query to ensure consistent results
        query = Setting.all().ancestor(Setting.entity_group_key())
        results = dict((setting.key().name(), setting)
                       for setting in query.fetch(20))
        return results

    @staticmethod
    def cached_content_add_date(val=None):
        return Setting._get_or_set_with_key("cached_content_add_date", val)

    @staticmethod
    def topic_tree_version(val=None):
        return Setting._get_or_set_with_key("topic_tree_version", val)

    @staticmethod
    def cached_exercises_date(val=None):
        return Setting._get_or_set_with_key("cached_exercises_date", val)

    @staticmethod
    def count_videos(val=None):
        return Setting._get_or_set_with_key("count_videos", val) or 0

    @staticmethod
    def last_youtube_sync_generation_start(val=None):
        return Setting._get_or_set_with_key(
            "last_youtube_sync_generation_start", val) or 0

    @staticmethod
    def topic_admin_task_message(val=None):
        return Setting._get_or_set_with_key("topic_admin_task_message", val)

    @staticmethod
    def smarthistory_version(val=None):
        return Setting._get_or_set_with_key("smarthistory_version", val) or 0

    @staticmethod
    def classtime_report_method(val=None):
        return Setting._get_or_set_with_key("classtime_report_method", val)

    @staticmethod
    def classtime_report_startdate(val=None):
        return Setting._get_or_set_with_key("classtime_report_startdate", val)
