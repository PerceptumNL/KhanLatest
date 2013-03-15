import coaches
try:
    import json
except ImportError:
    import simplejson as json

import custom_exceptions
import url_util
import user_util
import request_handler
import layer_cache

from user_models import UserData, StudentList
from coach_resources.coach_request_model import CoachRequest

import profiles.util_profile as util_profile
import json
import logging

import datetime
from google.appengine.ext import deferred



class UpdateCoachesList(request_handler.RequestHandler):

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def get(self):
        """update get the blog entries add the new ones """
        deferred.defer(get_coaches_list)
        self.response.write("sent to queue")     
        #coaches = get_coaches_list()
        #logging.info("Found %d coaches" % len(coaches))

#@layer_cache.cache_with_key_fxn(
#    lambda: "coaches_utils.get_coaches_all_students_%s" % str(datetime.datetime.now()))
def get_coaches_all_students():
    users = UserData.all()
    coaches_dict = {}
    for user in users:
        for coach in user.coaches:
            if not coach in coaches_dict:
                coaches_dict[coach] = [user.user_email]
            else:
                coaches_dict[coach].append(user.user_email)
    return coaches_dict

def get_coaches_students_count():
    coaches_dict = get_coaches_all_students()
    coaches_list = []
    for coach_email, students_list in coaches_dict.items():
        coach = UserData.all().filter("user_email = ", coach_email).get()
        if coach:
            coach_dict = { 
                            "joined": str(coach.joined),
                            "last_activity": str(coach.last_activity),
                            "coach_email": coach_email,
                            "number_of_students": len(students_list)
                         }
            coaches_list.append(coach_dict)
    return coaches_list
