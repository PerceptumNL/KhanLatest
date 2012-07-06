import auth.cookies
import datetime
import request_cache
import logging
from google.appengine.api import users
from google.appengine.ext import db

from third_party.asynctools import AsyncMultiTask, QueryTask

# Needed for side effects of secondary imports
import nicknames  # @UnusedImport
import facebook_util
from phantom_users.phantom_util import get_phantom_user_id_from_cookies, \
    is_phantom_id

from api.auth.auth_util import current_oauth_map, allow_cookie_based_auth
import uid


def current_req_has_auth_credentials():
    """Determine whether or not the current request has valid credentials."""
    return get_current_user_id_unsafe() is not None


# TODO(benkomalo): kill this method! Clients interested in the current user
# should use user_models.UserData.current() instead, as this may be returning
# invalid user_id values (though if it's non-empty, then we know that the user
# is logged in.)
@request_cache.cache()
def get_current_user_id_unsafe():
    """Get the user_id a new user would get for the current auth credentials.

    Typically, this is the user_id of the current, logged in user. However,
    it's really important to note that it may correspond to a user_id that
    doesn't belong to any user. For example, if third-party
    credentials are provided (e.g. valid Facebook tokens), and we
    resolve them to point to an existing, different user (through e-mail
    e-mail matching or other means), this would return a user_id value
    that's constructed from the Facebook credentials, even though
    the user_id of the current logged in user is something different.

    Returns:
        A string value for the user_id, or None if no valid auth credentials
        are detected in the request.
    """

    user_id = None

    oauth_map = current_oauth_map()
    if oauth_map:
        user_id = _get_current_user_id_from_oauth_map(oauth_map)

    if not user_id and allow_cookie_based_auth():
        user_id = _get_current_user_id_from_cookies_unsafe()

    return user_id


def _get_current_user_id_from_oauth_map(oauth_map):
    return oauth_map.get_user_id()


# get_current_user_from_cookies_unsafe is labeled unsafe because it should
# never be used in our JSONP-enabled API. Clients should do XSRF checks.
def _get_current_user_id_from_cookies_unsafe():
    user = users.get_current_user()

    user_id = None
    if user:  # if we have a google account
        user_id = uid.google_user_id(user)

    if not user_id:
        user_id = auth.cookies.get_user_from_khan_cookies()

    if not user_id:
        user_id = facebook_util.get_current_facebook_user_id_from_cookies()

    # if we don't have a user_id, then it's not facebook or google
    if not user_id:
        user_id = get_phantom_user_id_from_cookies()

    return user_id


def is_phantom_user(user_id):
    return user_id and is_phantom_id(user_id)


def seconds_since(dt):
    return seconds_between(dt, datetime.datetime.now())


def seconds_between(dt1, dt2):
    timespan = dt2 - dt1
    return float(timespan.seconds + (timespan.days * 24 * 3600))


def minutes_between(dt1, dt2):
    return seconds_between(dt1, dt2) / 60.0


def hours_between(dt1, dt2):
    return seconds_between(dt1, dt2) / (60.0 * 60.0)


def thousands_separated_number(x):
    # See http://stackoverflow.com/questions/1823058/
    # how-to-print-number-with-commas-as-thousands-separators-in-python-2-x
    if x < 0:
        return '-' + thousands_separated_number(-x)
    result = ''
    while x >= 1000:
        x, r = divmod(x, 1000)
        result = ",%03d%s" % (r, result)
    return "%d%s" % (x, result)


def async_queries(queries, limit=100000):

    task_runner = AsyncMultiTask()
    for query in queries:
        task_runner.append(QueryTask(query, limit=limit))
    task_runner.run()

    return task_runner


def config_iterable(plain_config, batch_size=50, limit=1000):

    config = plain_config

    try:
        # This specific use of the QueryOptions private API was
        # suggested to us by the App Engine team.  Wrapping in
        # try/except in case it ever goes away.
        from google.appengine.datastore import datastore_query
        config = datastore_query.QueryOptions(
            config=plain_config,
            limit=limit,
            offset=0,
            prefetch_size=batch_size,
            batch_size=batch_size)

    except Exception, e:
        logging.exception("Failed to create QueryOptions config object: %s", e)

    return config


