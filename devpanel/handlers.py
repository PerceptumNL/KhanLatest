import logging

from google.appengine.ext import db, deferred
import user_util
from user_models import UserData
from common_core.models import CommonCoreMap
import request_handler

import csv
import StringIO


class Panel(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):
        self.render_jinja2_template('devpanel/panel.html',
                                    {"selected_id": "panel"})

class CoachesList(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):
        import coaches_utils
        template_values = {
            "rows": coaches_utils.get_coaches_students_count()
        }

        self.render_jinja2_template("devpanel/coaches_list.html",
                                    template_values)


class MergeUsers(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):

        source = self.request_user_data("source_email")
        target = self.request_user_data("target_email")

        merged = self.request_bool("merged", default=False)
        merge_error = ""

        if not merged and bool(source) != bool(target):
            merge_error = ("Both source and target user emails must "
                           "correspond to existing accounts before they can "
                           "be merged.")

        template_values = {
                "selected_id": "users",
                "source": source,
                "target": target,
                "merged": merged,
                "merge_error": merge_error,
        }

        self.render_jinja2_template("devpanel/mergeusers.html",
                                    template_values)

    @user_util.developer_required
    def post(self):

        if not self.request_bool("confirm", default=False):
            self.get()
            return

        source = self.request_user_data("source_email")
        target = self.request_user_data("target_email")

        if source and target:

            old_source_email = source.email

            # Make source the new official user, because it has all
            # the historical data.  Just copy over target's
            # identifying properties.
            source.current_user = target.current_user
            source.user_email = target.user_email
            source.user_nickname = target.user_nickname
            source.user_id = target.user_id

            # Put source, which gives it the same identity as target 
            source.put()

            # Delete target
            target.delete()

            self.redirect(("/devadmin/emailchange"
                           "?merged=1&source_email=%s&target_email=%s")
                          % (old_source_email, target.email))
            return

        self.redirect("/devadmin/emailchange")
        

class DeleteAccount(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):
        self.render_jinja2_template("devpanel/deleteuser.html", {})


class Manage(request_handler.RequestHandler):

    @user_util.admin_required  # only admins may add devs, devs cannot add devs
    def get(self):
        developers = UserData.all()
        developers.filter('developer = ', True).fetch(1000)
        template_values = { 
            "developers": developers,
            "selected_id": "devs",
        }

        self.render_jinja2_template('devpanel/devs.html', template_values) 
        

class ManageCoworkers(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):

        user_data_coach = self.request_user_data("coach_email")
        user_data_coworkers = []

        if user_data_coach:
            user_data_coworkers = user_data_coach.get_coworkers_data()

        template_values = {
            "user_data_coach": user_data_coach,
            "user_data_coworkers": user_data_coworkers,
            "selected_id": "coworkers",
        }

        self.render_jinja2_template("devpanel/coworkers.html", template_values)
        

def update_common_core_map(cc_file):
    logging.info("Deferred job <update_common_core_map> started")
    reader = csv.reader(cc_file, delimiter='\t')
    _ = reader.next()
    cc_list = []
    cc_standards = {}
    for line in reader:
        cc_standard = line[0]
        cc_cluster = line[1]
        try:
            cc_description = line[2].encode('utf-8')
        except Exception:
            cc_description = cc_cluster
        exercise_name = line[3]
        video_youtube_id = line[4]

        if len(cc_standard) == 0:
            continue

        if cc_standard in cc_standards:
            cc = cc_standards[cc_standard]
        else:
            cc = CommonCoreMap.all().filter('standard = ', cc_standard).get()
            if cc is None:
                cc = CommonCoreMap()

            cc_standards[cc_standard] = cc
            cc_list.append(cc)

        cc.update_standard(cc_standard, cc_cluster, cc_description)

        if len(exercise_name) > 0:
            cc.update_exercise(exercise_name)

        if len(video_youtube_id) > 0:
            cc.update_video(video_youtube_id)

        if len(cc_list) > 500:
            db.put(cc_list)
            cc_list = []
            cc_standards = {}

    db.put(cc_list)

    return


class ManageCommonCore(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):
        template_values = {
            "selected_id": "commoncore",
        } 

        self.render_jinja2_template("devpanel/uploadcommoncorefile.html",
                                    template_values)

    @user_util.developer_required
    def post(self):

        logging.info("Accessing %s" % self.request.path)

        cc_file = StringIO.StringIO(self.request_string('commoncore'))
        deferred.defer(update_common_core_map, cc_file)

        self.redirect("/devadmin")
        return
