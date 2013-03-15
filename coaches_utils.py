import coaches
try:
    import json
except ImportError:
    import simplejson as json

import custom_exceptions
import url_util
import user_util
import request_handler

from user_models import UserData, StudentList
from coach_resources.coach_request_model import CoachRequest

import profiles.util_profile as util_profile
import json
import logging

def get_coaches_list():
    users = UserData.all().fetch(999999)

    coaches_dict = {}
    for user in users:
        for coach in user.coaches:
            if not coach in coaches_dict:
                coaches_dict[coach] = [user.user_email]
            else:
                coaches_dict[coach].append(user.user_email)

    coaches_list = []
    for k, v in coaches_dict.items():
        coach = UserData.get_from_username_or_email(k)
        coach_dict = { 
                        "joined": str(coach.joined),
                        "last_activity": str(coach.last_activity),
                        "coach_email": k,
                        "number_of_students": len(v)
                     }
        coaches_list.append(coach_dict)
        
    return coaches_list
