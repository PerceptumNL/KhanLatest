import datetime
import os
import logging
import re
import sys
import time
import traceback

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError

from api.jsonify import jsonify
from app import App
import gae_bingo.identity
import cookie_util
from custom_exceptions import MissingVideoException, MissingExerciseException, SmartHistoryLoadException, PageNotFoundException, QuietException, ClosedBetaException
import shared_jinja
import user_util
import webapp2
import badges.util_badges
import goals.models
from profiles import util_profile
import url_util
import user_models
from gandalf.bridge import gandalf


class RequestInputHandler(object):

    def request_string(self, key, default=''):
        return self.request.get(key, default_value=default)

    def request_continue_url(self, key="continue", default="/"):
        """ Gets the request string representing a continue URL for the current
        request.

        This will safely filter out continue URL's that are not-served by
        us so that users can't be tricked into going to a malicious site post
        login or some other flow that goes through KA.
        """
        val = self.request_string(key, default)
        if (val and not App.is_dev_server and
            not url_util.is_khanacademy_url(val)):
            logging.warn("Invalid continue URI [%s]. Ignoring." % val)
            if val != default and url_util.is_khanacademy_url(default):
                # Make a last ditch effort to try the default, in case the
                # explicit continue URI was the bad one
                return default
            return "/"

        return val

    def request_int(self, key, default = None):
        try:
            return int(self.request_string(key))
        except ValueError:
            if default is not None:
                return default
            else:
                raise # No value available and no default supplied, raise error

    def request_date(self, key, format_string, default = None):
        try:
            return datetime.datetime.strptime(self.request_string(key), format_string)
        except ValueError:
            if default is not None:
                return default
            else:
                raise # No value available and no default supplied, raise error

    def request_date_iso(self, key, default = None):
        s_date = self.request_string(key)

        # Pull out milliseconds b/c Python 2.5 doesn't play nicely w/ milliseconds in date format strings
        if "." in s_date:
            s_date = s_date[:s_date.find(".")]

        # Try to parse date in our approved ISO 8601 format
        try:
            return datetime.datetime.strptime(s_date, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            if default is not None:
                return default
            else:
                raise # No value available and no default supplied, raise error

    # TODO(benkomalo): kill this, or make it private and
    # consolidate it with the other request user data methods by
    # various email keys
    def request_user_data(self, key):
        """Gets the user for the request, specified by an email value.

        Arguments:
            key: The name of the request param to read the user email from.
        """
        email = self.request_string(key)
        current = user_models.UserData.current()
        if current and current.email == email:
            return current
        return user_models.UserData.get_from_user_input_email(email)

    def request_visible_student_user_data(self):
        """Return the UserData for the given request.

        This looks for an identifying parameter
        (see request_student_user_data) and attempts to return that user
        if the current actor for the request has access to view that
        user's information (will return None if the actor does not
        have sufficient permissions)

        If no identifying parameter is specified, returns the current user.
        """
        override_user_data = self.request_student_user_data()
        if not override_user_data:
            # TODO(benkomalo): maybe this shouldn't fallback to current user?
            # It seems like a weird API to accept an explicit user identifier
            # but then fallback to the current user if that identifier doesn't
            # resolve. It should give an error instead.
            return user_models.UserData.current()
        return user_models.UserData.get_visible_user(override_user_data)

    def request_student_user_data(self):
        """Return the specified UserData for the given request.

        This looks for an identifying parameter, looking first for userId,
        then username, then email, from the request parameters and returns
        the user that matches, if any.
        """
        current = user_models.UserData.current()
        user_id = self.request_string("userId")
        if user_id:
            if current and current.user_id == user_id:
                return current
            return user_models.UserData.get_from_user_id(user_id)

        username = self.request_string("username")
        if username:
            if current and user_models.UniqueUsername.matches(
                    current.username, username):
                return current
            return user_models.UserData.get_from_username(username)

        email = self._request_student_email()
        if email:
            if current and current.email == email:
                return current
            return user_models.UserData.get_from_user_input_email(email)

        key = self.request_string("userKey")
        if key:
            return db.get(key)

        # Last resort - the client specified an un-typed identifier.
        identifier = self.request_string("identifier")
        if identifier:
            return user_util.get_possibly_current_user(identifier)
        return None

    def _request_student_email(self):
        """Retrieve email parameter from the request.

        This abstracts away some history behind the name changes for the email
        parameter and is robust to handling "student_email" and "email"
        parameter names.
        """
        email = self.request_string("student_email")
        if email:
            logging.warning("API called with legacy student_email parameter")
        email = self.request_string("email", email)
        return email

    def request_float(self, key, default = None):
        try:
            return float(self.request_string(key))
        except ValueError:
            if default is not None:
                return default
            else:
                raise # No value available and no default supplied, raise error

    def request_bool(self, key, default = None):
        if default is None:
            return self.request_int(key) == 1
        else:
            return self.request_int(key, 1 if default else 0) == 1

class RequestHandler(webapp2.RequestHandler, RequestInputHandler):

    class __metaclass__(type):
        """Enforce that subclasses of RequestHandler decorate get()/post()/etc.
        This metaclass enforces that whenever we create a
        RequestHandler or subclass thereof, that the class we're
        creating has a decorator on its get(), post(), and other
        http-verb methods that specify the access needed to get or
        post (admin, moderator, etc).

        It does this through a two-step process.  In step 1, we make
        all the access-control decorators set a function-global
        variable in the method they're decorating.  (This is done in
        the decorator definitions in user_util.py.)  In step 2, here,
        we check that that variable is defined.  We can do this
        because metaclass, when creating a new class, has access to
        the functions (methods) that the class implements.

        Note that this check happens at import-time, so we don't have
        to worry about this assertion triggering surprisingly in
        production.
        """
        def __new__(mcls, name, bases, attrs):
            for fn in ("get", "post", "head", "put"):
                if fn in attrs:
                    # TODO(csilvers): remove the requirement that the
                    # access control decorator go first.  To do that,
                    # we'll have to store state somewhere other than
                    # in func_dict (which later decorators overwrite).
                    assert '_access_control' in attrs[fn].func_dict, \
                           ('FATAL ERROR: '
                            'Need to put an access control decorator '
                            '(from user_util) on %s.%s. '
                            '(It must be the topmost decorator for the method.)'
                            % (name, fn))
            return type.__new__(mcls, name, bases, attrs)

    def is_ajax_request(self):
        # jQuery sets X-Requested-With header for this detection.
        if self.request.headers.has_key("x-requested-with"):
            s_requested_with = self.request.headers["x-requested-with"]
            if s_requested_with and s_requested_with.lower() == "xmlhttprequest":
                return True
        return self.request_bool("is_ajax_override", default=False)

    def request_url_with_additional_query_params(self, params):
        url = self.request.url
        if url.find("?") > -1:
            url += "&"
        else:
            url += "?"
        return url + params

    def handle_exception(self, e, *args):

        title = "Oeps. We hebben een fout gemaakt."
        message_html = "Er is een probleem, onze schuld, er wordt aan gewerkt."
        sub_message_html = "Dit probleem is al aan ons gerapporteerd, en we proberen het te repareren. Als het probleem zich voor blijft doen, neem gerust contact met ons op.<a href='/reportissue?type=Defect'></a>."

        if type(e) is CapabilityDisabledError:

            # App Engine maintenance period
            title = "Ssst. Wij zijn aan het studeren."
            message_html = "We zijn even offline, dit probleem wordt zo spoedig mogelijk verholpen. In de tussentijd kun je alle video's bekijken op ons Youtube-kanaal <a href='http://www.youtube.com/user/khanacademy'>Khan Academy YouTube channel</a>."
            sub_message_html = "Het spijt ons zeer, er wordt aan een oplossing gewerkt."

        elif type(e) is MissingExerciseException:

            title = "Deze oefening is nu niet beschikbaar."
            message_html = "Deze oefening bestaat niet (meer) of is tijdelijk offline. Ga terug naar  <a href='/exercisedashboard'> om andere oefeningen te maken</a>."
            sub_message_html = "Als dit probleem zich voor blijft doen, neem gerust contact met ons op <a href='/reportissue?type=Defect'></a>."

        elif type(e) is MissingVideoException:

            # We don't log missing videos as errors because they're so common due to malformed URLs or renamed videos.
            # Ask users to report any significant problems, and log as info in case we need to research.
            title = "Deze video is niet langer beschikbaar."
            message_html = "Deze video is niet langer beschikbaar, of is door de eigenaar offline gehaald. <a href='/'>Zoek in onze bibliotheek</a> om hem te vinden."
            sub_message_html = "Als dit probleem zich voor blijft doen, neem gerust contact met ons op <a href='/reportissue?type=Defect'></a>."

        elif type(e) is SmartHistoryLoadException:
            # 404s are very common with Smarthistory as bots have gotten hold of bad urls, silencing these reports and log as info instead
            title = "Deze pagina bestaat niet."
            message_html = "Ga naar <a href='/'>our Smarthistory homepage</a> om hier meer over te lezen."
            sub_message_html = "Als dit probleem zich voor blijft doen, neem gerust contact met ons op <a href='/reportissue?type=Defect'></a>."

        elif type(e) is PageNotFoundException:

            title = "Sorry, hetgene waarnaar je zoekt kunnen we niet vinden."
            message_html = "Deze pagina lijkt niet te bestaan. <a href='/'>Ga naar de homepage</a>."
            sub_message_html = "Als dit probleem zich voor blijft doen,e <a href='/reportissue?type=Defect'>neem dan contact met ons op</a>."

        elif type(e) is ClosedBetaException:

            title = "Shhh. It's a secret."
            message_html = ("This feature is in closed beta at the moment. "
                "We laten weten wanneer dit verholpen is.")
            sub_message_html = ("Je kunt je inschrijven om updates te ontvangen "
                "<a href='/about/blog'>Khan Academy Blog</a> "
                "or by following us on twitter "
                "<a href='https://twitter.com/KhanAcademie'>@KhanAcademie</a>.")

        if isinstance(e, QuietException):
            logging.info(e)
        else:
            self.error(500)
            logging.exception(e)

        # Show a nice stack trace on development machines, but not in production
        if App.is_dev_server or users.is_current_user_admin():
            try:
                import google

                exc_type, exc_value, exc_traceback = sys.exc_info()

                # Grab module and convert "__main__" to just "main"
                class_name = '%s.%s' % (re.sub(r'^__|__$', '', self.__class__.__module__), type(self).__name__)

                http_method = self.request.method
                title = '%s in %s.%s' % ((exc_value.exc_info[0] if hasattr(exc_value, 'exc_info') else exc_type).__name__, class_name, http_method.lower())

                message = str(exc_value.exc_info[1]) if hasattr(exc_value, 'exc_info') else str(exc_value)

                sdk_root = os.path.normpath(os.path.join(os.path.dirname(google.__file__), '..'))
                sdk_version = os.environ['SDK_VERSION'] if os.environ.has_key('SDK_VERSION') else os.environ['SERVER_SOFTWARE'].split('/')[-1]
                app_root = App.root
                r_sdk_root = re.compile(r'^%s/' % re.escape(sdk_root))
                r_app_root = re.compile(r'^%s/' % re.escape(app_root))

                (template_filename, template_line, extracted_source) = (None, None, None)
                if hasattr(exc_value, 'source'):
                    origin, (start, end) = exc_value.source
                    template_filename = str(origin)

                    f = open(template_filename)
                    template_contents = f.read()
                    f.close()

                    template_lines = template_contents.split('\n')
                    template_line = 1 + template_contents[:start].count('\n')
                    template_end_line = 1 + template_contents[:end].count('\n')

                    ctx_start = max(1, template_line - 3)
                    ctx_end = min(len(template_lines), template_end_line + 3)

                    extracted_source = '\n'.join('%s: %s' % (num, template_lines[num - 1]) for num in range(ctx_start, ctx_end + 1))

                def format_frame(frame):
                    filename, line, function, text = frame
                    filename = r_sdk_root.sub('google_appengine (%s) ' % sdk_version, filename)
                    filename = r_app_root.sub('', filename)
                    return "%s:%s:in `%s'" % (filename, line, function)

                extracted = traceback.extract_tb(exc_traceback)
                if hasattr(exc_value, 'exc_info'):
                    extracted += traceback.extract_tb(exc_value.exc_info[2])

                application_frames = reversed([frame for frame in extracted if r_app_root.match(frame[0])])
                framework_frames = reversed([frame for frame in extracted if not r_app_root.match(frame[0])])
                full_frames = reversed([frame for frame in extracted])

                application_trace = '\n'.join(format_frame(frame) for frame in application_frames)
                framework_trace = '\n'.join(format_frame(frame) for frame in framework_frames)
                full_trace = '\n'.join(format_frame(frame) for frame in full_frames)

                param_keys = self.request.arguments()
                params = ',\n    '.join('%s: %s' % (repr(k.encode('utf8')), repr(self.request.get(k).encode('utf8'))) for k in param_keys)
                params_dump = '{\n    %s\n}' % params if len(param_keys) else '{}'

                environ = self.request.environ
                env_dump = '\n'.join('%s: %s' % (k, environ[k]) for k in sorted(environ))

                self.response.clear()
                self.render_jinja2_template('viewtraceback.html', { "title": title, "message": message, "template_filename": template_filename, "template_line": template_line, "extracted_source": extracted_source, "app_root": app_root, "application_trace": application_trace, "framework_trace": framework_trace, "full_trace": full_trace, "params_dump": params_dump, "env_dump": env_dump })
            except:
                # We messed something up showing the backtrace nicely; just show it normally
                pass
        else:
            self.response.clear()
            self.render_jinja2_template('viewerror.html', { "title": title, "message_html": message_html, "sub_message_html": sub_message_html })

    @classmethod
    def exceptions_to_http(klass, status):
        def decorator(fn):
            def wrapper(self, *args, **kwargs):
                try:
                    fn(self, *args, **kwargs);
                except Exception, e:
                    self.response.clear()
                    self.response.set_status(status)
            return wrapper
        return decorator

    def user_agent(self):
        return str(self.request.headers.get('User-Agent', ""))

    def is_mobile_capable(self):
        user_agent_lower = self.user_agent().lower()
        return False #turn mobile off

#        return user_agent_lower.find("ipod") > -1 or \
#                user_agent_lower.find("ipad") > -1 or \
#                user_agent_lower.find("iphone") > -1 or \
#                user_agent_lower.find("webos") > -1 or \
#                user_agent_lower.find("android") > -1

    def is_older_ie(self):
        user_agent_lower = self.user_agent().lower()
        return user_agent_lower.find("msie 7.") > -1 or \
                user_agent_lower.find("msie 6.") > -1

    def is_webos(self):
        user_agent_lower = self.user_agent().lower()
        return user_agent_lower.find("webos") > -1 or \
                user_agent_lower.find("hp-tablet") > -1

    def is_ipad(self):
        user_agent_lower = self.user_agent().lower()
        return user_agent_lower.find("ipad") > -1

    def is_mobile(self):
        if self.is_mobile_capable():
            return not self.has_mobile_full_site_cookie()
        return False

    def has_mobile_full_site_cookie(self):
        return self.get_cookie_value("mobile_full_site") == "1"

    def set_mobile_full_site_cookie(self, is_mobile):
        self.set_cookie("mobile_full_site", "1" if is_mobile else "0")

    @staticmethod
    def get_cookie_value(key):
        return cookie_util.get_cookie_value(key)

    # Cookie handling from http://appengine-cookbook.appspot.com/recipe/a-simple-cookie-class/
    def set_cookie(self, key, value='', max_age=None,
                   path='/', domain=None, secure=None, httponly=False,
                   version=None, comment=None):

        # We manually add the header here so we can support httponly cookies in Python 2.5,
        # which self.response.set_cookie does not.
        header_value = cookie_util.set_cookie_value(key, value, max_age, path, domain, secure, httponly, version, comment)
        self.response.headerlist.append(('Set-Cookie', header_value))

    def delete_cookie_including_dot_domain(self, key, path='/', domain=None):

        self.delete_cookie(key, path, domain)

        if domain is None:
            domain = os.environ["SERVER_NAME"]

        self.delete_cookie(key, path, "." + domain)

    def delete_cookie(self, key, path='/', domain=None):
        self.set_cookie(key, '', path=path, domain=domain, max_age=0)

    def add_global_template_values(self, template_values):
        template_values['App'] = App
        template_values['None'] = None

        if not template_values.has_key('user_data'):
            user_data = user_models.UserData.current()
            template_values['user_data'] = user_data

        user_data = template_values['user_data']

        display_name = ""
        if user_data:
            display_name = user_data.nickname or user_data.username

        template_values['server_time'] = time.time()

        # TODO(marcia): Remove username, points, logged_in template values
        # since they should be encapsulated in this UserProfile object
        logged_in_user_profile = util_profile.UserProfile.from_user(user_data,
                                                                    user_data)
        template_values['logged_in_user_profile'] = logged_in_user_profile

        # TODO(benkomalo): rename this global template property from "username"
        #    as it's not really the user's username, but just a display name.
        template_values['username'] = display_name
        template_values['points'] = user_data.points if user_data else 0
        template_values['logged_in'] = not user_data.is_phantom if user_data else False
        template_values['http_host'] = os.environ["HTTP_HOST"]

        # Always insert a post-login request before our continue url
        template_values['continue'] = url_util.create_post_login_url(
            template_values.get('continue') or self.request.uri)
        template_values['login_url'] = ('%s&direct=1' %
                                        url_util.create_login_url(
                                            template_values['continue']))
        template_values['logout_url'] = url_util.create_logout_url(
            self.request.uri)

        # TODO(stephanie): these settings are temporary; for FB testing purposes only
        template_values['site_base_url'] = 'http://%s' % os.environ["HTTP_HOST"]

        template_values['is_mobile'] = False
        template_values['is_mobile_capable'] = False
        template_values['is_ipad'] = False

        if self.is_mobile_capable():
            template_values['is_mobile_capable'] = True
            template_values['is_ipad'] = self.is_ipad()

            if 'is_mobile_allowed' in template_values and template_values['is_mobile_allowed']:
                template_values['is_mobile'] = self.is_mobile()

        # overridable hide_analytics querystring that defaults to true in dev
        # mode but false for prod.
        hide_analytics = self.request_bool("hide_analytics", App.is_dev_server)
        template_values['hide_analytics'] = hide_analytics

        # client-side error logging
        template_values['include_errorception'] = gandalf('errorception')

        # Analytics
        template_values['mixpanel_enabled'] = gandalf('mixpanel_enabled')

        # Enable for Mixpanel testing only
        # You will need to ask Tom, Kitt, or Marcia to add you to the "Khan
        # Academy Test" project on Mixpanel so that you can see the results.
        if False:
            template_values['mixpanel_test'] = "70acc4fce4511b89477ac005639cfee1"
            template_values['mixpanel_enabled'] = True
            template_values['hide_analytics'] = False

        if template_values['mixpanel_enabled']:
            template_values['mixpanel_id'] = gae_bingo.identity.identity()

        if not template_values['hide_analytics']:
            superprops_list = user_models.UserData.get_analytics_properties(user_data)

            # Create a superprops dict for MixPanel with a version number
            # Bump the version number if changes are made to the client-side
            # analytics code and we want to be able to filter by version.
            template_values['mixpanel_superprops'] = dict(superprops_list)

            # Copy over first 4 per-user properties for GA
            # (The 5th is reserved for Bingo)
            template_values['ga_custom_vars'] = superprops_list[0:4]

        if user_data:
            user_goals = goals.models.GoalList.get_current_goals(user_data)
            goals_data = [g.get_visible_data() for g in user_goals]
            if goals_data:
                template_values['global_goals'] = jsonify(goals_data)

        badges_earned = badges.util_badges.get_badge_notifications_json()
        template_values['badges_earned'] = badges_earned

        # Disable topic browser in the header on mobile devices
        template_values['watch_topic_browser_enabled'] = not self.is_mobile_capable()

        template_values['show_topic_pages'] = True

        return template_values

    def redirect(self, uri, *args, **kwargs):
        """Override to handle locations with non-ASCII unicode characters.

        A URI containing non-ASCII characters is known as an IRI, or
        Internationalized Resource Identifier. This override conveniently
        converts IRIs to URIs for use in the HTTP Location header.
        See http://www.ietf.org/rfc/rfc3987.txt

        webapp2.RequestHandler has redirect() and redirect_to(). Since
        redirect_to() calls redirect(), this override handles both cases.
        """
        uri = url_util.iri_to_uri(uri)
        super(RequestHandler, self).redirect(uri, *args, **kwargs)

    def render_jinja2_template(self, template_name, template_values):
        self.add_global_template_values(template_values)
        self.response.write(self.render_jinja2_template_to_string(template_name, template_values))

    def render_jinja2_template_to_string(self, template_name, template_values):
        return shared_jinja.template_to_string(template_name, template_values)

    def render_json(self, obj, camel_cased=False):
        json_string = jsonify(obj, camel_cased=camel_cased)
        self.response.content_type = "application/json"
        self.response.out.write(json_string)

    def render_jsonp(self, obj, camel_cased=False):
        if isinstance(obj, basestring):
            json_string = obj
        else:
            json_string = jsonify(obj, camel_cased=camel_cased)
        callback = self.request_string("callback")
        if callback:
            self.response.out.write("%s(%s)" % (callback, json_string))
        else:
            self.response.out.write(json_string)
