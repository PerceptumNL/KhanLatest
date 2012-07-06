# TODO(csilvers): rename this file to something better, and/or break it up.

# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

from google.appengine.ext import db
from google.appengine.ext import deferred

import custom_exceptions
import datetime
import exercise_models
import points
import topic_models
import user_util
import video_models

import badges.util_badges
import phantom_users

import gae_bingo.gae_bingo
from goals.models import GoalList
from experiments import StrugglingExperiment


def exercise_graph_dict_json(user_data, user_exercise_graph, admin=False):
    graph_dicts = user_exercise_graph.graph_dicts()
    if admin:
        suggested_graph_dicts = []
        proficient_graph_dicts = []
        recent_graph_dicts = []
        review_graph_dicts = []
    else:
        suggested_graph_dicts = user_exercise_graph.suggested_graph_dicts()
        proficient_graph_dicts = user_exercise_graph.proficient_graph_dicts()
        recent_graph_dicts = user_exercise_graph.recent_graph_dicts()
        review_graph_dicts = user_exercise_graph.review_graph_dicts()

    for graph_dict in suggested_graph_dicts:
        graph_dict["status"] = "Suggested"

    for graph_dict in proficient_graph_dicts:
        graph_dict["status"] = "Proficient"

    for graph_dict in recent_graph_dicts:
        graph_dict["recent"] = True

    for graph_dict in review_graph_dicts:
        graph_dict["status"] = "Review"

        try:
            suggested_graph_dicts.remove(graph_dict)
        except ValueError:
            pass

    goal_exercises = GoalList.exercises_in_current_goals(user_data)

    graph_dict_data = []
    for graph_dict in graph_dicts:
        row = {
            'name': graph_dict["name"],
            'points': graph_dict.get("points", ''),
            'display_name': graph_dict["display_name"],
            'status': graph_dict.get("status"),
            'recent': graph_dict.get("recent", False),
            'progress': graph_dict["progress"],
            'progress_display': exercise_models.UserExercise.to_progress_display(graph_dict["progress"]),
            'longest_streak': graph_dict["longest_streak"],
            'h_position': graph_dict["h_position"],
            'v_position': graph_dict["v_position"],
            'goal_req': (graph_dict["name"] in goal_exercises),
            'states': user_exercise_graph.states(graph_dict["name"]),

            # get_by_name returns only exercises visible to current user
            'prereqs': [prereq["name"] for prereq in graph_dict["prerequisites"] if exercise_models.Exercise.get_by_name(prereq["name"])],
        }

        if admin:
            exercise = exercise_models.Exercise.get_by_name(graph_dict["name"])
            row["live"] = exercise and exercise.live
        graph_dict_data.append(row)

    return json.dumps(graph_dict_data)


def make_wrong_attempt(user_data, user_exercise):
    if user_exercise and user_exercise.belongs_to(user_data):
        user_exercise.update_proficiency_model(correct=False)
        user_exercise.put()

        return user_exercise


