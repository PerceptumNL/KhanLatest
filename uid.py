"""

Utilities for handling user ID values for UserData objects.

"""

import uuid

USER_ID_PREFIX = "http://id.khanacademy.org/"

GOOGLE_USER_ID_PREFIX = "http://googleid.khanacademy.org/"


def new_user_id():
    """
    Generates a probabilisticly new user id value.

    Clients should still double-check the database to see if an existing user
    by the specified ID exists, and re-try if so.

    """
    return "%s%s" % (USER_ID_PREFIX, uuid.uuid4().hex)


def google_user_id(user):
    """ Generates the user ID used in our databases given a
    google.appengine.api.users.user """

    return "%s%s" % (GOOGLE_USER_ID_PREFIX, user.user_id())
