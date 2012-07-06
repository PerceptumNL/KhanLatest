"""Helper routines for automating tests that require oauth authentication.

This was written to support end-to-end tests on handlers that require
oauth authentication.  For instance, if we wanted to test the behavior
of /api/v1/user, in an automated fashion, we'd need some way of
getting oauth credentials (consumer token, request token, access
token).  Normally oauth requires manual intervention for some of these
tokens.  This file automates the process so no manual intervention is
necessary, while still testing (most of) the oauth-validation code-paths
in the khan academy code.

Example usage:
   stub_for_oauth()
   json_user_info = fetch_via_oauth('http://localhost:8088/api/v1/user')
   [...]
   unstub_for_oauth()
"""

import cgi
import copy
import os
import urllib2
import urlparse

# This isn't needed if running from runtests.py, which it probably
# is, but is useful if running by hand.
if False:
    # remote_api_shell has a fix-paths-for-appengine function, and
    # it's easy to find because it lives on $PATH (though not
    # necessarily $PYTHONPATH).  Note this changes $PYTHONPATH:
    import os
    import sys
    sys.path.extend([''] + os.environ.get('PATH', '').split(':'))
    import remote_api_shell
    remote_api_shell.fix_sys_path(include_google_sql_libs=False)
    os.environ['SERVER_SOFTWARE'] = 'Development (oauth-test remote-api)/1.0'

from google.appengine.api import apiproxy_stub_map
from google.appengine.ext.remote_api import remote_api_stub
from mock import patch
    
from oauth_provider import consts
from oauth_provider import models_oauth
from oauth_provider import oauth
import user_models
import handler_test_utils

_g_stub_map = None
_have_stubbed = False
_env_patcher = None


def stub_for_oauth():
    """Sets up infrastructure so the oauth calls can work."""
    # Technically, we could do this when making the first
    # fetch_via_oauth call, but we want the flexibility to add more
    # stuff at stub-time later, so we put in some code here.
    # fetch_via_oauth will complain if _g_stub_map isn't set.
    global _g_stub_map, _env_patcher
    _g_stub_map = copy.copy(apiproxy_stub_map.apiproxy)
    _env_patcher = patch.dict(os.environ, {
            'SERVER_SOFTWARE': 'Development (oauth-test remote-api)/1.0'})
    _env_patcher.start()


def _maybe_stub_dev_appserver(dev_appserver_url):
    """Use remote_api_stub to set up a user account, consumer key, etc.

    remote_api_stub (which is part of appengine), stubs out all
    appengine calls so they go to the remote server (dev_appserver_url).

    Arguments:
        dev_appserver_url: the machine:port pair your dev-appserver
           process is running, likely 'localhost:8080'
    """
    global _have_stubbed
    if _have_stubbed:
        return

    for protocol in ('http://', 'https://'):  # we want a hostname, not a proto
        if dev_appserver_url.startswith(protocol):
            dev_appserver_url = dev_appserver_url[len(protocol):]

    # Store the existing stubs so we can restore them later
    remote_api_stub.ConfigureRemoteApi(
        None,
        '/_ah/remote_api',
        auth_func=(lambda: ('test', 'test')),   # username/password
        servername=dev_appserver_url)
    _have_stubbed = True


def unstub_for_oauth():
    """Undoes the work of stub_for_oauth."""
    # This is not documented as a way to undo stubbing -- nothing is
    # -- so it's probably fragile.
    global _g_stub_map, _have_stubbed, _env_patcher
    if _g_stub_map:
        apiproxy_stub_map.apiproxy = copy.copy(_g_stub_map)
        _env_patcher.stop()
        _env_patcher = None
        _g_stub_map = None
        _have_stubbed = False


def _create_user(name):
    """Creates a user with the given username, and an email/pw based on it."""
    email = name + '@example.com'
    pw = name + '_password'
    user_data = user_models.UserData.insert_for(name, email)
    # Don't reset the password if it's already set as we expect, since
    # resetting the password can invalidate keys.
    if not user_data.validate_password(pw):
        user_data.set_password(pw)
    return (user_data, email, pw)


