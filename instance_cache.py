"""
Based on cachepy.py by Juan Pablo Guereca with additional modifications
for thread safety and simplified to reduce time spent in critical areas.

Module which implements a per GAE instance data cache, similar to what
you can achieve with APC in PHP instances.

Each GAE instance caches the global scope, keeping the state of every
variable on the global scope.

You can go farther and cache other things, creating a caching layer
for each GAE instance, and it's really fast because there is no
network transfer like in memcache. Moreover GAE doesn't charge for
using it and it can save you many memcache and db requests.

Not everything are upsides. You can not use it on every case because:

- There's no way to know if you have set or deleted a key in all the
  GAE instances that your app is using. Everything you do with Cachepy
  happens in the instance of the current request and you have N
  instances, be aware of that.

- The only way to be sure you have flushed all the GAE instances
  caches is doing a code upload, no code change required.

- The memory available depends on each GAE instance and your app. I've
  been able to set a 60 millions characters string which is like 57 MB
  at least. You can cache somethings but not everything.
"""

# TODO(chris): implement an LRU cache. currently we store all sorts of
# things in instance memory by default via layer_cache, and these
# things might never be reaped.

import time
import logging
import os

try:
    import threading
except ImportError:
    import dummy_threading as threading

_CACHE = {}
_CACHE_LOCK = threading.RLock()

""" Flag to deactivate it on local environment. """
ACTIVE = (not os.environ.get('SERVER_SOFTWARE').startswith('Devel') or
          os.environ.get('FAKE_PROD_APPSERVER'))

"""
None means forever.
Value in seconds.
"""
DEFAULT_CACHING_TIME = None


def get(key):
    """ Gets the data associated to the key or a None """
    if ACTIVE is False:
        return None

    with _CACHE_LOCK:
        entry = _CACHE.get(key, None)
        if entry is None:
            return None

        value, expiry = entry
        if expiry == None:
            return value

        current_timestamp = time.time()
        if current_timestamp < expiry:
            return value
        else:
            del _CACHE[key]
            return None


def set(key, value, expiry=DEFAULT_CACHING_TIME):
    """
    Sets a key in the current instance
    key, value, expiry seconds till it expires
    """
    if ACTIVE is False:
        return None

    if expiry != None:
        expiry = time.time() + int(expiry)

    try:
        with _CACHE_LOCK:
            _CACHE[key] = (value, expiry)
    except MemoryError:
        # It doesn't seems to catch the exception, something in the
        # GAE's python runtime probably.
        logging.info("%s memory error setting key '%s'" % (__name__, key))


def delete(key):
    """ Deletes the key stored in the cache of the current instance,
    not all the instances.  There's no reason to use it except for
    debugging when developing, use expiry when setting a value
    instead.
    """
    with _CACHE_LOCK:
        _CACHE.pop(key, None)


def dump():
    """
    Returns the cache dictionary with all the data of the current
    instance, not all the instances.  There's no reason to use it
    except for debugging when developing.
    """
    return _CACHE


def flush():
    """
    Resets the cache of the current instance, not all the instances.
    There's no reason to use it except for debugging when developing.
    """
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = {}
