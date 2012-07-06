"""Decorators for verifying authentication and authorization of users.

These decorators are applied to flask handlers, and automatically
return a 401 if certain conditions aren't met.

@login_required: the user making the request has to be logged in.  For
   oauth, that means that the oauth token they use has to exist in our
   oauth map.  For cookies-based authentication, it means that there is
   a valid cookie (that could only have been created by a logged-in user).

@developer_required: like login_required, but the logged in user must have
   user_data.developer == True.

@moderator_required: like login_required, but the logged in user must have
   user_data.moderator == True.

@admin_required: like login_required, but the logged in user must be an
   admin.  (We use google's auth for this; users.current_user_is_admin()
   must be true.)

@login_required_and: the above are all special cases of this more generic
   decorator, which can be used when more complex access control is
   required.

@open_access: anyone can access this url, they don't need to be logged in.
   (They still must have a valid oauth credential or cookie, though.)
   This is used for urls that are not protected (developer-only, say)
   and do not have any user-specific information in them.

@manual_access_checking: anyone can access this url, they don't even
   need a valid oauth credential or cookie.  The expectation is the
   handler will do its own authentication.  This is primarily used
   for handlers that are part of the oauth handshake itself.

@oauth_consumers_must_be_anointed: unlike the above, which concern the
   user (the access-token, in oauth-speak), this concerns the platform
   the user is using to make its request (the consumer-token, in
   oauth-speak).  This says only certain consumers, such as our iPad
   app, can make such a request.  This obviously requires oauth; users
   trying to access this handler using cookies will automatically
   fail.
"""

from functools import wraps

from third_party import flask
from third_party.flask import request

from api.auth.auth_util import oauth_error_response, unauthorized_response
from api.auth.auth_models import OAuthMap

from oauth_provider.decorators import is_valid_request, validate_token
from oauth_provider.oauth import OAuthError

import user_util
import util
import os
import logging


class NotLoggedInError(Exception):
    pass


def verify_and_cache_oauth_or_cookie(request):
    """ For a given request, try to oauth-verify or cookie-verify it.

    If the request has a valid oauth token, we store all the auth
    info in a per-request global (for easy access) and return.

    If the request does not have a valid oauth token, but has a valid
    http cookie *and* a valid xsrf token, return.

    Otherwise -- including the cases where there is an oauth token or
    cookie but they're not valid, raise an OAuthError of one form or
    another.

    This function is designed to be idempotent: it's safe (and fast)
    to call multiple times on the same request.  It caches enough
    per-request information to avoid repeating expensive work.

    Arguments:
       request: A 'global' flask var holding the current active request.

    Raises:
       OAuthError: are not able to authenticate the current user.
         (Note we give OAuthError even when we're failing the
         cookie-based request, which is a bit of abuse of terminology
         since there's no oauth involved in that step.)
    """
    if hasattr(flask.g, "oauth_map"):
        # Already called this routine and succeeded, so no need to call again.
        return

    # is_valid_request() verifies this request has something in it
    # that looks like an oauth token.
    if is_valid_request(request):
        consumer, token, parameters = validate_token(request)
        if (not consumer) or (not token):
            raise OAuthError("Not valid consumer or token")

        # Store the OAuthMap containing all auth info in the request
        # global for easy access during the rest of this request.
        # We do this now because current_req_has_auth_credentials()
        # accesses oauth_map.
        flask.g.oauth_map = OAuthMap.get_from_access_token(token.key_)

        if not util.current_req_has_auth_credentials():
            # If our OAuth provider thinks you're logged in but the
            # identity providers we consume (Google/Facebook)
            # disagree, we act as if our token is no longer valid.
            del flask.g.oauth_map
            raise NotLoggedInError("verifying oauth token")

        # Child users cannot authenticate against our API via oauth unless the
        # oauth consumer is anointed by us. This stops children from approving
        # third party app data access.
        if not consumer.anointed and user_util.is_current_user_child():
            del flask.g.oauth_map
            raise NotLoggedInError("under-13 accounts are denied API access")

        # (We can do all the other global-setting after
        #  current_req_has_auth_credentials.)
        # Store enough information from the consumer token that we can
        # do anointed checks.
        # TODO(csilvers): is it better to just store all of
        # 'consumer'? Seems too big given we just need to cache this
        # one piece of information right now.
        flask.g.is_anointed = consumer.anointed

    elif util.allow_cookie_based_auth():
        # TODO(csilvers): simplify; this duplicates a lot of calls
        # (current_req_has_auth_credentials calls allow_cookie_based_auth too).
        # Would suffice to call util._get_current_user_id_from_cookies_unsafe()
        # and maybe auth_util.current_oauth_map_from_session_unsafe() as well.
        if not util.current_req_has_auth_credentials():
            raise NotLoggedInError("verifying cookie values")

    else:
        raise NotLoggedInError("looking at oauth headers and cookies")


