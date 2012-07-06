from functools import wraps
from google.appengine.api import memcache
import time
import logging


def clamp(min_val, max_val):
    """Ensures wrapped fn's return value is between given min and max bounds"""
    def decorator(func):
        @wraps(func)
        def wrapped(*arg, **kwargs):
            return sorted((min_val, func(*arg, **kwargs), max_val))[1]
        return wrapped
    return decorator


def synchronized_with_memcache(key=None, timeout=10):
    """A mutually exclusive (mutex) lock based on memcache.  
    USE WITH EXTREME CAUTION:
    
    It should be used only on things that two processes should not be doing at 
    the same time.  It could be used on an expensive function that will then be 
    cached, so that more than one process does not have to do that function, 
    but if the cache dies for some reason, you could get a lot of processes 
    waiting serially for the next one to finish.
    """
    def decorator(func):
        @wraps(func)
        def wrapped(*arg, **kwargs):
            start = time.time()
            end = start

            lock_key = key
            if lock_key is None:
                lock_key = "%s.%s__" % (func.__module__, func.__name__)
              
            lock_key = "__synchronized_with_memcache_" + lock_key 
                    
            client = memcache.Client()
            got_lock = False
            try:
                # Make sure the func gets called only one at a time
                while not got_lock and end - start < timeout:
                    locked = client.gets(lock_key)

                    while locked is None:
                        # Initialize the lock if necessary
                        client.set(lock_key, False)
                        locked = client.gets(lock_key)

                    if not locked:
                        # Lock looks available, try to take it with compare 
                        # and set (expiration of 10 seconds)
                        got_lock = client.cas(lock_key, True, time=timeout)
                    
                    if not got_lock:
                        # If we didn't get it, wait a bit and try again
                        time.sleep(0.1)

                    end = time.time()

                if not got_lock:
                    logging.warning(("synchronization lock on %s:%s timed out "
                                     "after %f seconds")
                                    % (func.__module__, func.__name__,
                                       end - start))
                elif end - start > timeout * 0.75:
                    # its possible that the func didn't finish but the
                    # cas timeout was reached, so if we get these
                    # warnings we should probably bump the timeout as well
                    logging.warning(("synchronization lock %s:%s almost timed "
                                     "out, but got lock after %f seconds")
                                    % (func.__module__, func.__name__,
                                       end - start))
                
                results = func(*arg, **kwargs)

            finally:
                if got_lock:
                    # Release the lock
                    client.set(lock_key, False)

            return results
        return wrapped
    return decorator
