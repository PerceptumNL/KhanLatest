import datetime
import time
import exercise_models
from secrets import *
import base64
import logging
import json
from app import App
import urllib


#if App.is_dev_server:
#    import urlfetch
#else:
from google.appengine.api import urlfetch

class TinCan():
    testMode = False
    def __init__(self):
        self.user_email = None
        self.statement = {
          "verb": {},
          "version": "1.0.0",
          "timestamp": None,
          "object": {},
          "actor": {}
        }

    def set_actor_from_user(self, user):
        self.user_email = user.user_email
        self.statement["actor"] = {
            "mbox": "mailto:%s" % user.user_email,
            "name": user.user_nickname,
            "objectType": "Agent"
        }

    def set_assessment(self, exercise):
        name = exercise.pretty_display_name or exercise.name, 
        description = exercise.description or "", 
        exercise_id = exercise.name

        self.statement["object"] = {
          "definition": {
            "type": "http://adlnet.gov/expapi/activities/assessment",
            "name": {
              "en-US": name,
            },
            "description": {
              "en-US": description,
            }
          },
          "id": "http://www.iktel.nl/exercise/%s" % exercise_id,
          "objectType": "Activity"
        }

    def set_question(self, exercise):
        name = exercise.pretty_display_name or exercise.name,
        description = exercise.description or ""
        exercise_id = exercise.name

        self.statement["object"] = {
          "definition": {
            "type": "http://adlnet.gov/expapi/activities/question",
            "name": {
              "en-US": name,
            },
            "description": {
              "en-US": description,
            }
          },
          "id": "http://www.iktel.nl/exercise/%s" % (exercise_id),
          "objectType": "Activity"
        }

    def set_media(self, video):
        name = video.title
        description = video.description
        video_id = video.readable_id
        #add youtube_id?

        self.statement["object"] = {
          "definition": {
            "type": "http://adlnet.gov/expapi/activities/media",
            "name": {
              "en-US": name,
            },
            "description": {
              "en-US": description,
            }
          },
          "id": "http://www.iktel.nl/video/%s" % (video_id),
          "objectType": "Activity"
        }

    def set_verb(self, verb):
        self.statement['verb'] = {
          "id": "http://adlnet.gov/expapi/verbs/%s" % verb,
          "display": {
            "en-US": "%s" % verb
          }
        }

    def set_timestamp(self):
        #self.statement['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S.000000%z")
        self.statement['timestamp'] = datetime.datetime.today().isoformat()


    def set_result(self, k, v):
        if not "result" in self.statement:
            self.statement["result"] = {}
        self.statement["result"][k] = v

    def set_result_extension(self, k, v):
        if not "result" in self.statement:
            self.statement["result"] = {"extension": { k : v }}
        elif not "extensions" in self.statement["result"]:
            self.statement["result"]["extension"] = { k : v }
        else:
            self.statement["result"]["extension"][k] = v

    def set_progress(self, progress):
        self.set_result_extension("http://iktel.nl/coach/progress", progress)

    def set_success(self, result):
        self.statement['result'] = result
 
    #change problem_log and user_exercise directly by progress and correct
    @classmethod
    def create_question(cls, user, verb, exercise, problem_log=None, user_exercise=None):
        tc = cls()
        tc.set_actor_from_user(user)
        tc.set_question(exercise)
        tc.set_timestamp()
        tc.set_verb(verb)

        if verb == "progressed" and user_exercise:
            tc.set_progress(user_exercise.progress)

        if verb == "answered" and problem_log:
            tc.set_result("success", problem_log.correct)

        if verb == "completed" and problem_log:
            tc.set_result("success", problem_log.correct)

        tc.push()
        return tc

    @classmethod
    def create_media(cls, user, verb, video, userVideo=None):
        tc = cls()
        tc.set_actor_from_user(user)

        tc.set_media(video)
        tc.set_timestamp()
        tc.set_verb(verb)

        if verb == "progressed" and userVideo:
            per = float(userVideo.last_second_watched) / userVideo.duration
            tc.set_result_extension("http://iktel.nl/coach/progress", per)

        tc.push()
        return tc

    def log_statement(self):
        logging.error(json.dumps(self.statement,sort_keys=True,
                                 indent=4, separators=(',', ': ')))

    def check_email(self):
        import re
        for m in tincan_whitelist:
            if re.match(m, self.user_email):
                return True
        return False
        

    def push(self):
        logging.error(self.user_email)
        if not self.check_email(): 
            return

        auth_token = base64.b64encode("%s:%s" % (tincan_user, tincan_pw))
        tincan_headers = {
          "Authorization": "Basic %s" % auth_token,
          "X-Experience-API-Version":"1.0.0",
          'Content-Type': 'application/json',
        }

        tincan_data = json.dumps(self.statement)
        
        if App.is_dev_server:
            if self.testMode:
                self.log_statement()
            else:
                res = urlfetch.post(
                    tincan_url,
                    headers = tincan_headers,
                    data = tincan_data
                )
                logging.error(res.status)
                logging.error(res.content)
                self.log_statement()
        else:
            res = urlfetch.fetch(url=tincan_url,
                payload=tincan_data,
                method=urlfetch.POST,
                headers=tincan_headers)
            logging.error(res.status_code)
            logging.error(res.content) 
            self.log_statement()
