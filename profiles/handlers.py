import datetime
import urllib

# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

import promo_record_model
import setting_model
from profiles import templatetags
import request_handler
import url_util
import user_models
import user_util
import util_profile
import exercise_models
import consts
from api.auth.xsrf import ensure_xsrf_cookie
from user_models import StudentList, UserData, ParentChildPair


class ViewClassProfile(request_handler.RequestHandler):
    @user_util.login_required_and(phantom_user_allowed=False,
                                  child_user_allowed=False,
                                  demo_user_allowed=True)
    def get(self, subpath=None):
        """Render class profile.

        Keyword arguments:
        subpath -- matches the grouping in /class_profile/(.*) and is ignored
        server-side, but is used to route client-side
        """
        coach = UserData.current()

        user_override = self.request_user_data("coach_email")
        if user_override and user_override.are_students_visible_to(coach):
            # Only allow looking at a student list other than your own
            # if you are a dev, admin, or coworker.
            coach = user_override

        student_lists = StudentList.get_for_coach(coach.key())

        student_lists_list = [{
            'key': 'allstudents',
            'name': 'All students',
        }]
        for student_list in student_lists:
            student_lists_list.append({
                'key': str(student_list.key()),
                'name': student_list.name,
            })

        list_id, _ = util_profile.get_last_student_list(self, student_lists,
                                           coach == UserData.current())
        current_list = None
        for student_list in student_lists_list:
            if student_list['key'] == list_id:
                current_list = student_list

        selected_graph_type = (self.request_string("selected_graph_type") or
                               ClassProgressReportGraph.GRAPH_TYPE)
        # TomY This is temporary until all the graphs are API calls
        if (selected_graph_type == 'progressreport' or
                selected_graph_type == 'goals'):
            initial_graph_url = ("/api/v1/user/students/%s?coach_email=%s&%s" %
                (selected_graph_type,
                 urllib.quote(coach.email),
                 urllib.unquote(self.request_string("graph_query_params",
                                                    default=""))))
        else:
            initial_graph_url = ("/profile/graph/%s?coach_email=%s&%s" % (
                selected_graph_type,
                urllib.quote(coach.email),
                urllib.unquote(self.request_string("graph_query_params",
                                                   default=""))))
        initial_graph_url += 'list_id=%s' % list_id

        template_values = {
                'user_data_coach': coach,
                'coach_email': coach.email,
                'list_id': list_id,
                'student_list': current_list,
                'student_lists': student_lists_list,
                'student_lists_json': json.dumps(student_lists_list),
                'coach_nickname': coach.nickname,
                'selected_graph_type': selected_graph_type,
                'initial_graph_url': initial_graph_url,
                'exercises': exercise_models.Exercise.get_all_use_cache(),
                'is_profile_empty': not coach.has_students(),
                'selected_nav_link': 'coach',
                "view": self.request_string("view", default=""),
                'stats_charts_class': 'coach-view',
                }
        self.render_jinja2_template('viewclassprofile.html', template_values)


