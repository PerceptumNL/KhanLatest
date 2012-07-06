import cookie_util
import base64
import os
import logging
import time
from functools import wraps
from api.route_decorator import (XSRF_API_VERSION, XSRF_COOKIE_KEY,
                                 XSRF_HEADER_KEY, is_current_api_version)


def create_xsrf_cookie_if_needed(http_response):
    """http_request is the http response object used to set the cookie on."""
    xsrf_token = get_xsrf_cookie_value()
    if xsrf_token and is_current_api_version(xsrf_token):
        return   # not needed -- the cookie already exists
    timestamp = int(time.time())
    xsrf_value = "%s_%s_%d" % (
        XSRF_API_VERSION,
        base64.urlsafe_b64encode(os.urandom(10)),
        timestamp)

    # Set a cookie containing the XSRF value.
    # The JavaScript is responsible for returning the cookie
    # in a matching header that is validated by
    # validate_xsrf_cookie.
    http_response.set_cookie(XSRF_COOKIE_KEY, xsrf_value, httponly=False)
    cookie_util.set_request_cookie(XSRF_COOKIE_KEY, xsrf_value)
    

def ensure_xsrf_cookie(func):
    """ This is a decorator for a method that ensures when the response to
    this request is sent, the user's browser has the appropriate XSRF cookie
    set.
    
    The XSRF cookie is required for making successful API calls from our site
    for calls that require oauth.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        create_xsrf_cookie_if_needed(self)
        return func(self, *args, **kwargs)

    return wrapper


def get_xsrf_cookie_value():
    return cookie_util.get_cookie_value(XSRF_COOKIE_KEY)


def validate_xsrf_value():
    header_value = os.environ.get(XSRF_HEADER_KEY)
    cookie_value = get_xsrf_cookie_value()
    if not header_value and not cookie_value:
        return False   # not using xsrf; we fail of course, but no need to log
    if not header_value or not cookie_value or header_value != cookie_value:
        logging.info("Mismatch between XSRF header (%s) and cookie (%s)"
                     % (header_value, cookie_value))
        return False
        
    return True
