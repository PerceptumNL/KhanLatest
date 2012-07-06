try:
    import threading
except ImportError:
    import dummy_threading as threading

from google.appengine.ext import db
from google.appengine.datastore import entity_pb
from google.appengine.api import memcache

from gandalf.models import GandalfBridge

# TODO(chris): expire the gandalf instance cache. Currently there is
# no way to force propagation of gandalf updates across all instances
# without redeploying. It's also possible that this should be a
# request cache instead.

_instance_cache = {}
_instance_cache_lock = threading.RLock()


def flush_instance_cache():
    global _instance_cache
    with _instance_cache_lock:
        _instance_cache = {}


def init_instance_cache_from_memcache():
    with _instance_cache_lock:
        # TODO(chris): remove use of redundant loaded_from_memcache key
        if not _instance_cache.get("loaded_from_memcache"):
            _instance_cache[GandalfCache.MEMCACHE_KEY] = memcache.get(
                GandalfCache.MEMCACHE_KEY)
            _instance_cache["loaded_from_memcache"] = True


class GandalfCache(object):
    """For internal use only. A cache of Gandalf bridges.

    Since an instance of this cache is shared across threads, the cache must
    be treated as read-only. Since we can't trust the public to obey this API
    constraint, this class is not part of the public interface.

    Callers must first acquire the lock returned by get_lock() for thread-safe
    access. For example:

    with gandalf_cache.get_lock():
        bridge = gandalf_cache.get_bridge_model(bridge_name)
    """

    MEMCACHE_KEY = "_gandalf_cache"

    # Share a lock between all instances. This would be better as an instance
    # property, but instances are pickled and stored in memcache, and lock
    # objects cannot be pickled. In practice a shared lock is good enough
    # because there is only one instance unless an admin busts the cache.
    _INSTANCE_LOCK = threading.RLock()

    def __init__(self):

        self.bridges = {}  # Protobuf version of bridges for extremely
                           # fast (de)serialization
        self.bridge_models = {}  # Deserialized bridge models

        self.filters = {}  # Protobuf version of filters for extremely
                           # fast (de)serialization
        self.filter_models = {}  # Deserialized filter models

    @staticmethod
    def get():
        with _instance_cache_lock:
            gandalf_cache = _instance_cache.get(GandalfCache.MEMCACHE_KEY)
            if gandalf_cache:
                return gandalf_cache

            init_instance_cache_from_memcache()

            if not _instance_cache.get(GandalfCache.MEMCACHE_KEY):
                _instance_cache[GandalfCache.MEMCACHE_KEY] = \
                    GandalfCache.load_from_datastore()

            return _instance_cache[GandalfCache.MEMCACHE_KEY]

    @staticmethod
    def load_from_datastore():
        gandalf_cache = GandalfCache()

        bridges = GandalfBridge.all()

        for bridge in bridges:

            key = bridge.key().name()

            gandalf_cache.bridges[key] = db.model_to_protobuf(bridge).Encode()

            filters = bridge.gandalffilter_set

            gandalf_cache.filters[key] = []

            for filter in filters:
                gandalf_cache.filters[key].append(
                    db.model_to_protobuf(filter).Encode())

        memcache.set(GandalfCache.MEMCACHE_KEY, gandalf_cache)

        return gandalf_cache

    @staticmethod
    def delete_from_memcache():
        memcache.delete(GandalfCache.MEMCACHE_KEY)

    def get_lock(self):
        return GandalfCache._INSTANCE_LOCK

    def get_bridge_model(self, bridge_name):
        """Callers must hold the lock returned by get_lock() when
        calling this method for thread-safe access."""
        if bridge_name in self.bridge_models:
            return self.bridge_models[bridge_name]
        elif bridge_name in self.bridges:
            model_proto_contents = self.bridges[bridge_name]
            model = db.model_from_protobuf(
                entity_pb.EntityProto(model_proto_contents))
            self.bridge_models[bridge_name] = model
            return model
        else:
            return None

    def get_filter_models(self, bridge_name):
        """Callers must hold the lock returned by get_lock() when
        calling this method for thread-safe access."""
        if bridge_name in self.filter_models:
            return self.filter_models[bridge_name]
        elif bridge_name in self.filters:
            models = [db.model_from_protobuf(entity_pb.EntityProto(filter))
                      for filter in self.filters[bridge_name]]
            self.filter_models[bridge_name] = models
            return models
        else:
            return None
