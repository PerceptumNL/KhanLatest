from phantom_users.phantom_util import is_phantom_id
import facebook_util
from third_party import search
import layer_cache
from google.appengine.ext import db


# Now that we're supporting unicode nicknames, ensure all callers get a
# consistent type of object back by converting everything to unicode.
# This fixes issue #4297.
def to_unicode(s):
    if not isinstance(s, unicode):
        return unicode(s, 'utf-8', 'ignore')
    else:
        return s


def get_default_nickname_for(user_data):
    """ Gets the default nickname for a user if none is available locally.

    This will infer a nickname either from Facebook or a Google e-mail address.
    """

    if not user_data:
        return None

    user_id = user_data.user_id
    email = user_data.email

    if not user_id or not email:
        return None

    if facebook_util.is_facebook_user_id(user_id):
        nickname = facebook_util.get_facebook_nickname(user_id)
    elif is_phantom_id(user_id):
        # Users will be prompted to login and save progress all over the place
        nickname = "Unsaved user"
    else:
        nickname = email.split('@')[0]
    return to_unicode(nickname)


def combinations(iterable, r):
    """Return r length subsequences of elements from the input iterable.

    Combinations are emitted in lexicographic sort order.
    So, if the input iterable is sorted, the combination tuples
    will be produced in sorted order.

    Elements are treated as unique based on their position, not on
    their value. So if the input elements are unique, there will be
    no repeat values in each combination.

    Copied from http://docs.python.org/library/itertools.html
    """
    pool = tuple(iterable)
    n = len(pool)
    if r > n:
        return
    indices = range(r)
    yield tuple(pool[i] for i in indices)
    while True:
        for i in reversed(range(r)):
            if indices[i] != i + n - r:
                break
        else:
            return
        indices[i] += 1
        for j in range(i + 1, r):
            indices[j] = indices[j - 1] + 1
        yield tuple(pool[i] for i in indices)

INDEX_DELIMITER = u"\uffff"


def build_index_strings(nickname):
    """ Builds sanitized strings to be used in a username index so that
    searches on a user's first, middle, or last name can be done.

    See models.NicknameIndex for details.
    """

    # Build out raw tokens. e.g. "Sal Amin Khan" -> ["amin", "khan", "sal"]
    tokens = search.PUNCTUATION_REGEX.sub(' ', nickname).lower().split()
    tokens.sort()

    # Build out terms for multi-term prefix scans:
    # e.g. [("amin"), ("khan"), ("sal"), ("amin, "khan"), ("amin", "sal")...]
    term_tuples = []
    for num_terms in range(1, len(tokens) + 1):
        term_tuples.extend([t for t in combinations(tokens, num_terms)])
    return [INDEX_DELIMITER.join(t) for t in term_tuples]


def build_search_query(raw_query):
    """ Builds out a relevant search query to be used in conjunction with
    the index tokens built out by build_index_strings

    See models.NicknameIndex for details.
    """
    tokens = search.PUNCTUATION_REGEX.sub(' ', raw_query).lower().split()
    tokens.sort()
    return INDEX_DELIMITER.join(tokens)


@layer_cache.cache(persist_across_app_versions=True)
def _get_offensive_terms():
    return frozenset([entity.term for entity in OffensiveTerm.all()])


class OffensiveTerm(db.Model):
    term = db.StringProperty()


def is_valid_nickname(name):
    """ Validates a name to be used, checking for blatantly offensive names.
    This uses a fairly conservative check to avoid embarassing false positives;
    the community and social pressures will hopefully deal with the keen
    offenders.
    """
    blacklist = _get_offensive_terms()
    return not any([token.lower() in blacklist for token in name.split(' ')])
