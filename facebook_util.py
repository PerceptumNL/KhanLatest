import os
import Cookie
import httplib
import logging
import unicodedata

from google.appengine.api import urlfetch

from app import App
import facebook
import layer_cache
import request_cache

FACEBOOK_ID_PREFIX = "http://facebookid.khanacademy.org/"

# TODO(benkomalo): rename these methods to have consistent naming
#   ("facebook" vs "fb")


def is_facebook_user_id(user_id):
    return user_id and user_id.startswith(FACEBOOK_ID_PREFIX)


def get_facebook_nickname_key(user_id):
    return "facebook_nickname_%s" % user_id


@request_cache.cache_with_key_fxn(get_facebook_nickname_key)
@layer_cache.cache_with_key_fxn(
        get_facebook_nickname_key,
        layer=layer_cache.Layers.Memcache | layer_cache.Layers.Datastore,
        persist_across_app_versions=True)
def get_facebook_nickname(user_id):

    id = user_id.replace(FACEBOOK_ID_PREFIX, "")
    graph = facebook.GraphAPI()

    try:
        profile = graph.get_object(id)
        # Workaround http://code.google.com/p/googleappengine/issues/detail?id=573
        # Bug fixed, utf-8 and nonascii is okay
        return unicodedata.normalize('NFKD', profile["name"]).encode('utf-8', 'ignore')
    except (facebook.GraphAPIError, urlfetch.DownloadError, AttributeError,
            httplib.HTTPException):
        # In the event of an FB error, don't cache the result.
        return layer_cache.UncachedResult(user_id)


def get_current_facebook_id_from_cookies():
    """ Get Facebook ID of current logged in Facebook user.

    "Current logged in Facebook user" refers to the user who has logged into
    the Khan Academy /Facebook app/. While this most often occurs when the
    user clicks on the "Facebook" button on the Khan Academy login page, this
    could also happen when a user is prompted with a Facebook login dialog,
    such as when sharing badges in the first version of Open Graph integration.

    Returns:
        A Unicode string consisting only of numbers. For example, this would
        return "4" for Mark Zuckerberg.
    """

    return get_user_id_from_profile(get_profile_from_cookies(), False)


def get_current_facebook_user_id_from_cookies():
    """ Get Khan Academy Facebook ID of current logged in Facebook user.

    "Current logged in Facebook user" refers to the user who has logged into
    the Khan Academy /Facebook app/. While this most often occurs when the
    user clicks on the "Facebook" button on the Khan Academy login page, this
    could also happen when a user is prompted with a Facebook login dialog,
    such as when sharing badges in the first version of Open Graph integration.

    Returns:
        A Unicode string consisting of FACEBOOK_ID_PREFIX concatenated with
        the user's Facebook ID. For example, this would return
        "http://facebookid.khanacademy.org/4" for Mark Zuckerberg.
    """

    return get_user_id_from_profile(get_profile_from_cookies())


def delete_fb_cookies(handler):
    """ Given the request handler, have it send headers to delete all FB cookies associated with Khan Academy. """

    if App.facebook_app_id:
        # Note that Facebook also sets cookies on ".www.khanacademy.org"
        # and "www.khanacademy.org" so we need to clear both.
        handler.delete_cookie_including_dot_domain('fbsr_' + App.facebook_app_id)
        handler.delete_cookie_including_dot_domain('fbm_' + App.facebook_app_id)


def get_facebook_user_id_from_oauth_map(oauth_map):
    if oauth_map:
        profile = _get_profile_from_fb_token(oauth_map.facebook_access_token)
        return get_user_id_from_profile(profile)
    return None


def get_fb_email_from_oauth_map(oauth_map):
    """Return the e-mail of the current logged in Facebook user, if possible.

    A user's Facebook e-mail is the one specified as her primary e-mail account
    in Facebook (not user@facebook.com).

    This may return None if no valid Facebook credentials were found in the
    OAuthmap.
    """

    if oauth_map:
        profile = _get_profile_from_fb_token(oauth_map.facebook_access_token)
        if profile:
            return profile.get("email", None)
    return None


def get_user_id_from_profile(profile, full_user_id=True):
    """ Get Facebook ID from Facebook profile data and cache Facebook nickname.

    Args:
        full_user_id: If true, return the full Khan Academy Facebook user ID
            (ex: "http://facebookid.khanacademy.org/4"). If false, return just
            the Facebook user ID ("4") without the FACEBOOK_ID_PREFIX.
    """

    if profile is not None and "name" in profile and "id" in profile:
        # Workaround http://code.google.com/p/googleappengine/issues/detail?id=573
        name = unicodedata.normalize('NFKD', profile["name"]).encode('utf-8', 'ignore')

        user_id = FACEBOOK_ID_PREFIX + profile["id"]

        if not full_user_id:
            return profile["id"]

        # Cache any future lookup of current user's facebook nickname in this request
        request_cache.set(get_facebook_nickname_key(user_id), name)

        return user_id

    return None

