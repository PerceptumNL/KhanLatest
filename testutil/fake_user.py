"""Used to create fake users for unit tests.
"""

from google.appengine.api import users
from google.appengine.ext import db

import facebook_util
import uid
import user_models


def user(user_id, db_key_email, user_email):
        user = user_models.UserData.insert_for(user_id, db_key_email)
        user.user_email = user_email
        user.put()
        # Flush db transaction.
        # TODO(ankit): What does this do?
        db.get(user.key())
        return user


def google_user(google_user_id, email):
    google_user_id = uid.google_user_id(
            users.User(_user_id=google_user_id, email=email))
    return user(google_user_id,
                db_key_email=email,
                user_email=email)


def fb_user(fb_id, email=None):
    fb_user_id = facebook_util.FACEBOOK_ID_PREFIX + str(fb_id)

    # Note - the db_key_email of Facebook users never change.
    return user(fb_user_id,
                db_key_email=fb_user_id,
                user_email=email or fb_user_id)


def private_user(user_id, email, username=None):
    user = google_user(user_id, email)
    if not username is None:
        user.username = username
        user.put()
    return user


def public_user(user_id, email, username):
    user = google_user(user_id, email)
    user.is_profile_public = True
    user.username = username
    user.put()
    return user
