# -*- coding: utf-8 -*-

from __future__ import absolute_import
from datetime import datetime
import random
import logging

# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

from google.appengine.api import users

import request_handler
import user_util
from knowledgemap.knowledgemap_util import deserializeMapCoords
from library import library_content_html
from phantom_users.phantom_util import create_phantom
from user_models import UserData
from exercise_models import UserExercise, Exercise, UserExerciseGraph
from video_models import Video, VideoLog
from .models import Goal, GoalList, GoalObjective


class CreateNewGoal(request_handler.RequestHandler):

    @user_util.login_required
    @create_phantom
    def get(self):
        user_data = UserData.current()
        user_exercise_graph = UserExerciseGraph.get(user_data)

        from exercises.exercise_util import exercise_graph_dict_json

        context = {
            'graph_dict_data': exercise_graph_dict_json(
                user_data, user_exercise_graph),
            'user_data': user_data,
            'map_coords': json.dumps(
                deserializeMapCoords(user_data.map_coords)),

            # Get pregenerated library content from our in-memory/memcache
            # two-layer cache
            'library_content': library_content_html(),
        }
        self.render_jinja2_template("goals/creategoal.html", context)


class CreateRandomGoalData(request_handler.RequestHandler):
    first_names = ["Aston", "Stratford", "Leanian", "Patwin", "Renaldo",
        "Welford", "Maher", "Gregorio", "Roth", "Gawain", "Fiacre",
        "Coillcumhann", "Honi", "Westcot", "Walden", "Onfroi", "Merlow",
        "Gimm", "Dumont", "Weorth", "Corcoran", "Sinley", "Perekin", "Galt",
        "Tequiefah", "Zina", "Hemi Skye", "Adelie", "Afric", "Laquinta",
        "Molli", "Cimberleigh", "Morissa", "Alastriona", "Ailisa", "Leontina",
        "Aruba", "Marilda", "Ascencion", "Lidoine", "Winema", "Eraman", "Atol",
        "Karline", "Edwinna", "Yseult", "Florencia", "Bethsaida", "Aminah",
        "Onida"]
    last_names = ["Smith", "Jackson", "Martin", "Brown", "Roy", "Tremblay",
        "Lee", "Gagnon", "Wilson", "Clark", "Johnson", "White", "Williams",
        "Taylor", "Campbell", "Anderson", "Cooper", "Jones", "Lambert"]

    @user_util.developer_required
    def get(self):
        from exercises import attempt_problem

        login_user = UserData.current()
        exercises_list = [exercise for exercise in Exercise.all()]
        videos_list = [video for video in Video.all()]

        user_count = self.request_int('users', 5)
        for user_id in xrange(0, user_count):
            # Create a new user
            first_name = random.choice(CreateRandomGoalData.first_names)
            last_name = random.choice(CreateRandomGoalData.last_names)
            nickname = "%s %s" % (first_name, last_name)
            email = 'test_%i@automatedrandomdata' % user_id
            user = users.User(email)

            logging.info("Creating user %s: (%i/%i)"
                % (nickname, user_id + 1, user_count))

            user_data = UserData.get_or_insert(
                key_name="test_user_%i" % user_id,
                user=user,
                current_user=user,
                user_id=str(user_id),
                moderator=False,
                last_login=datetime.now(),
                proficient_exercises=[],
                suggested_exercises=[],
                need_to_reassess=True,
                points=0,
                coaches=[login_user.user_email],
                user_email=email,
                user_nickname=nickname,
                )
            user_data.put()

            # Delete user exercise & video progress
            query = UserExercise.all()
            query.filter('user = ', user)
            for user_exercise in query:
                user_exercise.delete()

            query = VideoLog.all()
            query.filter('user = ', user)
            for user_video in query:
                user_video.delete()

            # Delete existing goals
            GoalList.delete_all_goals(user_data)

            for goal_idx in xrange(1, random.randint(-1, 4)):
                # Create a random goal
                obj_descriptors = []

                for objective in xrange(1, random.randint(2, 4)):
                    obj_descriptors.append({
                        'type': 'GoalObjectiveExerciseProficiency',
                        'exercise': random.choice(exercises_list)})

                for objective in xrange(1, random.randint(2, 4)):
                    obj_descriptors.append({
                        'type': 'GoalObjectiveWatchVideo',
                        'video': random.choice(videos_list)})

                title = first_name + "'s Goal #" + str(goal_idx)
                logging.info("Creating goal " + title)

                objectives = GoalObjective.from_descriptors(obj_descriptors,
                    user_data)
                goal = Goal(parent=user_data, title=title,
                    objectives=objectives)
                user_data.save_goal(goal)

                for objective in obj_descriptors:
                    if objective['type'] == 'GoalObjectiveExerciseProficiency':
                        user_exercise = user_data.get_or_insert_exercise(
                            objective['exercise'])
                        chooser = random.randint(1, 120)
                        if chooser >= 60:
                            continue
                        elif chooser > 15:
                            count = 1
                            hints = 0
                        elif chooser < 7:
                            count = 20
                            hints = 0
                        else:
                            count = 25
                            hints = 1
                        logging.info(
                            "Starting exercise: %s (%i problems, %i hints)" %
                            (objective['exercise'].name, count, hints * count))
                        for i in xrange(1, count):
                            attempt_problem(
                                user_data, user_exercise, i, 1, 'TEST', 'TEST',
                                'TEST', True, hints, 0, False, False, "TEST",
                                '0.0.0.0')

                    elif objective['type'] == 'GoalObjectiveWatchVideo':
                        seconds = random.randint(1, 1200)
                        logging.info("Watching %i seconds of video %s"
                            % (seconds, objective['video'].title))
                        VideoLog.add_entry(user_data, objective['video'],
                            seconds, 0, detect_cheat=False)

        self.response.out.write('OK')