class ViewProfile(request_handler.RequestHandler):
    # TODO(sundar) - add login_required_special(demo_allowed = True)
    # However, here only the profile of the students of the demo
    # account are allowed
    @user_util.open_access
    @ensure_xsrf_cookie
    def get(self, username=None, subpath=None):

        """Render a student profile.

        Keyword arguments:
        email_or_username -- matches the first grouping in /profile/(.+?)/(.*)
        subpath -- matches the second grouping, and is ignored server-side,
        but is used to route client-side

        """
        current_user_data = UserData.current() or UserData.pre_phantom()

        if current_user_data.is_pre_phantom and username is None:
            # Pre-phantom users don't have any profiles - just redirect them
            # to the homepage if they try to view their own.
            self.redirect(url_util.create_login_url(self.request.uri))
            return

        if not current_user_data.is_phantom and username == 'nouser':
            # If anybody has bookmarked, or gets redirected to, or otherwise
            # finds their way to /profile/nouser while they're logged in, just
            # redirect them to their actual profile.
            #
            # /profile/nouser is only sensible for phantom users and is never
            # used to look at another user's profile.
            self.redirect(current_user_data.profile_root)
            return

        if not username:
            user_data = current_user_data
        elif username == 'nouser' and current_user_data.is_phantom:
            user_data = current_user_data
        else:
            user_data = UserData.get_from_url_segment(username)
            if (user_models.UniqueUsername.is_valid_username(username)
                    and user_data
                    and user_data.username
                    and user_data.username != username):
                # The path segment is a username and resolved to the user,
                # but is not actually their canonical name. Redirect to the
                # canonical version.
                if subpath:
                    self.redirect("/profile/%s/%s" % (user_data.username,
                                                      subpath))
                else:
                    self.redirect("/profile/%s" % user_data.username)
                return

        profile = util_profile.UserProfile.from_user(user_data,
                current_user_data)

        if profile is None:
            self.render_jinja2_template('noprofile.html', {})
            return

        is_self = user_data.user_id == current_user_data.user_id
        show_intro = False
        show_discussion_intro = False

        if is_self:
            promo_record = promo_record_model.PromoRecord.get_for_values(
                    "New Profile Promo", user_data.user_id)

            if promo_record is None:
                # The user has never seen the new profile page! Show a tour.
                if subpath:
                    # But if they're not on the root profile page, force them.
                    self.redirect("/profile")
                    return

                show_intro = True
                promo_record_model.PromoRecord.record_promo(
                    "New Profile Promo", user_data.user_id, skip_check=True)
                # We also mark the "new discussion promo" as having been seen,
                # because it is a sub-set of the full tour, and new users don't
                # need to see it twice.
                promo_record_model.PromoRecord.record_promo(
                    "New Discussion Promo", user_data.user_id, skip_check=True)
            else:
                # The user has already seen the original profile page tour, but
                # not necessarily the "new discussion tab" tour.
                discussion_promo_record = (
                    promo_record_model.PromoRecord.get_for_values(
                        "New Discussion Promo", user_data.user_id))

                if discussion_promo_record is None:
                    # The user hasn't seen the new discussion promo.
                    show_discussion_intro = True
                    promo_record_model.PromoRecord.record_promo(
                        "New Discussion Promo", user_data.user_id,
                            skip_check=True)

        # This is the main capability bit - it indicates whether or not the
        # actor can view exercise, video, and goals data on the site for the
        # current profile.
        is_activity_visible = user_data.is_visible_to(current_user_data)

        # Resolve any other miscellaneous capabilities. This may need to be
        # changed if ACLing gets signicantly more complicated.
        if is_self:
            is_settings_available = not user_data.is_child_account()
            is_discussion_available = not user_data.is_child_account()
            is_coach_list_readable = True
            is_coach_list_writable = user_data.can_modify_coaches()
        else:
            is_actor_parent = ParentChildPair.is_pair(
                    parent_user_data=current_user_data,
                    child_user_data=user_data)
            is_settings_available = is_actor_parent
            is_discussion_available = (is_activity_visible and
                                       not user_data.is_child_account())
            is_coach_list_readable = is_actor_parent
            is_coach_list_writable = False

        tz_offset = self.request_int("tz_offset", default=0)

        # If profile is public and / or activity is visible,
        # include all the relevant data.
        if profile.is_public or is_activity_visible:
            template_values = {
                'show_intro': show_intro,
                'show_discussion_intro': show_discussion_intro,
                'profile': profile,
                'tz_offset': tz_offset,
                'count_videos': setting_model.Setting.count_videos(),
                'count_exercises': exercise_models.Exercise.get_count(),
                'user_data_student':
                    user_data if is_activity_visible else None,
                'profile_root': user_data.profile_root,
                'is_settings_available': is_settings_available,
                'is_coach_list_readable': is_coach_list_readable,
                'is_coach_list_writable': is_coach_list_writable,
                'is_discussion_available': is_discussion_available,
                'view': self.request_string("view", default=""),
            }

        # For private profiles
        else:
            template_values = {
                'profile': profile,
                'profile_root': profile.profile_root,
                'user_data_student': None,
                'count_videos': 0,
                'count_exercises': 0
            }
        self.render_jinja2_template('viewprofile.html', template_values)