def _create_oauth_tokens(dev_appserver_url,
                         email_and_password_of_user_wanting_access, anointed):
    """Helper for _setup_dev_appserver_for_oauth, to create two token-sets."""
    if anointed:
        name = 'test_consumer_anointed'
    else:
        name = 'test_consumer_not_anointed'

    # First, we need to create a user.
    (user_data, _, _) = _create_user('test_user_for_oauth_token')

    # To start the oauth request, we need a consumer token.
    consumer_object = models_oauth.Consumer.get_or_insert(
        key_name=name,
        name=name,
        description=name,
        website='',
        user=user_data.user,
        status=consts.ACCEPTED,
        phone='',
        company='',
        anointed=anointed)
    if not consumer_object.secret:   # we just created it
        consumer_object.generate_random_codes()
    consumer = oauth.OAuthConsumer(consumer_object.key_,
                                   consumer_object.secret)

    # Next, create an oauth request token.
    request = oauth.OAuthRequest.from_consumer_and_token(
        consumer, http_url='%s/api/auth/request_token' % dev_appserver_url)
    request.sign_request(oauth.OAuthSignatureMethod_PLAINTEXT(),
                         consumer, None)

    request_token_req = urllib2.urlopen(request.to_url())
    if request_token_req.code != 200:
        raise RuntimeError('Unable to get the request token, '
                           'instead got %d: "%s"'
                           % (request_token_req.code,
                              request_token_req.read()))

    # Next, we need to register the request token in Khan Academy
    # oauth-map.  The response from the request-token fetch is the url
    # we need to hit to do this: probably /login/mobileoauth?<stuff>.
    # The only thing we need to add are the name and password of the
    # user who wants access (which can/will be different from the user
    # who created the consumer key, above).
    scheme, netloc, path, params, query, fragment = \
             urlparse.urlparse(request_token_req.geturl())
    query += ('&identifier=%s&password=%s'
              % email_and_password_of_user_wanting_access)
    oauth_map_url = urlparse.urlunparse((scheme, netloc, path, params,
                                            {}, fragment))
    oauth_map_req = urllib2.urlopen(oauth_map_url, query)
    contents = oauth_map_req.read()
    if contents != 'OK':
        raise RuntimeError('Unable to get the access token, instead got: "%s"'
                           % contents)
    # The url that we end up with after going through
    # /login/mobileauth, which yields a *second* request token.
    # TODO(csilvers): figure out what's going on here.
    oauth_map_key_and_secret = urlparse.urlparse(oauth_map_req.geturl())[4]
    oauth_map_token = oauth.OAuthToken.from_string(oauth_map_key_and_secret)

    # Finally, we can get the access token from the previous request token.
    request = oauth.OAuthRequest.from_consumer_and_token(
        consumer,
        token=oauth_map_token,
        http_url="%s/api/auth/access_token" % dev_appserver_url
        )
    request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(),
                         consumer, oauth_map_token)
    access_token_req = urllib2.urlopen(request.to_url())
    if access_token_req.code != 200:
        raise RuntimeError('Unable to get the access token, '
                           'instead got %d: "%s"'
                           % (access_token_req.code, access_token_req.read()))
    access_key_and_secret_str = access_token_req.read()
    access_token = oauth.OAuthToken.from_string(access_key_and_secret_str)

    return (consumer, access_token)


def _access_resource(full_url,
                     consumer,
                     access_token,
                     method="GET",
                     data=None,
                     headers=None):
    url = urlparse.urlparse(full_url)
    query_params = cgi.parse_qs(url.query)
    for key in query_params:
        query_params[key] = query_params[key][0]

    # Get a new request token for the specific url we want to fetch.
    oauth_request = oauth.OAuthRequest.from_consumer_and_token(
        consumer,
        token=access_token,
        http_url=full_url,
        parameters=query_params,
        http_method=method
        )
    oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(),
                               consumer, access_token)

    url = oauth_request.to_url()

    if headers is None:
        headers = {}

    request = urllib2.Request(url, data, headers)

    # Force override the request method to support 'PUT' and 'DELETE'
    #   See http://stackoverflow.com/questions/4511598)
    request.get_method = lambda: method

    return urllib2.urlopen(request).read().strip()


# We store the consumer and access tokens for each user, so we don't
# have to fetch them for every test (it's quite expensive to get them!)
_TOKEN_MAP = {}


def clear_oauth_tokens_cache():
    """Erases the cached values for consumer and access tokens."""
    # Not sure why you might need this, but it's always nice to
    # be able to reset the state when you're using global vars.
    #
    # Use this to clear cached tokens if you use remote_api_stub
    # to point to a different datastore.
    #
    # The unit test suite points to one remote datastore in
    # api.labs.labs_test and another in api.v1_endtoend_test.
    # Tokens from the first test are invalid in the second.
    global _TOKEN_MAP
    _TOKEN_MAP = {}