def get_fb_email_from_cookies():
    """ Return the e-mail of the current logged in Facebook user, if possible.

    A user's Facebook e-mail is the one specified as her primary e-mail account
    in Facebook (not user@facebook.com).

    This may return None if no valid Facebook credentials were found, or
    if the user did not allow us to see her e-mail address.
    """

    profile = get_profile_from_cookies()
    if profile:
        return profile.get("email", None)
    return None

def get_profile_from_cookies():
    """ Get Facebook profile data of current logged in Facebook user

    Returns:
        A dict of Facebook profile data of the current logged in Facebook user.
        For example, this would return the following for Mark Zuckerberg:

        {
           "id": "4",
           "name": "Mark Zuckerberg",
           "first_name": "Mark",
           "last_name": "Zuckerberg",
           "link": "https://www.facebook.com/zuck",
           "username": "zuck",
           "gender": "male",
           "locale": "en_US"
        }

    """

    if App.facebook_app_secret is None:
        return None

    cookies = None
    try:
        cookies = Cookie.BaseCookie(os.environ.get('HTTP_COOKIE', ''))
    except Cookie.CookieError, error:
        logging.debug("Ignoring Cookie Error, skipping Facebook login: '%s'" % error)

    if cookies is None:
        return None

    morsel_key = "fbsr_" + App.facebook_app_id
    morsel = cookies.get(morsel_key)
    if morsel and morsel.value:
        parsed_request = parse_signed_request_cached(
                morsel.value, App.facebook_app_secret)
        if parsed_request and 'user_id' in parsed_request:
            return get_profile_from_cookie_key_value(morsel_key,
                                                     morsel.value,
                                                     parsed_request['user_id'])

    return None


@request_cache.cache_with_key_fxn(
        lambda signed_request, secret: "%s:%s" % (secret, signed_request))
def parse_signed_request_cached(signed_request, secret):
    """Similar to facebook.parse_signed_request, but using the requestcache."""
    return facebook.parse_signed_request(signed_request, secret)


def get_profile_cache_key(cookie_key, cookie_value, user_id):
    return "facebook:profile_from_userid:%s" % user_id


@request_cache.cache_with_key_fxn(key_fxn=get_profile_cache_key)
@layer_cache.cache_with_key_fxn(
        key_fxn=get_profile_cache_key,
        layer=layer_cache.Layers.Memcache,
        persist_across_app_versions=True)
def get_profile_from_cookie_key_value(cookie_key, cookie_value, user_id):
    """ Communicate with Facebook to get a FB profile associated with
    the specific cookie value.

    Because this talks to Facebook via an HTTP request, this is cached
    in memcache to avoid constant communication while a FB user is
    browsing the site. If we encounter an error or fail to load
    a Facebook profile, the results are not cached in memcache.

    However, we also cache in request_cache because if we fail to load
    a Facebook profile, we only want to do that once per request.
    """

    fb_auth_dict = facebook.get_user_from_cookie_patched(
            {cookie_key: cookie_value},
            App.facebook_app_id,
            App.facebook_app_secret)

    if fb_auth_dict:
        profile = _get_profile_from_fb_token(fb_auth_dict["access_token"])

        if profile:
            return profile

    # Don't cache any missing results in memcache
    return layer_cache.UncachedResult(None)


def _get_profile_from_fb_token(access_token):

    if App.facebook_app_secret is None:
        return None

    if not access_token:
        logging.debug("Empty access token")
        return None

    profile = None

    c_facebook_tries_left = 4
    while not profile and c_facebook_tries_left > 0:
        try:
            graph = facebook.GraphAPI(access_token)
            profile = graph.get_object("me")
        except (facebook.GraphAPIError, urlfetch.DownloadError, AttributeError,
                httplib.HTTPException), error:
            # GraphAPIError code is 190 for invalid access token
            # https://developers.facebook.com/docs/authentication/access-token-expiration/
            if type(error) == facebook.GraphAPIError and error.code == 190:
                c_facebook_tries_left = 0
                logging.error(("Ignoring '%s'. Assuming access_token is no"
                    "longer valid: %s\n%s") % (error.type, access_token, error.message))
            else:
                c_facebook_tries_left -= 1

                if c_facebook_tries_left > 1:
                    logging.info("Ignoring Facebook graph error '%s'. Tries left: %s" % (error, c_facebook_tries_left))
                elif c_facebook_tries_left > 0:
                    logging.warning("Ignoring Facebook graph error '%s'. Last try." % error)
                else:
                    logging.error("Last Facebook graph try failed with error '%s'." % error)

    return profile
