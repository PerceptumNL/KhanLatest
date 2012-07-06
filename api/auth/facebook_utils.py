import datetime
import urllib

from third_party.flask import request, redirect

from app import App
from api.route_decorator import route
from api.auth.auth_util import (pretty_error_response, oauth_error_response,
                                get_response, get_parsed_params,
                                authorize_token_redirect, OAuthBadRequestError)
from api.auth.auth_models import OAuthMap
from api.auth import decorators
import layer_cache
from oauth_provider.oauth import OAuthError

FB_URL_OAUTH_DIALOG = "https://www.facebook.com/dialog/oauth"
FB_URL_ACCESS_TOKEN = "https://graph.facebook.com/oauth/access_token"


def facebook_request_token_handler(oauth_map):
    # Start Facebook request token process
    params = {
                "client_id": App.facebook_app_id,
                "redirect_uri": get_facebook_token_callback_url(oauth_map),
                "scope": "email",
            }

    if oauth_map.is_mobile_view():
        # Add FB-specific mobile view identifier
        params["display"] = "touch"

    return redirect("%s?%s" % (FB_URL_OAUTH_DIALOG, urllib.urlencode(params)))


@layer_cache.cache()
def get_facebook_app_access_token():
    """Gets the Facebook App Access token

    There is one app access token for the entire Khan Academy Facebook app.
    It is the same for all users and requests. It only changes when the app
    secret changes (very rarely; done through the Facebook developer website),
    so we cache it using setting_model.Setting, which stores
    per-application key-value pairs for app-wide settings. In case the
    Facebook app secret is changed (on the Facebook developer site), the
    request to Facebook is performed for each deployed GAE version.

    More about the app access token here:
    https://developers.facebook.com/docs/opengraph/using-app-tokens/
    """

    params = {
                "client_id": App.facebook_app_id,
                "client_secret": App.facebook_app_secret,
                "grant_type": "client_credentials"
                }

    response = get_response(FB_URL_ACCESS_TOKEN, params)
    response_params = get_parsed_params(response)

    if response_params:
        response_array = response_params.get("access_token")
        if response_array:
            token = response_array[0]
            return token

    raise OAuthError("Cannot get access_token from Facebook's " +
                         "/oauth/access_token response")


def retrieve_facebook_access_token(oauth_map):
    # Start Facebook access token process
    params = {
                "client_id": App.facebook_app_id,
                "client_secret": App.facebook_app_secret,
                "redirect_uri": get_facebook_token_callback_url(oauth_map),
                "code": oauth_map.facebook_authorization_code,
                }

    response = get_response(FB_URL_ACCESS_TOKEN, params)

    response_params = get_parsed_params(response)
    if not response_params or not response_params.get("access_token"):
        raise OAuthError("Cannot get access_token from Facebook's " +
                         "/oauth/access_token response")

    # Associate our access token and Google/Facebook's
    oauth_map.facebook_access_token = response_params["access_token"][0]

    expires_seconds = 0
    try:
        expires_seconds = int(response_params["expires"][0])
    except (ValueError, KeyError):
        pass

    if expires_seconds:
        oauth_map.expires = (datetime.datetime.now() +
                             datetime.timedelta(seconds=expires_seconds))

    return oauth_map


# Associate our request or access token with Facebook's tokens
@route("/api/auth/facebook_token_callback", methods=["GET"])
@decorators.manual_access_checking
def facebook_token_callback():
    oauth_map = OAuthMap.get_by_id_safe(request.values.get("oauth_map_id"))

    if not oauth_map:
        return oauth_error_response(OAuthError(
                "Unable to find OAuthMap by id."))

    if oauth_map.facebook_authorization_code:
        return oauth_error_response(OAuthError(
                "Request token already has facebook authorization code."))

    oauth_map.facebook_authorization_code = request.values.get("code")

    try:
        oauth_map = retrieve_facebook_access_token(oauth_map)
    except OAuthBadRequestError, e:
        return pretty_error_response('Unable to log in with Facebook.')
    except OAuthError, e:
        return oauth_error_response(e)

    oauth_map.put()

    return authorize_token_redirect(oauth_map)


def get_facebook_token_callback_url(oauth_map):
    return "%sapi/auth/facebook_token_callback?oauth_map_id=%s" % (
            request.host_url, oauth_map.key().id())