def attempt_problem(user_data, user_exercise, problem_number, attempt_number,
    attempt_content, sha1, seed, completed, count_hints, time_taken,
    review_mode, topic_mode, problem_type, ip_address, card, stack_uid,
    topic_id, cards_done, cards_left, async_problem_log_put=True,
    async_stack_log_put=True):

    if user_exercise and user_exercise.belongs_to(user_data):
        dt_now = datetime.datetime.now()
        exercise = user_exercise.exercise_model

        user_exercise.last_done = dt_now
        user_exercise.seconds_per_fast_problem = exercise.seconds_per_fast_problem

        user_data.record_activity(user_exercise.last_done)

        # If somebody tries to answer a problem out-of-order, we need to raise
        # an exception.
        if problem_number != user_exercise.total_done + 1:

            # If we hit this error, make absolutely sure the UserExerciseCache
            # is up-to-date with this exercise's latest UserExercise state.
            # If they are out of sync, the user may repeatedly hit this crash.
            user_exercise_cache = exercise_models.UserExerciseCache.get(user_data)
            user_exercise_cache.update(user_exercise)
            user_exercise_cache.put()

            # If the client thinks it is ahead of the server, then we have an
            # issue worth paying attention to.
            error_class = Exception

            # If the client is behind the server, keep the error log quiet
            # because this is so easily caused by having two exercise tabs open
            # and letting one tab's client fall behind the server's state.
            if problem_number < user_exercise.total_done + 1:
                error_class = custom_exceptions.QuietException

            # If the client isn't aware that the user has recently logged out,
            # keep the error log quiet because this is so easily caused by
            # logging out of one tab and continuing work in another.
            if user_exercise.total_done == 0 and user_data.is_phantom:
                error_class = custom_exceptions.QuietException

            msg = "Problem out of order (%s, %s) for uid:%s, content:%s, seed:%s"

            raise error_class(msg % (problem_number,
                user_exercise.total_done + 1, user_data.user_id,
                attempt_content, seed))

        if len(sha1) <= 0:
            raise Exception("Missing sha1 hash of problem content.")

        if len(seed) <= 0:
            raise Exception("Missing seed for problem content.")

        if len(attempt_content) > 500:
            raise Exception("Attempt content exceeded maximum length.")

        # Build up problem log for deferred put
        problem_log = exercise_models.ProblemLog(
                key_name=exercise_models.ProblemLog.key_for(user_data, user_exercise.exercise, problem_number),
                user=user_data.user,
                user_id=user_data.user_id,
                exercise=user_exercise.exercise,
                problem_number=problem_number,
                time_taken=time_taken,
                time_done=dt_now,
                count_hints=count_hints,
                hint_used=count_hints > 0,
                correct=completed and not count_hints and (attempt_number == 1),
                sha1=sha1,
                seed=seed,
                problem_type=problem_type,
                count_attempts=attempt_number,
                attempts=[attempt_content],
                ip_address=ip_address,
                review_mode=review_mode,
                topic_mode=topic_mode,
        )

        first_response = (attempt_number == 1 and count_hints == 0) or (count_hints == 1 and attempt_number == 0)


        just_earned_proficiency = False

        # Users can only attempt problems for themselves, so the experiment
        # bucket always corresponds to the one for this current user
        struggling_model = StrugglingExperiment.get_alternative_for_user(
                 user_data, current_user=True) or StrugglingExperiment.DEFAULT
        if completed:

            user_exercise.total_done += 1

            if problem_log.correct:

                proficient = user_data.is_proficient_at(user_exercise.exercise)
                explicitly_proficient = user_data.is_explicitly_proficient_at(user_exercise.exercise)
                suggested = user_data.is_suggested(user_exercise.exercise)
                problem_log.suggested = suggested

                problem_log.points_earned = points.ExercisePointCalculator(user_exercise, topic_mode, suggested, proficient)
                user_data.add_points(problem_log.points_earned)

                # Streak only increments if problem was solved correctly (on first attempt)
                user_exercise.total_correct += 1
                user_exercise.streak += 1
                user_exercise.longest_streak = max(user_exercise.longest_streak, user_exercise.streak)

                user_exercise.update_proficiency_model(correct=True)

                gae_bingo.gae_bingo.bingo([
                    'struggling_problems_correct',
                    'problem_correct_binary', # Core metric
                    'problem_correct_count', # Core metric
                ])

                if user_exercise.progress >= 1.0 and not explicitly_proficient:
                    gae_bingo.gae_bingo.bingo([
                        'struggling_gained_proficiency_all',
                    ])
                    if not user_exercise.has_been_proficient():
                        gae_bingo.gae_bingo.bingo([
                            'new_proficiency_binary', # Core metric
                            'new_proficiency_count', # Core metric
                            ])

                    if user_exercise.history_indicates_struggling(struggling_model):
                        gae_bingo.gae_bingo.bingo(
                            'struggling_gained_proficiency_post_struggling')

                    user_exercise.set_proficient(user_data)
                    user_data.reassess_if_necessary()

                    just_earned_proficiency = True
                    problem_log.earned_proficiency = True

            badges.util_badges.update_with_user_exercise(
                user_data,
                user_exercise,
                include_other_badges=True,
                action_cache=badges.last_action_cache.LastActionCache.get_cache_and_push_problem_log(user_data, problem_log))

            # Update phantom user notifications
            phantom_users.util_notify.update(user_data, user_exercise)

            gae_bingo.gae_bingo.bingo([
                'struggling_problems_done',
                'problem_attempt_binary', # Core metric
                'problem_attempt_count', # Core metric
            ])

        else:
            # Only count wrong answer at most once per problem
            if first_response:
                user_exercise.update_proficiency_model(correct=False)
                gae_bingo.gae_bingo.bingo([
                    'struggling_problems_wrong',
                    'problem_incorrect_count', # Core metric
                    'problem_incorrect_binary', # Core metric
                ])

            if user_exercise.is_struggling(struggling_model):
                gae_bingo.gae_bingo.bingo('struggling_struggled_binary')

        # If this is the first attempt, update review schedule appropriately
        if attempt_number == 1:
            user_exercise.schedule_review(completed)

        user_exercise_graph = exercise_models.UserExerciseGraph.get_and_update(user_data, user_exercise)

        goals_updated = GoalList.update_goals(user_data,
            lambda goal: goal.just_did_exercise(user_data, user_exercise,
                just_earned_proficiency))

        # Bulk put
        db.put([user_data, user_exercise, user_exercise_graph.cache])

        if async_problem_log_put:
            # Defer the put of ProblemLog for now, as we think it might be causing hot tablets
            # and want to shift it off to an automatically-retrying task queue.
            # http://ikaisays.com/2011/01/25/app-engine-datastore-tip-monotonically-increasing-values-are-bad/
            deferred.defer(exercise_models.commit_problem_log, problem_log,
                           _queue="problem-log-queue",
                           _url="/_ah/queue/deferred_problemlog")
        else:
            exercise_models.commit_problem_log(problem_log)

        if user_data is not None and user_data.coaches:
            # Making a separate queue for the log summaries so we can clearly see how much they are getting used
            deferred.defer(video_models.commit_log_summary_coaches, problem_log, user_data.coaches,
                       _queue="log-summary-queue",
                       _url="/_ah/queue/deferred_log_summary")

        if user_data is not None and completed and stack_uid:
            # Update the stack log iff the user just finished this card.
            # If the request is missing the UID of the stack we're on, then
            # this is an old stack and we just won't log it
            stack_log_source = exercise_models.StackLog(
                    key_name=exercise_models.StackLog.key_for(user_data.user_id, stack_uid),
                    user_id=user_data.user_id,
                    time_last_done=datetime.datetime.now(),
                    review_mode=review_mode,
                    topic_mode=topic_mode,
                    exercise_id=user_exercise.exercise,
                    topic_id=topic_id,
                    cards_list=[],
                    extra_data={},
            )

            if topic_mode:
                stack_log_source.extra_data['topic_mode'] = calc_topic_mode_log_stats(
                        user_exercise_graph, topic_id, just_earned_proficiency)

            if async_stack_log_put:
                deferred.defer(exercise_models.commit_stack_log,
                               stack_log_source, card, cards_done, cards_left,
                               problem_log.__class__.__name__,
                               str(problem_log.key()),
                               _queue="stack-log-queue",
                               _url="/_ah/queue/deferred_stacklog")
            else:
                exercise_models.commit_stack_log(
                    stack_log_source, card, cards_done, cards_left,
                    problem_log.__class__.__name__, str(problem_log.key()))

        return user_exercise, user_exercise_graph, goals_updated

def calc_topic_mode_log_stats(user_exercise_graph, topic_id,
        just_earned_proficiency):
    """Returns a dict of topic mode-specific extra info for stack logs."""
    topic = topic_models.Topic.get_by_id(topic_id)
    topic_exercises = topic.get_exercises()

    total_exercises = len(topic_exercises)
    count_proficient = len(set(ex.name for ex in topic_exercises) &
            set(user_exercise_graph.proficient_exercise_names()))
    just_completed = (just_earned_proficiency and total_exercises ==
            count_proficient)

    return {
        'total_exercises': total_exercises,
        'count_proficient': count_proficient,
        'just_completed': just_completed,
    }

