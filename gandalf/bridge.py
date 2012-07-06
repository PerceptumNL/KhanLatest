import logging

from app import App
from gandalf.cache import GandalfCache
from gandalf.config import current_logged_in_identity


def gandalf(bridge_name):

    if not bridge_name:
        raise Exception("Must include 'bridge_name' parameter")

    gandalf_cache = GandalfCache.get()

    with gandalf_cache.get_lock():
        # Lock while getting models because they are built lazily and
        # so might modify the cache object.
        bridge = gandalf_cache.get_bridge_model(bridge_name)
        if not bridge:
            if not App.is_dev_server:
                logging.error("User tried to cross non-existent bridge '%s'" %
                              bridge_name)
            return False
        filters = gandalf_cache.get_filter_models(bridge_name)

    identity = current_logged_in_identity()

    # A user needs to pass a single whitelist, and pass no blacklists,
    # to pass a bridge
    passes_a_whitelist = False

    for filter in filters:
        if filter.whitelist:
            if filter.filter_class.passes_filter(filter, identity):
                passes_a_whitelist = True
        else:
            if filter.filter_class.passes_filter(filter, identity):
                return False

    return passes_a_whitelist
