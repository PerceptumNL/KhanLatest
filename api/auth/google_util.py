import urllib

from google.appengine.api import oauth as google_oauth
from google.appengine.api.oauth.oauth_api import InvalidOAuthTokenError

from third_party.flask import request, redirect

from oauth_provider.oauth import OAuthError

import layer_cache

from api.route_decorator import route
from api.auth.auth_util import (authorize_token_redirect,
                                pretty_error_response, oauth_error_response,
                                OAuthBadRequestError)
from api.auth.google_oauth_client import GoogleOAuthClient
from api.auth.auth_models import OAuthMap
from api.decorators import jsonify
from api.auth import decorators


# Utility request handler to let Google authorize the OAuth token/request and
# return the authorized user's id and email address.
@route("/api/auth/current_google_oauth_user_id_and_email")
@decorators.manual_access_checking
@jsonify
def current_google_oauth_user_id_and_email():
    user = None

    try:
        user = google_oauth.get_current_user()
    except InvalidOAuthTokenError:
        # Ignore invalid auth tokens, user is not logged in
        pass

    if user:
        return ["http://googleid.khanacademy.org/" + user.user_id(),
                user.email()]

    return []


@layer_cache.cache_with_key_fxn(
    lambda oauth_map: ("google_id_and_email_from_oauth_token_%s" %
                       oauth_map.google_access_token),
    layer=layer_cache.Layers.Memcache)
def get_google_user_id_and_email_from_oauth_map(oauth_map):
    google_client = GoogleOAuthClient()
    return google_client.access_user_id_and_email(oauth_map)


def google_request_token_handler(oauth_map):
    # Start Google request token process
    try:
        google_client = GoogleOAuthClient()
        google_token = google_client.fetch_request_token(oauth_map)
    except Exception, e:
        return oauth_error_response(OAuthError(e.message))

    oauth_map.google_request_token = google_token.key
    oauth_map.google_request_token_secret = google_token.secret
    oauth_map.put()

    params = {"oauth_token": oauth_map.google_request_token}
    if oauth_map.is_mobile_view():
        # Add google-specific mobile view identifier
        params["btmpl"] = "mobile"

    return redirect("http://www.khanacademie.nl/_ah/OAuthAuthorizeToken?%s" %
                    urllib.urlencode(params))


def retrieve_google_access_token(oauth_map):
    # Start Google access token process
    import logging
    logging.error("import access token")
    google_client = GoogleOAuthClient()
    logging.error("import access token")
    google_token = google_client.fetch_access_token(oauth_map)

    logging.error("1")
    oauth_map.google_access_token = google_token.key
    logging.error(google_token.key)
    logging.error("2")
    oauth_map.google_access_token_secret = google_token.secret
    logging.error(google_token.secret)

    return oauth_map


@route("/api/auth/google_token_callback", methods=["GET"])
@decorators.manual_access_checking
def google_token_callback():
    oauth_map = OAuthMap.get_by_id_safe(request.values.get("oauth_map_id"))

    if not oauth_map:
        return oauth_error_response(
            OAuthError("Unable to find OAuthMap by id."))

    if oauth_map.google_verification_code:
        return oauth_error_response(OAuthError("Request token already has "
                                               "google verification code."))

    oauth_map.google_verification_code = request.values.get("oauth_verifier")

    try:
        oauth_map = retrieve_google_access_token(oauth_map)
    except OAuthBadRequestError, e:
        return pretty_error_response('Unable to log in with Google.')
    except OAuthError, e:
        return oauth_error_response(e)

    oauth_map.put()

    return authorize_token_redirect(oauth_map)