class ProfileGraph(request_handler.RequestHandler):

    @user_util.open_access    # TODO(csilvers): is this right? -- ask marcia
    def get(self):
        html = ""
        json_update = ""

        user_data_target = self.get_profile_target_user_data()
        if user_data_target:
            if self.redirect_if_not_ajax(user_data_target):
                return

            if self.request_bool("update", default=False):
                json_update = self.json_update(user_data_target)
            else:
                html_and_context = self.graph_html_and_context(
                    user_data_target)

                if ("is_graph_empty" in html_and_context["context"] and
                        html_and_context["context"]["is_graph_empty"]):
                    # This graph is empty of activity. If it's a
                    # date-restricted graph, see if bumping out the
                    # time restrictions can help.
                    if self.redirect_for_more_data():
                        return

                html = html_and_context["html"]

        if len(json_update) > 0:
            self.response.out.write(json_update)
        else:
            self.response.out.write(html)

    def get_profile_target_user_data(self):
        return self.request_visible_student_user_data()

    def redirect_if_not_ajax(self, student):
        if not self.is_ajax_request():
            # If it's not an ajax request, redirect to the appropriate
            # /profile URL
            self.redirect(
                "/profile?selected_graph_type=%s&student_email=%s&"
                "graph_query_params=%s" % (
                    self.GRAPH_TYPE,
                    urllib.quote(student.email),
                    urllib.quote(urllib.quote(self.request.query_string))))
            return True
        return False

    def redirect_for_more_data(self):
        return False

    def json_update(self, user_data):
        return ""


class ClassProfileGraph(ProfileGraph):
    def get_profile_target_user_data(self):
        coach = UserData.current()

        if coach:
            user_override = self.request_user_data("coach_email")
            if user_override and user_override.are_students_visible_to(coach):
                # Only allow looking at a student list other than your own
                # if you are a dev, admin, or coworker.
                coach = user_override

        return coach

    def redirect_if_not_ajax(self, coach):
        if not self.is_ajax_request():
            # If it's not an ajax request, redirect to the appropriate
            # /profile URL
            self.redirect(
                "/class_profile?selected_graph_type=%s&coach_email=%s&"
                "graph_query_params=%s" % (
                    self.GRAPH_TYPE,
                    urllib.quote(coach.email),
                    urllib.quote(urllib.quote(self.request.query_string))))
            return True
        return False

    def get_student_list(self, coach):
        student_lists = StudentList.get_for_coach(coach.key())
        current_user_is_coach = (coach.key() == UserData.current().key())
        _, actual_list = util_profile.get_last_student_list(self,
                student_lists, current_user_is_coach)
        return actual_list


class ProfileDateToolsGraph(ProfileGraph):

    DATE_FORMAT = "%Y-%m-%d"

    @staticmethod
    def inclusive_start_date(dt):
        # Inclusive of start date
        return datetime.datetime(dt.year, dt.month, dt.day, 0, 0, 0)

    @staticmethod
    def inclusive_end_date(dt):
        # Inclusive of end date
        return datetime.datetime(dt.year, dt.month, dt.day, 23, 59, 59)

    def request_date_ctz(self, key):
        # Always work w/ client timezone dates on the client and UTC
        # dates on the server
        dt = self.request_date(key, self.DATE_FORMAT,
                               default=datetime.datetime.min)
        if dt == datetime.datetime.min:
            dt_ctz = self.utc_to_ctz(datetime.datetime.now())
            s_dt = self.request_string(key, default="")
            if s_dt == "today":
                dt = self.inclusive_start_date(dt_ctz)
            elif s_dt == "yesterday":
                dt = self.inclusive_start_date(dt_ctz -
                                               datetime.timedelta(days=1))
            elif s_dt == "lastweek":
                dt = self.inclusive_start_date(dt_ctz -
                                               datetime.timedelta(days=6))
            elif s_dt == "lastmonth":
                dt = self.inclusive_start_date(dt_ctz -
                                               datetime.timedelta(days=29))
        return dt

    def tz_offset(self):
        return self.request_int("tz_offset", default=0)

    def ctz_to_utc(self, dt_ctz):
        return dt_ctz - datetime.timedelta(minutes=self.tz_offset())

    def utc_to_ctz(self, dt_utc):
        return dt_utc + datetime.timedelta(minutes=self.tz_offset())


class ClassProfileDateGraph(ClassProfileGraph, ProfileDateToolsGraph):

    DATE_FORMAT = "%m/%d/%Y"

    def get_date(self):
        dt_ctz = self.request_date_ctz("dt")

        if dt_ctz == datetime.datetime.min:
            # If no date, assume looking at today
            dt_ctz = self.utc_to_ctz(datetime.datetime.now())

        return self.ctz_to_utc(self.inclusive_start_date(dt_ctz))