def open_access(func):
    """Decorator that allows anyone to access a url."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # We try to read the oauth info, so we have access to login
        # data if the user *does* happen to be logged in, but if
        # they're not we don't worry about it.
        try:
            verify_and_cache_oauth_or_cookie(request)
        except (OAuthError, NotLoggedInError):
            pass
        return func(*args, **kwargs)

    assert "_access_control" not in wrapper.func_dict, \
           "Multiple auth decorators"
    wrapper._access_control = 'open-access'   # checked in api.route()
    return wrapper


def manual_access_checking(func):
    """Decorator that documents the site itself is doing authentication.

    This is intended for use by urls that are involved in the oauth
    handshake itself, and thus shouldn't be calling
    verify_and_cache_oauth_or_cookie(), since the oauth data may be in
    an unfinished or inconsistent state.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # For manual_access_checking we don't even try to read the
        # oauth data -- that's up for the handler to do itself.  This
        # makes manual_access_checking appropriate for handlers that
        # are part of the oauth-authentication process itself.
        return func(*args, **kwargs)

    assert "_access_control" not in wrapper.func_dict, \
           "Multiple auth decorators"
    wrapper._access_control = 'manual-access'   # checked in api.route()
    return wrapper


def login_required_and(admin_required=False,
                       developer_required=False,
                       moderator_required=False,
                       child_user_allowed=True,
                       demo_user_allowed=False,
                       phantom_user_allowed=True):
    """Decorator for validating an authenticated request.

    Checking oauth/cookie is the way to tell whether an API client is
    'logged in', since they can only have gotten an oauth token (or
    cookie token) via the login process.

    In addition to checking whether the user is logged in, this
    function also checks access based on the *type* of the user: if
    demo_user_allowed==False, for instance, and the logged-in user is
    a demo user, then access will be denied.

    (Exception: if the user is an admin user, then access is *always*
    allowed, and the only check we make is if they're logged in.)

    The default values specify the default permissions: for instance,
    phantom users are considered a valid user by this routine, and
    under-13 users are allowed access all urls unless explicitly
    stated otherwise.

    (Exception: under-13 users are always disallowed for oauth requests
    unless the oauth consumer is preapproved/anointed by us. No third party
    apps can access under-13 account data.)

    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                verify_and_cache_oauth_or_cookie(request)
            except OAuthError, e:
                return oauth_error_response(e)
            except NotLoggedInError, e:
                # TODO(csilvers): just count how often this happens intead
                # of logging.  Why warn about something we can't control?
                # The only reason is it's possible this is caused by a bug.
                logging.warning('No login info found via %s\nCookie: %s'
                                % (e, os.environ.get('HTTP_COOKIE', '')))
                return unauthorized_response()

            try:
                user_util.verify_login(admin_required, developer_required,
                                       moderator_required, child_user_allowed,
                                       demo_user_allowed, phantom_user_allowed)
            except user_util.LoginFailedError:
                return unauthorized_response()

            return func(*args, **kwargs)

        # For purposes of IDing this decorator, just store the True arguments.
        all_local_vars = locals()
        arg_names = [var for var in all_local_vars if
                     all_local_vars[var] and
                     var not in ('func', 'wrapper', 'all_arg_names')]
        auth_decorator = 'login-required(%s)' % ','.join(arg_names)
        assert "_access_control" not in wrapper.func_dict, \
               ("Mutiple auth decorators: %s and %s"
                % (wrapper._access_control, auth_decorator))
        wrapper._access_control = auth_decorator   # checked in api.route()
        return wrapper

    return decorator


def admin_required(func):
    return login_required_and(admin_required=True)(func)


def developer_required(func):
    return login_required_and(developer_required=True)(func)


def moderator_required(func):
    return login_required_and(moderator_required=True)(func)


def login_required(func):
    """Decorator for validating an authenticated request.

    Checking oauth/cookie is the way to tell whether an API client is
    'logged in', since they can only have gotten an oauth token (or
    cookie token) via the login process.

    Note that phantom users with exercise data is considered
    a valid user -- see the default values for login_required_and().
    """
    return login_required_and()(func)


def oauth_consumers_must_be_anointed(func):
    """ Check that if a client is an oauth client, it's an 'anointed' one.

    This is a bit different from user authentication -- it only cares
    about the oauth *consumer* token.  That is, we don't care who the
    user is, we care what app (or script, etc) they are using to make
    this API call.  Some apps, such as the Khan iPad app, are
    'annointed', and have powers that normal API callers don't.

    NOTE: If the client is accessing via cookies and not via oauth, we
    always succeed.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # This checks flask.g.is_anointed, though only if the
        # request was an oauth request (and not a cookie request).
        if is_valid_request(request):   # only check if we're an oauth req.
            try:
                verify_and_cache_oauth_or_cookie(request)
                if not getattr(flask.g, "is_anointed", False):
                    raise OAuthError("Consumer access denied.")
            except OAuthError, e:
                return oauth_error_response(e)
            except NotLoggedInError, e:
                # TODO(csilvers): just count how often this happens intead
                # of logging.  Why warn about something we can't control?
                # The only reason is it's possible this is caused by a bug.
                logging.warning('is_anointed: no login info found via %s' % e)
                return unauthorized_response()
        return func(*args, **kwargs)

    return wrapper