def fetch_via_oauth(url_to_fetch,
                    email_of_user_wanting_access=None,
                    password_of_user_wanting_access=None,
                    consumer_is_anointed=False,
                    method="GET",
                    data=None,
                    headers=None):
    """Fetches a given url (e.g. http://localhost:8080/api/v1/user)
    that requires oauth authentication, and returns the results.
    This function takes care of all the necessary oauth handshaking.

    The host at this url must accept remote-api calls via
    /_ah/remote_api.  The intended use is for it to be a dev_appserver
    instance.

    **NOTE**: this function also will stub out all appengine calls
    so they go to the remote api server (using remote_api_stub)!
    Be careful if you call appengine functions after calling this.
    TODO(csilvers): can we unstub at the end of this function?

    Arguments:
       url_to_fetch:
          The url to retrieve.  The host/port should be that of
          the local dev-appserver instance, probably localhost:8080.
          The protocol should probably be http://.

       email_of_user_wanting_access:
          This is who the oauth process will say is logging in (the
          'resource provider').  This user must exist in the khan db.
          You can create a user via
             user_data = user_models.UserData.insert_for('random_string',
                                                         'a@b.com')
             user_data.set_password('password')
          If you pass in None, we will use an 'internal' user we create.

       password_of_user_wanting_access:
          The password corresponding to the user specified via email.
          If you pass in None for email_of_user_wanting_access, the
          value here is ignored.

       consumer_is_anointed:
          oauth cares not only about the user it's retrieving
          information for, but also about the client (application)
          fetching the data.  Khan recognizes two classes of clients:
          anointed (like the ipad), and non-anointed (the default).
          Anointed clients can perform some actions that non-anointed
          ones cannot.  This boolean specifies whether you wish the
          oauth requeste to seem to come from an anointed client or
          a non-anointed client.

       method:
          GET, POST, PUT and DELETE are supported.

       data:
          Payload string for the request. Ignored for GET requests.

       headers:
          Dict of extra headers for the request.
          Default headers for the request will not be overwritten.
          e.g. {'Content-type' : 'application/json'}


    Returns:
       The response from fetching the given url.  The HTTP response code
       is not returned.
    """
    user_pw_pair = (email_of_user_wanting_access,
                    password_of_user_wanting_access)
    scheme, hostname, path, params, query, fragment = \
            urlparse.urlparse(url_to_fetch)
    dev_appserver_url = urlparse.urlunparse((scheme, hostname, '', '', '', ''))

    # Make sure the user did the stubbing, and finish off the work if so.
    if not _g_stub_map:
        raise RuntimeError('Must call stub_for_oauth() before oauth calls.')
    _maybe_stub_dev_appserver(hostname)

    # If the caller doesn't care who the user is making the request,
    # we'll just use one that we make and keep around.
    if user_pw_pair == (None, None):
        (_, user, pw) = _create_user('test_user_for_oauth_fetch')
        user_pw_pair = (user, pw)

    # If we already have the tokens cached, don't refetch (it's expensive).
    # The key is exactly the set of arguments for _create_oauth_tokens.
    token_map_key = (dev_appserver_url, user_pw_pair, consumer_is_anointed)
    if token_map_key in _TOKEN_MAP:
        consumer, access_token = _TOKEN_MAP[token_map_key]
    else:
        consumer, access_token = _create_oauth_tokens(*token_map_key)
        _TOKEN_MAP[token_map_key] = (consumer, access_token)

    return _access_resource(
        url_to_fetch, consumer, access_token,
        method, data, headers)


class OAuthRequestFetcher(object):
    def set_user(self, moderator=False, developer=False, admin=False,
                 child=False, anointed_consumer=False):
        """Change the user for subsequent fetch calls to have these perms.

        Uses user accounts created by testutil.make_test_db.Users, which are
        stored in the database in testutil/test_db.sqlite
        """
        self.email = 'user1@example.com'
        self.password = 'user1'

        if moderator:
            assert not (developer or admin), 'Can only have one right now'

            self.email = 'moderator@example.com'
            self.password = 'moderator'

        if developer:
            assert not (moderator or admin), 'Can only have one right now'

            self.email = 'developer@example.com'
            self.password = 'developer'

        if child:
            self.email = 'child@example.com'
            self.password = 'child'

        if admin:
            assert not (moderator or developer), 'Can only have one right now'
            raise NotImplementedError('TODO(csilvers): make an admin user')

        self.consumer_is_anointed = anointed_consumer

    def fetch(self, path, method, data=None, headers=None):
        """path is e.g. '/api/v1/users'. Does a lot, so makes a test large."""
        return fetch_via_oauth(
            handler_test_utils.appserver_url + path,
            email_of_user_wanting_access=self.email,
            password_of_user_wanting_access=self.password,
            consumer_is_anointed=self.consumer_is_anointed,
            method=method,
            data=data,
            headers=headers)