def clone_entity(e, **extra_args):
    """http://stackoverflow.com/questions/2687724/copy-an-entity-in-google-app-engine-datastore-in-python-without-knowing-property
    Clones an entity, adding or overriding constructor attributes.

    The cloned entity will have exactly the same property values as
    the original entity, except where overridden. By default it will
    have no parent entity or key name, unless supplied.

    Args:
        e: The entity to clone
        extra_args: Keyword arguments to override from the cloned entity and
        pass to the constructor.
    Returns:
        A cloned, possibly modified, copy of entity e.
    """
    klass = e.__class__
    props = dict((k, v.__get__(e, klass))
                 for k, v in klass.properties().iteritems())
    props.update(extra_args)
    return klass(**props)


def parse_iso8601(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def prefetch_refprops(entities, *props):
    """http://blog.notdot.net/2010/01/ReferenceProperty-prefetching-in-App-Engine
    Loads referenced models defined by the given model properties
    all at once on the given entities.

    Example:
    posts = Post.all().order("-timestamp").fetch(20)
    prefetch_refprop(posts, Post.author)
    """
    # Get a list of (entity,property of this entity)
    fields = [(entity, prop) for entity in entities for prop in props]
    # Pull out an equally sized list of the referenced key for each
    # field (possibly None)
    ref_keys_with_none = [prop.get_value_for_datastore(x)
                          for x, prop in fields]
    # Make a dict of keys:fetched entities
    ref_keys = filter(None, ref_keys_with_none)
    ref_entities = dict((x.key(), x) for x in db.get(set(ref_keys)))
    # Set the fetched entity on the non-None reference properties
    for (entity, prop), ref_key in zip(fields, ref_keys_with_none):
        if ref_key is not None:
            prop.__set__(entity, ref_entities[ref_key])
    return entities


def coalesce(fn, s):
    """Call a function only if the argument is not None"""
    if s is not None:
        return fn(s)
    else:
        return None


def count_with_cursors(query, max_value=None):
    """ Counts the number of items that match a given query, using cursors
    so that it can return a number over 1000.

    USE WITH CARE: should not be done in user-serving requests and can be
    very slow.
    """
    count = 0
    while (count % 1000 == 0 and
             (max_value is None or count < max_value)):
        current_count = len(query.fetch(1000))
        if current_count == 0:
            break

        count += current_count
        if current_count == 1000:
            cursor = query.cursor()
            query.with_cursor(cursor)

    return count


def insert_in_position(index, items, val, filler):
    """Inserts val into the list items at position index, adding filler
    elements to extend the list size if required.

    This does not have the same behavior as .insert(). This is used in deferred
    logging tasks because tasks can be run out of order so we extend the list
    as needed and insert values.
    """
    if index >= len(items):
        items.extend([filler] * (index + 1 - len(items)))
    items[index] = val


def update_dict_with(old_dict, new_dict, func_map):
    """A version of {}.update that uses custom functions when updating values
    of existing entries.

    old_dict - The dictionary that will be updated. Same as the first argument
        to {}.update.
    new_dict - A dictionary of what to update in old_dict. Same as second
        argument in {}.update.
    func_map - a dict of key-function pairs. When updating a key-value pair
        that exists in old_dict, will assign the value of the function
        func_map[key] called on with the params the old value and the new
        value, respectively.

    >>> import operator
    >>> old_dict = {'correct': 3, 'problem_num': 5, 'cake': True}
    >>> update_dict_with(old_dict, {'correct': 1, 'problem_num': 4, 'cake':
    ... False}, {'correct': operator.add, 'problem_num': max})
    >>> old_dict
    {'cake': False, 'problem_num': 5, 'correct': 4}
    """

    for k, v in new_dict.iteritems():
        old_dict[k] = (func_map.get(k, lambda x, y: y)(old_dict[k], v) if k in
                old_dict else v)
