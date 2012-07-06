import datetime
import json
import logging
import os
import re
import time
import urllib

from google.appengine.api import mail, users

import auth.cookies
import auth.passwords
import cookie_util
import facebook_util
import request_handler
import shared_jinja
import transaction_util
import uid
import url_util
import user_models
import user_util
import util

from api import jsonify
from api.auth import auth_util
from api.auth.auth_models import OAuthMap
from app import App
from auth import age_util
from auth.tokens import AuthToken, PasswordResetToken, TransferAuthToken
from counters import user_counter
from experiments import CoreMetrics
import gae_bingo.gae_bingo
from models import UserData
import notifications
from phantom_users.phantom_util import get_phantom_user_id_from_cookies


class Login(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        if self.request_bool("form", default=False):
            self.render_login_form()
        else:
            self.render_login_outer()

    def request_continue_url(self, key="continue", default="/"):
        cont = super(Login, self).request_continue_url(key, default)

        # Always go to /postlogin after a /login, regardless if the continue
        # url actually specified it or not. Important things happen there.
        return url_util.create_post_login_url(cont)

    def render_login_outer(self):
        """Render the login page.

        Note that part of the contents of this page is hosted on an iframe
        and rendered by this same RequestHandler (render_login_form)
        """
        cont = self.request_continue_url()
        direct = self.request_bool('direct', default=False)

        user_data = UserData.current()
        if user_data and not user_data.is_phantom:
            # Don't let users see the login page if they're already logged in.
            # This avoids dangerous edge cases in which users have conflicting
            # Google/FB cookies, and google.appengine.api.users.get_current_user
            # returns a different user than the actual person logged in.
            self.redirect(cont)
            return

        template_values = {
                           'continue': cont,
                           'direct': direct,
                           'google_url': users.create_login_url(cont),
                           }

        self.render_jinja2_template('login.html', template_values)


    def render_login_form(self, identifier=None, errors=None):
        """Render the form with the username/password fields. This is
        hosted an in iframe in the main login page.

        errors - a dictionary of possible errors from a previous login that
                 can be highlighted in the UI of the login page
        """
        cont = self.request_continue_url()
        direct = self.request_bool('direct', default=False)

        template_values = {
                           'continue': cont,
                           'direct': direct,
                           'identifier': identifier or "",
                           'errors': errors or {},
                           'google_url': users.create_login_url(cont),
                           }

        self.render_jinja2_template('login_contents.html', template_values)

    @user_util.open_access
    def post(self):
        """Handle a POST from the login form.

        This happens when the user attempts to login with an identifier (email
        or username) and password.
        """

        cont = self.request_continue_url()

        # Authenticate via username or email + password
        identifier = self.request_string('identifier')
        password = self.request_string('password')
        if not identifier or not password:
            errors = {}
            if not identifier: errors['noemail'] = True
            if not password: errors['nopassword'] = True
            self.render_json({'errors': errors})
            return

        user_data = UserData.get_from_username_or_email(identifier.strip())
        if not user_data or not user_data.validate_password(password):
            errors = {}
            errors['badlogin'] = True
            # TODO(benkomalo): IP-based throttling of failed logins?
            self.render_json({'errors': errors})
            return

        # Successful login
        Login.return_login_json(self, user_data, cont)

    @staticmethod
    def return_login_json(handler, user_data, cont="/"):
        """Handle a successful login for a user by redirecting them
        to the PostLogin URL with the auth token, which will ultimately set
        the auth cookie for them.

        This level of indirection is needed since the Login/Register handlers
        must accept requests with password strings over https, but the rest
        of the site is not (yet) using https, and therefore must use a
        non-https cookie.
        """

        auth_token = AuthToken.for_user(user_data)
        handler.response.write(jsonify.jsonify({
                    'auth': auth_token.value,
                    'continue': cont
                }, camel_cased=True))

class MobileOAuthLogin(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.render_login_page()

    def render_login_page(self, error=None):
        self.render_jinja2_template('login_mobile_oauth.html', {
            "oauth_map_id": self.request_string("oauth_map_id", default=""),
            "anointed": self.request_bool("an", default=False),
            "view": self.request_string("view", default=""),
            "error": error,
        })

    @user_util.manual_access_checking
    def post(self):
        """POST submissions are for username/password based logins to
        acquire an OAuth access token.
        """

        identifier = self.request_string('identifier')
        password = self.request_string('password')
        if not identifier or not password:
            self.render_login_page("Please enter your username and password.")
            return

        user_data = UserData.get_from_username_or_email(identifier.strip())
        if not user_data or not user_data.validate_password(password):
            # TODO(benkomalo): IP-based throttling of failed logins?
            self.render_login_page("Your login or password is incorrect.")
            return

        # Successful login - convert to an OAuth access_token
        oauth_map_id = self.request_string("oauth_map_id", default="")
        oauth_map = OAuthMap.get_by_id_safe(oauth_map_id)
        if not oauth_map:
            self.render_login_page("Unable to find OAuthMap by id.")
            return

        # Mint the token and persist to the oauth_map
        oauth_map.khan_auth_token = AuthToken.for_user(user_data).value
        oauth_map.put()

        # Flush the "apply phase" of the above put() to ensure that subsequent
        # retrievals of this OAuthmap returns fresh data. GAE's HRD can
        # otherwise take a second or two to propagate the data, and the
        # following authorize endpoint redirect below could happen quicker
        # than that in some cases.
        oauth_map = OAuthMap.get(oauth_map.key())

        # Need to redirect back to the http authorize endpoint
        return auth_util.authorize_token_redirect(oauth_map, force_http=True)

def _upgrade_phantom_into(phantom_data, target_data):
    """Attempt to merge a phantom user into a target user.
    Will bail if any signs that the target user has previous activity.
    """

    # First make sure user has 0 points and phantom user has some activity
    if (phantom_data and phantom_data.points > 0):
        if phantom_data.consume_identity(target_data):
            # Phantom user just converted into a real user.
            user_counter.add(1)

            # Clear all "login" notifications
            notifications.PhantomNotification.clear(phantom_data)
            return True
    return False

class PostLogin(request_handler.RequestHandler):
    def _consume_auth_token(self):
        """Check to see if a valid auth token is specified as a param
        in the request, so it can be converted into a cookie
        and used as the identifier for the current and future requests.
        """

        auth_stamp = self.request_string("auth")
        if auth_stamp:
            # If an auth stamp is provided, it means they logged in using
            # a password via HTTPS, and it has redirected here to postlogin
            # to set the auth cookie from that token. We can't rely on
            # UserData.current() yet since no cookies have yet been set.
            token = AuthToken.for_value(auth_stamp)
            if not token:
                logging.error("Invalid authentication token specified")
            else:
                user_data = UserData.get_from_user_id(token.user_id)
                if not user_data or not token.is_valid(user_data):
                    logging.error("Invalid authentication token specified")
                else:
                    # Good auth stamp - set the cookie for the user, which
                    # will also set it for this request.
                    auth.cookies.set_auth_cookie(self, user_data, token)
                    return True
        return False

    def _finish_and_redirect(self, cont):
        # Always delete phantom user cookies on login
        self.delete_cookie('ureg_id')
        self.redirect(cont)

    @user_util.manual_access_checking
    def get(self):
        cont = self.request_continue_url()

        self._consume_auth_token()
        user_data = UserData.current(create_if_none=True)
        if not user_data:
            # Nobody is logged in - clear any expired Facebook cookies
            # that may be hanging around.
            facebook_util.delete_fb_cookies(self)

            logging.critical(("Missing UserData during PostLogin, " +
                              "with id: %s, cookies: (%s), google user: %s") %
                             (util.get_current_user_id_unsafe(),
                              os.environ.get('HTTP_COOKIE', ''),
                              users.get_current_user()))
            self._finish_and_redirect(cont)
            return

        first_time = not user_data.last_login

        if not user_data.has_sendable_email():

            if (not user_data.is_facebook_user and
                not user_data.is_child_account()):
                # TODO(benkomalo): seems like there are some phantoms hitting
                # this code path at least - are there any others?
                logging.error(
                    "Non-FB users should have a valid email. User: [%s]" %
                    user_data)

            # Facebook can give us the user's e-mail if the user granted
            # us permission to see it - try to update existing users with
            # emails, if we don't already have one for them.
            fb_email = facebook_util.get_fb_email_from_cookies()
            if fb_email:
                # We have to be careful - we haven't always asked for emails
                # from facebook users, so getting an e-mail after the fact
                # may result in a collision with an existing Google or Khan
                # account. In those cases, we silently drop the e-mail.
                existing_user = \
                    user_models.UserData.get_from_user_input_email(fb_email)

                if (existing_user and
                        existing_user.user_id != user_data.user_id):
                    logging.warning("FB user gave us e-mail and it "
                                    "corresponds to an existing account. "
                                    "Ignoring e-mail value.")
                else:
                    user_data.user_email = fb_email

        # If the user has a public profile, we stop "syncing" their username
        # from Facebook, as they now have an opportunity to set it themself
        if not user_data.username:
            user_data.update_nickname()

        # Set developer and moderator to True if user is admin
        if ((not user_data.developer or not user_data.moderator) and
                users.is_current_user_admin()):
            user_data.developer = True
            user_data.moderator = True

        # Track return visits -- check here for cross-computer tracking
        # Cast to str ensures any bad value will give ValueError, even None
        last_visit = str(self.get_cookie_value("return_visits_" +
                                        urllib.quote_plus(user_data.user_id)))
        try:
           # If cookie's invalid/not there count this as a return
           # visit and reset the cookie
           last_visit = float(last_visit)
        except ValueError:
            gae_bingo.gae_bingo.bingo([
                'return_visit_binary',  # Core metric
                'return_visit_count',  # Core metric
                'logged_in_return_visit_binary',  # Core metric
                'logged_in_return_visit_count',  # Core metric
            ])

            self.set_cookie(
                    "return_visits_" + urllib.quote_plus(user_data.user_id),
                    value=json.dumps(time.time()),  # Avoid scientific notation
                    max_age=str(60*60*24*365*2))  # Keep cookie for <= 2 years

        user_data.last_login = datetime.datetime.utcnow()
        user_data.put()


        complete_signup = self.request_bool("completesignup", default=False)

        if first_time:
            email_now_verified = None
            if user_data.has_sendable_email():
                email_now_verified = user_data.email

                # Look for a matching UnverifiedUser with the same e-mail
                # to see if the user used Google login to verify.
                unverified_user = user_models.UnverifiedUser.get_for_value(
                        email_now_verified)
                if unverified_user:
                    unverified_user.delete()

            # Note that we can only migrate phantom users right now if this
            # login is not going to lead to a "/completesignup" page, which
            # indicates the user has to finish more information in the
            # signup phase.
            if not complete_signup:
                # If user is brand new and has 0 points, migrate data.
                phantom_id = get_phantom_user_id_from_cookies()
                if phantom_id:
                    phantom_data = UserData.get_from_db_key_email(phantom_id)
                    if _upgrade_phantom_into(phantom_data, user_data):
                        cont = "/newaccount?continue=%s" % cont
        if complete_signup:
            cont = "/completesignup?continue=%s" % cont


        # testing going to profile page vs.
        # going to homepage on login from homepage
        if cont == "/":
            # For now, we just use the core metrics.
            # We may add more specific to this experiment later.
            if CoreMetrics.ab_test("redirect to profile",
                                  core_categories=["all"]):
                cont = user_data.profile_root

        # NOTE: this may be suboptimal, as a user can go to
        # /postlogin every 3 hours to have this be counted extraneously.
        # (Probably few if any will do that)
        # TODO(josh): figure out if this is worth fixing, and do it if so.

        # Get last login time and convert to seconds since epoch
        # http://stackoverflow.com/a/11111177
        epoch = datetime.datetime.utcfromtimestamp(0)
        last_login = (user_data.last_login - epoch).total_seconds()

        if last_login + (60 * 60 * 3) < time.time():
            gae_bingo.gae_bingo.bingo(['login_binary', # Core metric
                                       'login_count',  # Core metric
                                      ])

        self._finish_and_redirect(cont)

class Logout(request_handler.RequestHandler):
    @staticmethod
    def delete_all_identifying_cookies(handler):
        handler.delete_cookie('ureg_id')
        handler.delete_cookie(auth.cookies.AUTH_COOKIE_NAME)

        # Delete session cookie set by flask (used in /api/auth/token_to_session)
        handler.delete_cookie('session')

        # Delete Facebook cookie, which sets ithandler both on "www.ka.org" and ".www.ka.org"
        facebook_util.delete_fb_cookies(handler)

        # Delete all return visit cookies to mimize clutter
        for cookie in cookie_util.get_all_cookies():
            if cookie.startswith("return_visits_"):
                handler.delete_cookie(cookie)

    @user_util.open_access
    def get(self):
        google_user = users.get_current_user()
        Logout.delete_all_identifying_cookies(self)

        next_url = self.request_continue_url()
        if google_user is not None:
            next_url = users.create_logout_url(next_url)
        self.redirect(next_url)

# TODO(benkomalo): move this to a more appropriate, generic spot
# Loose regex for Email validation, copied from django.core.validators
# Most regex or validation libraries are overly strict - this is intentionally
# loose since the RFC is crazy and the only good way to know if an e-mail is
# really valid is to send and see if it fails.
_email_re = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"' # quoted-string
    r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$', re.IGNORECASE)  # domain

class Signup(request_handler.RequestHandler):
    """The handler for kicking off the process for signing up for an account.

    In some cases, if the user is signing up for a KA account with a personal
    email account, this will fire off an e-mail for verification of ownership
    of the e-mail. The rest of the data for the signup process is collected
    in a second step in the CompleteSignup handler.
    """

    @user_util.open_access
    def get(self):
        """Render the register for new user page."""

        parent_email = self.request_string("parent")
        if (self.request_bool('under13', default=False)
                or cookie_util.get_cookie_value(auth.cookies.U13_COOKIE_NAME)):
            if parent_email:
                # We have a non-empty "parent" string, which probably means
                # the user got here from ParentSignup.
                self.delete_cookie("u13")
            else:
                # User detected to be under13. Show them a page with
                # instructions to have their parent complete the process.
                u13_cookie = cookie_util.get_cookie_value('u13')
                parent_registered = u13_cookie == "notifiedparent"
                self.render_jinja2_template(
                    'under13.html', {
                        'parent_registered': parent_registered,
                    })
                return

        if parent_email:
            continue_url = "/createchild"
        else:
            continue_url = self.request_continue_url(default=None)

        continue_param = ""
        if continue_url:
            continue_param = "&continue=%s" % urllib.quote_plus(continue_url)
        template_values = {
            'errors': {},
            'values': {'email': parent_email} if parent_email else {},
            'continue_url': continue_url,
            'google_url': users.create_login_url(
                    "/postlogin?completesignup=1%s" % continue_param),
        }
        self.render_jinja2_template('signup.html', template_values)

    @user_util.manual_access_checking
    def post(self):
        """Handle registration request on our site.

        Note that new users can still be created via PostLogin if the user
        signs in via Google/FB for the first time - this is for the
        explicit registration via our own services.
        """

        values = {
            'birthdate': self.request_string('birthdate', default=None),
            'email': self.request_string('email', default=None),
        }

        errors = {}

        # Under-13 check (note the JavaScript on our form should never really
        # send an invalid date, but just to make sure...)
        birthdate = None
        if values['birthdate']:
            try:
                birthdate_dt = datetime.datetime.strptime(values['birthdate'],
                                                          '%Y-%m-%d')
                birthdate = birthdate_dt.date()
            except ValueError:
                errors['birthdate'] = "Invalid birthdate"
        else:
            errors['birthdate'] = "Birthdate required"

        if birthdate and age_util.get_age(birthdate) < 13:
            # We don't yet allow under13 users. We need to lock them out now,
            # unfortunately. Set an under-13 cookie so they can't try again.
            Logout.delete_all_identifying_cookies(self)
            auth.cookies.set_under13_cookie(self)

            self.render_json({"under13": True})
            return

        existing_google_user_detected = False
        resend_detected = False

        if values['email']:
            email = values['email']

            # Perform loose validation - we can't actually know if this is
            # valid until we send an e-mail.
            if not _email_re.search(email):
                errors['email'] = "That email appears to be invalid."
            else:
                existing = UserData.get_from_user_input_email(email)
                if existing is not None:
                    if existing.has_password():
                        # TODO(benkomalo): do something nicer and maybe ask the
                        # user to try and login with that e-mail?
                        errors['email'] = "Oops. There's already an account with that e-mail."
                    else:
                        existing_google_user_detected = True
                        logging.warn("User tried to register with password, "
                                     "but has an account w/ Google login")
                else:
                    # No full user account detected, but have they tried to
                    # signup before and still haven't verified their e-mail?
                    existing = user_models.UnverifiedUser.get_for_value(email)
                    resend_detected = existing is not None
        else:
            errors['email'] = "Please enter your email."

        if existing_google_user_detected:
            # TODO(benkomalo): just deny signing up with username/password for
            # existing users with a Google login. In the future, we can show
            # a message to ask them to sign in with their Google login
            errors['email'] = (
                    "There is already an account with that e-mail. " +
                    "If it's yours, sign in with Google below.")

        if len(errors) > 0:
            self.render_json({'errors': errors})
            return

        # TODO(benkomalo): make this /createchild for the case of a parent
        # signing up from a parent notification email in ParentSignup
        continue_url = self.request_continue_url(default=None)

        # Success!
        unverified_user = user_models.UnverifiedUser.get_or_insert_for_value(
                email,
                birthdate,
                continue_url)
        Signup.send_verification_email(unverified_user)

        response_json = {
                'success': True,
                'email': email,
                'resend_detected': resend_detected,
                }

        if App.is_dev_server:
            # Send down the verification token so the client can easily
            # create a link to test with.
            response_json['token'] = unverified_user.randstring

        # TODO(benkomalo): since users are now blocked from further access
        #    due to requiring verification of e-mail, we need to do something
        #    about migrating phantom data (we can store the phantom id in
        #    the UnverifiedUser object and migrate after they finish
        #    registering, for example)
        self.render_json(response_json, camel_cased=True)

    @staticmethod
    def send_verification_email(unverified_user):
        recipient = unverified_user.email
        verification_link = CompleteSignup.build_link(unverified_user)

        template_values = {
                'verification_link': verification_link,
            }

        body = shared_jinja.template_to_string(
                'verification-email-text-only.html',
                template_values)

        if not App.is_dev_server:
            mail.send_mail(
                    sender='Khan Academy Accounts <no-reply@khanacademy.org>',
                    to=recipient,
                    subject="Verify your email with Khan Academy",
                    body=body)

class ParentSignup(request_handler.RequestHandler):
    """A handler to accept parent email address.

    If a child attempts to signup for an account, we block them
    because they need a parent to complete the process. This handler collects
    info from the child about what their parent email address is, so we can
    contact the parent.
    """
    @user_util.open_access
    def post(self):
        email = self.request_string("parent-email")
        if not email:
            return self.error("Please tell us your parent or guardian's email")
        elif not _email_re.search(email):
            return self.error("That doesn't look like a valid email.")

        existing_user = UserData.get_from_user_input_email(email)

        if existing_user:
            if not existing_user.is_eligible_parent():
                return self.error("Sorry, but that user isn't old enough")
            template_values = {
                'name': existing_user.nickname,
                'create_child_link': url_util.absolute_url("/createchild"),
            }
        else:
            # Include a "parent" param with a random string to bust the u-13
            # cookie. This doesn't need to be secure - it only needs to be
            # non-obvious enough that under-13 users won't realize what is
            # going on and has an easy way to circumvent the system.
            template_values = {
                'create_account_link': url_util.absolute_url(
                    "/signup?parent=%s" % urllib.quote_plus(email))
            }

        body = shared_jinja.template_to_string(
            'parent-verification-email-text-only.html', template_values)

        if not App.is_dev_server:
            mail.send_mail(
                    sender='Khan Academy Accounts <no-reply@khanacademy.org>',
                    to=email,
                    subject="Help finish creating a child account",
                    body=body)
        else:
            logging.info("Skipping sending mail on dev server:\n%s\n" %
                         body)

        self.render_json({'success': True}, camel_cased=True)

    def error(self, message):
        self.render_json({
            'error': message
        }, camel_cased=True)

class CompleteSignup(request_handler.RequestHandler):
    """A handler for a page that allows users to create a password to login
    with a Khan Academy account. This is also being doubly used for existing
    Google/FB users to add a password to their account.
    """

    @staticmethod
    def build_link(unverified_user):
        """Build a link for an unverified user by using their unique
        randstring as a token embedded into the URL
        """

        return url_util.absolute_url(
                "/completesignup?token=%s" %
                unverified_user.randstring)

    def resolve_token(self):
        """Validate the token specified in the request parameters and returns
        a tuple of (token, UnverifiedUser) if it is a valid token.
        Returns (None, None) if no valid token was detected.
        """

        token = self.request_string("token", default=None)
        if not token:
            return (None, None)

        unverified_user = user_models.UnverifiedUser.get_for_token(token)
        if not unverified_user:
            return (None, None)

        # Success - token does indeed point to an unverified user.
        return (token, unverified_user)

    @user_util.manual_access_checking
    def get(self):
        if self.request_bool("form", default=False):
            return self.render_form()
        else:
            return self.render_outer()

    def render_outer(self):
        """Render the second part of the user signup step, after the user
        has verified ownership of their e-mail account.

        The request URI must include a valid token from an UnverifiedUser, and
        can be made via build_link(), or be made by a user without an existing
        password set.

        Note that the contents are actually rendered in an iframe so it
        can be sent over https (generated in render_form).
        """
        (valid_token, _) = self.resolve_token()
        user_data = UserData.current()
        if valid_token and user_data:
            if not user_data.is_phantom:
                logging.info("User tried to verify e-mail and complete a " +
                             "signup in a browser with an existing " +
                             "signed-in user. Forcefully signing old user " +
                             "out to avoid conflicts")
                self.redirect(url_util.create_logout_url(self.request.uri))
                return

            # Ignore phantom users.
            user_data = None

        if not valid_token and not user_data:
            # Just take them to the homepage for now.
            self.redirect("/")
            return

        transfer_token = None
        if user_data:
            if user_data.has_password():
                # The user already has a KA login - redirect them to their profile
                self.redirect(user_data.profile_root)
                return
            elif not user_data.has_sendable_email():
                # This is a case where a Facebook user logged in and tried
                # to signup for a KA password. Unfortunately, since we don't
                # have their e-mail, we can't let them proceed, since, without
                # a valid e-mail we can't reset passwords, etc.
                logging.error("User tried to signup for password with "
                              "no email associated with the account")
                self.redirect("/")
                return
            else:
                # Here we have a valid user, and need to transfer their identity
                # to the inner iframe that will be hosted on https.
                # Since their current cookies may not be transferred/valid in
                # https, mint a custom, short-lived token to transfer identity.
                transfer_token = TransferAuthToken.for_user(user_data).value

        template_values = {
            'params': url_util.build_params({
                'token': valid_token,
                'transfer_token': transfer_token,
            }),
            'continue': self.request_continue_url(),
        }

        self.render_jinja2_template('completesignup.html', template_values)

    def render_form(self):
        """Render the contents of the form for completing a signup."""

        valid_token, unverified_user = self.resolve_token()
        user_data = _resolve_user_in_https_frame(self)
        if not valid_token and not user_data:
            # TODO(benkomalo): handle this better since it's going to be in
            # an iframe! The outer container should do this check for us though.

            # Just take them to the homepage for now.
            self.redirect("/")
            return

        if not valid_token and user_data:
            if user_data.has_password():
                # The user already has a KA login - redirect them to
                # their profile
                self.redirect(user_data.profile_root)
                return
            elif not user_data.has_sendable_email():
                self.redirect("/")
                return

        values = {}
        if valid_token:
            # Give priority to the token in the URL.
            values['email'] = unverified_user.email
            user_data = None
        else:
            # Must be that the user is signing in with Google/FB and wanting
            # to create a KA password to associate with it

            # TODO(benkomalo): handle storage for FB users. Right now their
            # "email" value is a URI like http://facebookid.ka.org/1234
            email = user_data.email
            nickname = user_data.nickname
            if user_data.has_sendable_email():
                values['email'] = email

                if email.split('@')[0] == nickname:
                    # The user's "nickname" property defaults to the user part
                    # of their e-mail. Encourage them to use a real name and
                    # leave the name field blank in that case.
                    nickname = ""

            values['nickname'] = nickname
            values['gender'] = user_data.gender
            values['username'] = user_data.username

        template_values = {
            'user': user_data,
            'values': values,
            'token': valid_token,
        }
        self.render_jinja2_template('completesignup_contents.html', template_values)

    @user_util.manual_access_checking
    def post(self):
        valid_token, unverified_user = self.resolve_token()
        user_data = _resolve_user_in_https_frame(self)
        if not valid_token and not user_data:
            logging.warn("No valid token or user for /completesignup")
            self.redirect("/")
            return

        if valid_token:
            if user_data:
                logging.warn("Existing user is signed in, but also specified "
                             "a valid UnverifiedUser's token. Ignoring "
                             " existing sign-in and using token")
            user_data = None

        # Store values in a dict so we can iterate for monotonous checks.
        values = {
            'nickname': self.request_string('nickname', default=None),
            'gender': self.request_string('gender', default="unspecified"),
            'username': self.request_string('username', default=None),
            'password': self.request_string('password', default=None),
        }

        # Simple existence validations
        errors = {}
        for field, error in [('nickname', "Please tell us your name."),
                             ('username', "Please pick a username."),
                             ('password', "We need a password from you.")]:
            if not values[field]:
                errors[field] = error

        gender = None
        if values['gender']:
            gender = values['gender'].lower()
            if gender not in ['male', 'female']:
                gender = None

        if values['username']:
            username = values['username']
            # TODO(benkomalo): ask for advice on text
            if user_models.UniqueUsername.is_username_too_short(username):
                errors['username'] = "Sorry, that username's too short."
            elif not user_models.UniqueUsername.is_valid_username(username):
                errors['username'] = "Usernames must start with a letter and be alphanumeric."

            # Only check to see if it's available if we're changing values
            # or if this is a brand new UserData
            elif ((not user_data or user_data.username != username) and
                    not user_models.UniqueUsername.is_available_username(username)):
                errors['username'] = "That username isn't available."

        if values['password']:
            password = values['password']
            if not auth.passwords.is_sufficient_password(password,
                                                         values['nickname'],
                                                         values['username']):
                errors['password'] = "Sorry, but that password's too weak."


        if len(errors) > 0:
            self.render_json({'errors': errors}, camel_cased=True)
            return

        continue_url = ((unverified_user and unverified_user.continue_url) or
                        self.request_continue_url(default=None))
        if user_data:
            # Existing user - update their info
            def txn():
                if (username != user_data.username
                        and not user_data.claim_username(username)):
                    errors['username'] = "That username isn't available."
                    return False

                user_data.set_password(password)
                user_data.update_nickname(values['nickname'])

            transaction_util.ensure_in_transaction(txn, xg_on=True)
            if len(errors) > 0:
                self.render_json({'errors': errors}, camel_cased=True)
                return

        else:
            # Converting unverified_user to a full UserData.
            num_tries = 0
            user_data = None
            while not user_data and num_tries < 2:
                # Double-check to ensure we don't create any duplicate ids!
                user_id = uid.new_user_id()
                user_data = user_models.UserData.insert_for(
                        user_id,
                        unverified_user.email,
                        username,
                        password,
                        birthdate=unverified_user.birthdate,
                        gender=gender)

                if not user_data:
                    self.render_json({'errors': {'username': "That username isn't available."}},
                                     camel_cased=True)
                    return
                elif user_data.username != username:
                    # Something went awry - insert_for may have returned
                    # an existing user due to an ID collision. Try again.
                    user_data = None
                num_tries += 1

            if not user_data:
                logging.error("Tried several times to create a new user " +
                              "unsuccessfully")
                self.render_json({
                        'errors': {'username': "Oops! Something went wrong. " +
                                               "Please try again later."}
                }, camel_cased=True)
                return

            # Nickname is special since it requires updating external indices.
            user_data.update_nickname(values['nickname'])

            # TODO(benkomalo): move this into a transaction with the above creation
            unverified_user.delete()
            
        # TODO(benkomalo): give some kind of "congrats"/"welcome" notification
        Login.return_login_json(self,
                                user_data,
                                cont=continue_url or user_data.profile_root)


class PasswordChangeInfo(object):
    """Info about a password change request."""
    def __init__(self, actor, target, is_password_reset=False):
        # The authenticated user who is performing the password change
        self.actor = actor
            
        # The user whose password is being changed (can be same as actor,
        # or a child account the actor manages)
        self.target = target

        if is_password_reset and actor != target:
            raise Exception("Can only do password resets for self")

        # Whether or not this is a password reset.
        self.is_password_reset = is_password_reset

    @property
    def requires_prev_password(self):
        return (self.actor == self.target and
                not self.is_password_reset)


class PasswordChange(request_handler.RequestHandler):
    """Handler for changing a user's password.

    Note there are three types of password changes:
    - a regular password change for a logged in user,
    - a password reset using a "reset_token" (no need to enter prev password)
    - a password change from a parent account for a child account
        (no need to enter prev password)

    This must always be rendered in an https form. If a request is made to
    render the form in HTTP, this handler will automatically redirect to
    the HTTPS version with a transfer_token to identify the user in HTTPS.
    """

    def _get_request_info(self):
        """Return the information for the user and current request.

        This resolves auth information, taking into account the transfer
        token and also determines what type of a password change this is.

        Returns:
            A ChangeContext object for this password change. If insufficient
            privileges or bad authentication credentials are supplied, or if
            this is an invalid request of any kind, returns None.
        """

        actor = _resolve_user_in_https_frame(self)

        if actor and actor.is_child_account():
            # Child accounts can't change password. No big deal - just
            # don't let them. Not worth logging, though.
            return None

        if not actor:
            # Try to resolve the user from a reset token, if nobody is
            # logged in.
            reset_token_value = self.request_string("reset_token", default="")
            reset_token = PasswordResetToken.for_value(reset_token_value)
            if not reset_token:
                return None

            actor = user_models.UserData.get_from_user_id(reset_token.user_id)
            if not reset_token.is_valid(actor):
                logging.warning("Password change attempted with invalid "
                                "reset token for user [%s]" % actor)
                return None

            return PasswordChangeInfo(actor=actor,
                                      target=actor,
                                      is_password_reset=True)

        # Assert - someone is logged in as a valid actor of a pw change.
        # See if they're trying to change someone else's password.
        target = self.request_student_user_data() or actor
        if target.key() != actor.key():
            if not user_models.ParentChildPair.is_pair(actor, target):
                logging.warning("User tried to change password for someone "
                                "that is not a child account.")
                return None
        return PasswordChangeInfo(actor=actor, target=target)

    @user_util.manual_access_checking
    def get(self):
        # Always render on https.
        if self.request.scheme != "https" and not App.is_dev_server:
            self.redirect(self.secure_url_with_token(self.request.uri))
            return

        if self.request_bool("success", default=False):
            self.render_form(message="Password changed", success=True)
        else:
            self.render_form()

    def render_form(self, message=None, success=False, request_info=None):
        transfer_token_value = self.request_string("transfer_token", default="")
        reset_token_value = self.request_string("reset_token", default="")
        if not request_info:
            request_info = self._get_request_info()

        self.render_jinja2_template('password-change.html',
                                    {'message': message or "",
                                     'success': success,
                                     'request_info': request_info,
                                     'transfer_token': transfer_token_value,
                                     'reset_token': reset_token_value})

    def secure_url_with_token(self, url, request_info=None):
        if request_info is None:
            request_info = self._get_request_info()
        if not request_info:
            # Bad or invalid request. What to do? Forward them anyways with
            # no transfer_token.
            return url_util.secure_url(url)

        token = TransferAuthToken.for_user(request_info.actor).value
        if url.find('?') == -1:
            return "%s?transfer_token=%s" % (url_util.secure_url(url),
                                             urllib.quote_plus(token))
        else:
            return "%s&transfer_token=%s" % (url_util.secure_url(url),
                                             urllib.quote_plus(token))


    @user_util.manual_access_checking
    def post(self):
        request_info = self._get_request_info()
        if not request_info:
            self.response.write("Oops. Something went wrong. Please try again.")
            return
        
        if request_info.requires_prev_password:
            existing = self.request_string("existing")
            if not request_info.actor.validate_password(existing):
                # TODO(benkomalo): throttle incorrect password attempts
                self.render_form(message="Incorrect password",
                                 request_info=request_info)
                return

        target = request_info.target
        password1 = self.request_string("password1")
        password2 = self.request_string("password2")
        if (not password1 or
                not password2 or
                password1 != password2):
            self.render_form(message="Passwords don't match",
                             request_info=request_info)
        elif not auth.passwords.is_sufficient_password(password1,
                                                       target.nickname,
                                                       target.username):
            self.render_form(message="Password too weak",
                             request_info=request_info)
        else:
            # We're good!
            target.set_password(password1)
            if request_info.is_password_reset:
                # Password resets are done when the user is not even logged in,
                # so redirect the host page to the login page (done via
                # client side JS)
                self.render_form(message="Password reset. Redirecting...",
                                 success=True,
                                 request_info=request_info)
            elif request_info.actor != request_info.target:
                # Changing a password for a child account. No need to do
                # fancy redirects here.
                self.render_form(message="Password changed.",
                                 success=True,
                                 request_info=request_info)
            else:
                # Need to create a new auth token as the existing cookie will
                # expire. Use /postlogin to set the cookie. This requires
                # some redirects (/postlogin on http, then back to this
                # pwchange form in https).
                auth_token = AuthToken.for_user(request_info.actor)
                self.redirect("%s?%s" % (
                    url_util.insecure_url("/postlogin"),
                    url_util.build_params({
                        'auth': auth_token.value,
                        'continue': self.secure_url_with_token(
                            "/pwchange?success=1", request_info),
                    })))

class ForgotPassword(request_handler.RequestHandler):
    """Handler for initiating the password reset flow."""

    @user_util.open_access
    def get(self):
        user_data = user_models.UserData.current()
        if user_data and not user_data.is_phantom:
            # User is already logged in! Shouldn't want to reset passwords.
            self.redirect(user_data.profile_root)
            return

        self.render_jinja2_template('forgot-password.html', {})

    @user_util.open_access
    def post(self):
        email = self.request_string("email", default=None)
        if not email:
            self.render_jinja2_template('forgot-password.html', {})
            return

        user_data = user_models.UserData.get_from_user_input_email(email)
        if not user_data or not user_data.has_password():
            # TODO(benkomalo): separate out the case where we detected a user
            # but he/she doesn't have a password set?
            self.render_jinja2_template(
                'forgot-password-error.html', {
                    'email': email,
                    'google_url': users.create_login_url('/completesignup'),
                })
            return

        reset_url = PasswordReset.build_link(user_data)
        template_values = {
            'name': user_data.nickname,
            'url': reset_url,
        }
        body = shared_jinja.template_to_string(
                'password-reset-email-text-only.html',
                template_values)

        if not App.is_dev_server:
            mail.send_mail(
                    sender="Khan Academy Accounts <no-reply@khanacademy.org>",
                    to=email,
                    subject="Khan Academy account recovery",
                    body=body)

        template_values =  {
            'sent_email': email,
        }
        if App.is_dev_server:
            template_values['debug_link'] = reset_url
        self.render_jinja2_template('forgot-password.html', template_values)


class PasswordReset(request_handler.RequestHandler):
    """Handler for the password reset flow.

    This is after the user has received an e-mail with a recovery link
    and handles the request for when they click on that link in the e-mail.
    """

    @user_util.manual_access_checking
    def get(self):
        reset_token_value = self.request_string("token", default="")
        
        user_data = PasswordResetToken.get_user_for_value(
            reset_token_value, UserData.get_from_user_id)
        if not user_data:
            self.redirect("/")
            return

        self.render_jinja2_template(
            'password-reset.html', {
                'reset_token': reset_token_value,
            })

    @staticmethod
    def build_link(user_data):
        pw_reset_token = PasswordResetToken.for_user(user_data)
        if not pw_reset_token:
            raise Exception("Unable to build password reset link for user")
        return url_util.absolute_url("/pwreset?token=%s" %
                                     urllib.quote_plus(pw_reset_token.value))


class CreateChild(request_handler.RequestHandler):
    """A handler for creating a new child account.

    Must be done by a logged-in user that is not a child account.
    Since this involves password submission, the main contents are done
    inside of an HTTPS iframe, just like the other login/signup related
    handlers.
    """

    @user_util.manual_access_checking
    def get(self):
        if self.request_bool("form", default=False):
            self.render_form()
        else:
            self.render_outer()
            
    def _is_eligible_for_child_creation(self, user_data):
        return user_data and user_data.is_eligible_parent()
    
    @user_util.manual_access_checking
    def render_outer(self):
        user_data = UserData.current()
        if not user_data:
            # Show a message to the user that they need to login.
            self.render_jinja2_template(
                'create-child.html', {
                    'show_login_warning': True
                })
            return
            
        if not self._is_eligible_for_child_creation(user_data):
            # TODO(benkomalo): we should probably put up a notification
            # explaining that the user is inelgible, since this may be
            # immediately after a laborious child signup process, and it may
            # be confusing why it just dropped them in the homepage.
            self.redirect("/")
            return

        self.render_jinja2_template(
            'create-child.html', {
                'secure_url': self.build_form_url(user_data),
            })
        
    def render_form(self, values={}):
        user_data = _resolve_user_in_https_frame(self)
        if not self._is_eligible_for_child_creation(user_data):
            self.redirect("/")
            return

        self.render_jinja2_template(
            'create-child-contents.html', {
                'transfer_token': self.request_string('transfer_token'),
                'values': values,
            })

    def build_form_url(self, user_data):
        base_url = url_util.secure_url(self.request.path)
        token = TransferAuthToken.for_user(user_data).value
        if base_url.find('?') == -1:
            return "%s?form=1&transfer_token=%s" % (
                url_util.secure_url(base_url),
                urllib.quote_plus(token))
        else:
            return "%s&form=1&transfer_token=%s" % (
                url_util.secure_url(base_url),
                urllib.quote_plus(token))

    @user_util.manual_access_checking
    def post(self):
        user_data = _resolve_user_in_https_frame(self)
        if not user_data:
            return
        
        # Store values in a dict so we can iterate for monotonous checks.
        values = {
            'birthdate': self.request_string('birthdate', default=None),
            'gender': self.request_string('gender', default="unspecified"),
            'username': self.request_string('username', default=None),
            'password': self.request_string('password', default=None),
        }

        # Simple existence validations
        errors = {}
        for field, error in [
                ('birthdate', "Please tell us your child's birthday."),
                ('username', "Please pick a username."),
                ('password', "We need a password from you.")
                ]:
            if not values[field]:
                errors[field] = error

        # Bail early if there are any missing fields.
        if len(errors) > 0:
            self.render_json({'errors': errors}, camel_cased=True)
            return

        # TODO(benkomalo): deal with this date parsing duplication with
        #   CompleteSignup
        try:
            birthdate_dt = datetime.datetime.strptime(values['birthdate'],
                                                      '%Y-%m-%d')
            birthdate = birthdate_dt.date()
        except ValueError:
            errors['birthdate'] = "Invalid birthdate"
            self.render_json({'errors': errors}, camel_cased=True)
            return

        if age_util.get_age(birthdate) >= 13:
            errors['birthdate'] = \
                    "You can't create child accounts over 13 years old."
            self.render_json({'errors': errors}, camel_cased=True)
            return

        gender = values['gender'].lower()
        if gender not in ['male', 'female']:
            gender = None

        username = values['username']
        if user_models.UniqueUsername.is_username_too_short(username):
            errors['username'] = "Sorry, that username's too short."
        elif not user_models.UniqueUsername.is_valid_username(username):
            errors['username'] = \
                "Usernames must start with a letter and be alphanumeric."
        elif not user_models.UniqueUsername.is_available_username(username):
            errors['username'] = "That username isn't available."

        password = values['password']
        if not auth.passwords.is_sufficient_password(password,
                                                     '',  # Nickname
                                                     values['username']):
            errors['password'] = "Sorry, but that password's too weak."

        # Bail if there are any invalid fields.
        if len(errors) > 0:
            self.render_json({'errors': errors}, camel_cased=True)
            return
        
        # Fields look good - give it a shot!
        child_user_data = user_data.spawn_child(username=username,
                                                birthdate=birthdate,
                                                password=password)

        if not child_user_data:
            # Shouldn't happen since we checked everything above, but
            # just in case...
            logging.error("Did not succeed creating a child account with " +
                          "username [%s] and birthdate [%s]" % (username, 
                                                                birthdate))
            self.render_json({
                'errors': {
                    'unknown': "Oops. Something went wrong. "
                                "Please try again later."
                }
            }, camel_cased=True)
            return
        else:
            allow_coaches = self.request_bool("allow-coaches", default=False)
            child_user_data.set_can_modify_coaches(allow=allow_coaches)

        # Success!
        self.render_json({'success': True}, camel_cased=True)


def _resolve_user_in_https_frame(handler):
    """Determine the current logged in user for the HTTPS request.

    This has logic in additional to UserData.current(), since it should also
    accept TransferAuthTokens, since HTTPS requests may not have normal HTTP
    cookies sent.
    """

    user_data = UserData.current()
    if user_data:
        return user_data

    if not App.is_dev_server and not handler.request.uri.startswith('https'):
        return None

    # On https, users aren't recognized through the normal means of cookie auth
    # since their cookies were set on HTTP domains.
    token_value = handler.request_string("transfer_token", default=None)
    return TransferAuthToken.get_user_for_value(
        token_value, UserData.get_from_user_id)