class ProfileDateRangeGraph(ProfileDateToolsGraph):

    def get_start_date(self):
        dt_ctz = self.request_date_ctz("dt_start")

        if dt_ctz == datetime.datetime.min:
            # If no start date, assume looking at last 7 days
            dt_ctz = self.utc_to_ctz(datetime.datetime.now() -
                                     datetime.timedelta(days=6))

        return self.ctz_to_utc(self.inclusive_start_date(dt_ctz))

    def get_end_date(self):
        dt_ctz = self.request_date_ctz("dt_end")
        dt_start_ctz_test = self.request_date_ctz("dt_start")
        dt_start_ctz = self.utc_to_ctz(self.get_start_date())

        if (dt_ctz == datetime.datetime.min and
                dt_start_ctz_test == datetime.datetime.min):
            # If no end date or start date specified, assume looking
            # at 7 days after start date
            dt_ctz = dt_start_ctz + datetime.timedelta(days=6)
        elif dt_ctz == datetime.datetime.min:
            # If start date specified but no end date, assume one day
            dt_ctz = dt_start_ctz

        if ((dt_ctz - dt_start_ctz).days > consts.MAX_GRAPH_DAY_RANGE or
                dt_start_ctz > dt_ctz):
            # Maximum range of 30 days for now
            dt_ctz = (dt_start_ctz +
                      datetime.timedelta(days=consts.MAX_GRAPH_DAY_RANGE))

        return self.ctz_to_utc(self.inclusive_end_date(dt_ctz))

    def redirect_for_more_data(self):
        dt_start_ctz_test = self.request_date_ctz("dt_start")
        dt_end_ctz_test = self.request_date_ctz("dt_end")

        # If no dates were specified and activity was empty, try max
        # day range instead of default 7.
        if (dt_start_ctz_test == datetime.datetime.min and
                dt_end_ctz_test == datetime.datetime.min):
            self.redirect(self.request_url_with_additional_query_params(
                    "dt_start=lastmonth&dt_end=today&is_ajax_override=1"))
            return True

        return False


# TODO(sundar) - add login_required_special(demo_allowed = True)
# However, here only the profile of the students of the demo account
# are allowed
class ActivityGraph(ProfileDateRangeGraph):
    GRAPH_TYPE = "activity"

    def graph_html_and_context(self, student):
        return templatetags.profile_activity_graph(
            student, self.get_start_date(), self.get_end_date(),
            self.tz_offset())


# TODO(sundar) - add login_required_special(demo_allowed = True)
# However, here only the profile of the students of the demo account
# are allowed
class FocusGraph(ProfileDateRangeGraph):
    GRAPH_TYPE = "focus"

    def graph_html_and_context(self, student):
        return templatetags.profile_focus_graph(student, self.get_start_date(),
                                                self.get_end_date())


# TODO(sundar) - add login_required_special(demo_allowed = True)
# However, here only the profile of the students of the demo account
# are allowed
class ExercisesOverTimeGraph(ProfileGraph):
    GRAPH_TYPE = "exercisesovertime"

    def graph_html_and_context(self, student):
        return templatetags.profile_exercises_over_time_graph(student)


# TODO(sundar) - add login_required_special(demo_allowed = True)
# However, here only the profile of the students of the demo account
# are allowed
class ExerciseProblemsGraph(ProfileGraph):
    GRAPH_TYPE = "exerciseproblems"

    def graph_html_and_context(self, student):
        return templatetags.profile_exercise_problems_graph(
            student, self.request_string("exercise_name"))


# TODO(sundar) - add login_required_special(demo_allowed = True)
class ClassExercisesOverTimeGraph(ClassProfileGraph):
    GRAPH_TYPE = "classexercisesovertime"

    def graph_html_and_context(self, coach):
        student_list = self.get_student_list(coach)
        return templatetags.class_profile_exercises_over_time_graph(
            coach, student_list)


# TODO(sundar) - add login_required_special(demo_allowed = True)
class ClassProgressReportGraph(ClassProfileGraph):
    GRAPH_TYPE = "progressreport"


# TODO(sundar) - add login_required_special(demo_allowed = True)
class ClassTimeGraph(ClassProfileDateGraph):
    GRAPH_TYPE = "classtime"

    def graph_html_and_context(self, coach):
        student_list = self.get_student_list(coach)
        return templatetags.class_profile_time_graph(
            coach, self.get_date(), self.tz_offset(), student_list)


# TODO(sundar) - add login_required_special(demo_allowed = True)
class ClassEnergyPointsPerMinuteGraph(ClassProfileGraph):
    GRAPH_TYPE = "classenergypointsperminute"

    def graph_html_and_context(self, coach):
        student_list = self.get_student_list(coach)
        return templatetags.class_profile_energy_points_per_minute_graph(
            coach, student_list)

    def json_update(self, coach):
        student_list = self.get_student_list(coach)
        return templatetags.class_profile_energy_points_per_minute_update(
            coach, student_list)
