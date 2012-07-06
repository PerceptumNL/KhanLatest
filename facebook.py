#!/usr/bin/env python
#
# Copyright 2010 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Python client library for the Facebook Platform.

This client library is designed to support the Graph API and the official
Facebook JavaScript SDK, which is the canonical way to implement
Facebook authentication. Read more about the Graph API at
http://developers.facebook.com/docs/api. You can download the Facebook
JavaScript SDK at http://github.com/facebook/connect-js/.

If your application is using Google AppEngine's webapp framework, your
usage of this module might look like this:

    user = facebook.get_user_from_cookie_patched(self.request.cookies, key, secret)
    if user:
        graph = facebook.GraphAPI(user["access_token"])
        profile = graph.get_object("me")
        friends = graph.get_connections("me", "friends")

* Modified by Ben Kamens...
* ...to fix urllib bug on GAE:
*   https://github.com/spoon16/python-sdk/commit/1785d233b8cfd8309ddd1ae99918266c61d96327
* ...and to support the Facebook JS SDK's OAuth scheme:
*   http://stackoverflow.com/questions/7585488/python-oauth-2-0-new-fbsr-facebook-cookie-error-validating-verification-code 

"""

import cgi
import hashlib
import hmac
import base64
import logging
import urllib
import urllib2

from google.appengine.api import urlfetch_errors

# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json


class GraphAPI(object):
    """A client for the Facebook Graph API.

    See http://developers.facebook.com/docs/api for complete documentation
    for the API.

    The Graph API is made up of the objects in Facebook (e.g., people, pages,
    events, photos) and the connections between them (e.g., friends,
    photo tags, and event RSVPs). This client provides access to those
    primitive types in a generic way. For example, given an OAuth access
    token, this will fetch the profile of the active user and the list
    of the user's friends:

       graph = facebook.GraphAPI(access_token)
       user = graph.get_object("me")
       friends = graph.get_connections(user["id"], "friends")

    You can see a list of all of the objects and connections supported
    by the API at http://developers.facebook.com/docs/reference/api/.

    You can obtain an access token via OAuth or by using the Facebook
    JavaScript SDK. See http://developers.facebook.com/docs/authentication/
    for details.

    If you are using the JavaScript SDK, you can use the
    get_user_from_cookie_patched() method below to get the OAuth access token
    for the active user from the cookie saved by the SDK.
    """
    def __init__(self, access_token=None):
        self.access_token = access_token

    def get_object(self, id, **args):
        """Fetchs the given object from the graph."""
        return self.request(id, args)

    def get_objects(self, ids, **args):
        """Fetchs all of the given object from the graph.

        We return a map from ID to object. If any of the IDs are invalid,
        we raise an exception.
        """
        args["ids"] = ",".join(ids)
        return self.request("", args)

    def get_connections(self, id, connection_name, **args):
        """Fetchs the connections for given object."""
        return self.request(id + "/" + connection_name, args)

    def put_object(self, parent_object, connection_name, **data):
        """Writes the given object to the graph, connected to the given parent.

        For example,

            graph.put_object("me", "feed", message="Hello, world")

        writes "Hello, world" to the active user's wall. Likewise, this
        will comment on a the first post of the active user's feed:

            feed = graph.get_connections("me", "feed")
            post = feed["data"][0]
            graph.put_object(post["id"], "comments", message="First!")

        See http://developers.facebook.com/docs/api#publishing for all of
        the supported writeable objects.

        Most write operations require extended permissions. For example,
        publishing wall posts requires the "publish_stream" permission. See
        http://developers.facebook.com/docs/authentication/ for details about
        extended permissions.
        """
        assert self.access_token, "Write operations require an access token"
        return self.request(parent_object + "/" + connection_name, post_args=data)

    def put_wall_post(self, message, attachment={}, profile_id="me"):
        """Writes a wall post to the given profile's wall.

        We default to writing to the authenticated user's wall if no
        profile_id is specified.

        attachment adds a structured attachment to the status message being
        posted to the Wall. It should be a dictionary of the form:

            {"name": "Link name"
             "link": "http://www.example.com/",
             "caption": "{*actor*} posted a new review",
             "description": "This is a longer description of the attachment",
             "picture": "http://www.example.com/thumbnail.jpg"}

        """
        return self.put_object(profile_id, "feed", message=message, **attachment)

    def put_comment(self, object_id, message):
        """Writes the given comment on the given post."""
        return self.put_object(object_id, "comments", message=message)

    def put_like(self, object_id):
        """Likes the given post."""
        return self.put_object(object_id, "likes")

    def delete_object(self, id):
        """Deletes the object with the given ID from the graph."""
        self.request(id, post_args={"method": "delete"})

    def request(self, path, args=None, post_args=None):
        """Fetches the given path in the Graph API.

        We translate args to a valid query string. If post_args is given,
        we send a POST request to the given path with the given arguments.
        """
        args = args or {}
        if self.access_token:
            if post_args is not None:
                post_args["access_token"] = self.access_token
            else:
                args["access_token"] = self.access_token
        post_data = None if post_args is None else urllib.urlencode(post_args)

        try:
            file = urllib2.urlopen("https://graph.facebook.com/" + path + "?" +
                                  urllib.urlencode(args), post_data)
        except urllib2.HTTPError, e:
            response = json.loads(e.read())
            raise GraphAPIError(response["error"]["type"],
                                response["error"]["message"],
                                response["error"]["code"])

        try:
            response = json.loads(file.read())
        finally:
            file.close()

        if response.get("error"):
            raise GraphAPIError(response["error"]["type"],
                                response["error"]["message"],
                                response["error"]["code"])
        return response


class GraphAPIError(Exception):
    """ Open Graph API Error

    A class to mirror the JSON error objects returned by Facebook. Ex:
    https://developers.facebook.com/docs/authentication/access-token-expiration/
    {
      "error": {
        "message": "Error validating access token: Session has expired at unix
                    time SOME_TIME. The current unix time is SOME_TIME.",
        "type": "OAuthException",
        "code": 190
      }
    }

    Arguments:
        type: a string specifying the type of Open Graph error (ex:
            "OAuthException")
        message: a string containing the error message (ex: "(#200) Requires
            extended permission: publish_actions")
        code: an integer specifying the error code returned by Facebook (ex: 200)
    """
    def __init__(self, type, message, code=0):
        Exception.__init__(self, message)
        self.type = type
        self.code = code


def get_user_from_cookie_patched(cookies, app_id, app_secret):
    """
    This patched version of get_user_from_cookie works with the new Facebook JS
    library's OAuth scheme.

    See http://stackoverflow.com/questions/7585488/python-oauth-2-0-new-fbsr-facebook-cookie-error-validating-verification-code 
    and https://gist.github.com/1190267

    Parses the cookie set by the official Facebook JavaScript SDK.

    cookies should be a dictionary-like object mapping cookie names to
    cookie values.

    If the user is logged in via Facebook, we return a dictionary with the
    keys "uid" and "access_token". The former is the user's Facebook ID,
    and the latter can be used to make authenticated requests to the Graph API.
    If the user is not logged in, we return None.

    This was based on code from the official Facebook JavaScript SDK that was
    at http://github.com/facebook/connect-js/. It has since been deprecated.
    Read more about Facebook authentication at
    http://developers.facebook.com/docs/authentication/.
    """

    cookie = cookies.get("fbsr_" + app_id, "")
    if not cookie:
        return None

    response = parse_signed_request(cookie, app_secret)
    if not response:
        return None

    args = dict(
        code = response['code'],
        client_id = app_id,
        client_secret = app_secret,
        redirect_uri = '',
    )

    tries = 3
    while tries > 0:
        try:
            file = urllib.urlopen(
                    "https://graph.facebook.com/oauth/access_token?" +
                    urllib.urlencode(args))
            break
        except urlfetch_errors.DownloadError, why:
            tries -= 1
            if tries > 1:
                logging.info(("Failed getting FB access token due to %s. " +
                              "Tries left: %s.") % (why, tries))
            elif tries > 0:
                logging.warning(("Failed getting FB access token due to %s. " +
                                 "Tries left: %s.") % (why, tries))
            else:
                raise  # Out of tries.

    try:
        token_response = file.read()
        access_token = cgi.parse_qs(token_response)["access_token"][-1]
    except Exception, e:
        logging.warning("Failed to get facebook access token: %s" % e)
        return None
    finally:
        file.close()

    return dict(
        uid = response["user_id"],
        access_token = access_token,
    )

def urlsafe_b64decode(str):
    """Perform Base 64 decoding for strings with missing padding."""

    l = len(str)
    pl = l % 4
    return base64.urlsafe_b64decode(str.ljust(l+pl, "="))

def parse_signed_request(signed_request, secret):
    """
    Parse signed_request given by Facebook (usually via POST),
    decrypt with app secret.

    See https://developers.facebook.com/docs/authentication/signed_request/
    for details.

    Arguments:
        signed_request -- Facebook's signed request given through POST
        secret -- Application's app_secret required to decrpyt signed_request

    Return:
        A dict containing the parsed, signed request. This is empty on error.
        On success, it will typically contain:
            issued_at: unix timestamp
            code: an OAuth code that can be converted to an access_token
            user_id: the Facebook User ID
            algorithm: Always "HMAC-SHA256"
    """

    if "." in signed_request:
        esig, payload = signed_request.split(".")
    else:
        logging.error("Malformed FB signed request [%s]" % signed_request)
        return {}

    sig = urlsafe_b64decode(str(esig))
    try:
        data = json.loads(urlsafe_b64decode(str(payload)))
    except Exception, e:
        logging.error("Error decoding FB signed request [%s]: %s" %
                      (signed_request, e))
        return {}

    if not isinstance(data, dict):
        logging.error("FB signed request payload is not a JSON dict [%s]" %
                      signed_request)
        return {}

    if data.get("algorithm", "").upper() == "HMAC-SHA256":
        if hmac.new(secret, payload, hashlib.sha256).digest() == sig:
            return data
        else:
            logging.error("Signature mismatch in FB signed request [%s]" %
                          signed_request)
    else:
        logging.error("FB signed request not HMAC-SHA256 encrypted [%s]" %
                      signed_request)
        return  {}

    return {}
