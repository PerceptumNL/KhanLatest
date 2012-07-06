import os
import Cookie
import logging
import hashlib
from functools import wraps

from third_party.flask import request
import user_models
from cookie_util import set_request_cookie
from api import api_util


# TODO: consolidate this with the constants in user_models.py:UserData
PHANTOM_ID_EMAIL_PREFIX = "http://nouserid.khanacademy.org/"
PHANTOM_MORSEL_KEY = 'ureg_id'
PHANTOM_COOKIE_AGE = 90 * 24 * 60 * 60  # ~3 months in seconds


def is_phantom_id(user_id):
    return user_id.startswith(PHANTOM_ID_EMAIL_PREFIX)


def get_phantom_user_id_from_cookies():
    cookies = None
    try:
        cookies = Cookie.BaseCookie(os.environ.get('HTTP_COOKIE', ''))
    except Cookie.CookieError, error:
        logging.critical("Ignoring Cookie Error: '%s'" % error)
        return None

    morsel = cookies.get(PHANTOM_MORSEL_KEY)
    if morsel and morsel.value:
        return PHANTOM_ID_EMAIL_PREFIX + morsel.value
    else:
        return None


def _create_phantom_user_id():
    rs = os.urandom(20)
    random_string = hashlib.md5(rs).hexdigest()
    return PHANTOM_ID_EMAIL_PREFIX + random_string


def _create_phantom_user_data():
    """ Create a phantom user data.
    """
    user_id = _create_phantom_user_id()
    user_data = user_models.UserData.insert_for(user_id, user_id)

    # Make it appear like the cookie was already set
    cookie = _get_cookie_from_phantom(user_data)
    set_request_cookie(PHANTOM_MORSEL_KEY, str(cookie))

    # Bust the cache so later calls to user_models.UserData.current() return
    # the phantom user
    return user_models.UserData.current(bust_cache=True)


def _get_cookie_from_phantom(phantom_user_data):
    """Return the cookie value for a phantom user."""
    parts = phantom_user_data.email.split(PHANTOM_ID_EMAIL_PREFIX)
    if len(parts) != 2:
        return None  # Malformed.
    return parts[1]


def create_phantom(method):
    '''Decorator used to create phantom users if necessary.

    Warning:
    - Only use on get methods where a phantom user should be created.
    '''

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        user_data = user_models.UserData.current()

        if not user_data:
            user_data = _create_phantom_user_data()
            # set the cookie on the user's computer
            cookie = _get_cookie_from_phantom(user_data)
            self.set_cookie(PHANTOM_MORSEL_KEY, cookie,
                    max_age=PHANTOM_COOKIE_AGE)

        return method(self, *args, **kwargs)
    return wrapper


def api_create_phantom(method):
    '''Decorator used to create phantom users in api calls if necessary.'''

    @wraps(method)
    def wrapper(*args, **kwargs):
        if user_models.UserData.current():
            return method(*args, **kwargs)
        else:
            user_data = _create_phantom_user_data()

            if not user_data:
                logging.warning("api_create_phantom failed to create "
                                "user_data properly. xsrf failure? "
                                "Headers:\n%s" % str(request.headers).strip())
                return api_util.api_unauthorized_response(
                    'Failed to create phantom user')

            response = method(*args, **kwargs)

            cookie = _get_cookie_from_phantom(user_data)
            response.set_cookie(PHANTOM_MORSEL_KEY, cookie,
                    max_age=PHANTOM_COOKIE_AGE)

            return response

    return wrapper
