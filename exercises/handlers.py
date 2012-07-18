import urllib

from custom_exceptions import MissingExerciseException
import exercise_models
import request_handler
import topic_models
import user_models
import user_util
from exercises.stacks import get_dummy_stack, get_problem_cards, get_review_cards, MAX_CARDS_PER_REVIEW_STACK
from api.jsonify import jsonify
from api.auth.xsrf import ensure_xsrf_cookie

class ViewExerciseDeprecated(request_handler.RequestHandler):
    """ Redirects old exercise URLs (/exercise?exid=monkeys, /exercise/monkeys)
    to their newer form (/earth/forests/e/monkeys).
    """

    @user_util.open_access
    def get(self, exid=None):

        if not exid:
            exid = self.request_string("exid")

        exercise = exercise_models.Exercise.get_by_name(exid)

        if not exercise:
            raise MissingExerciseException("Missing exercise w/ exid '%s'" % exid)

        topic = exercise.first_topic()

        if not topic:
            raise MissingExerciseException("Exercise '%s' is missing a topic" % exid)

        self.redirect("/%s/e/%s?%s" % 
                (topic.get_extended_slug(), urllib.quote(exid), self.request.query_string))

class ViewTopicExerciseDeprecated(request_handler.RequestHandler):
    """ Redirects old topic exercise URLs (/topicexercise/monkeys)
    to their newer form (/earth/forests/e/monkeys).

    TODO: Adding an already-deprecated URL here. We currently have no fast access
    to each topic's extended slug. As soon as this gets cached in topic models
    (https://trello.com/card/topic-models-seriously-need-cached-access-to-their-full-path-urls/4f3f43cd45533a1b3a065a1d/140),
    we'll serialize the full slug when returning topics via our API and switch our knowledge map
    to link to topics appropriately.
    """
    @user_util.open_access
    def get(self, topic_id):

        topic = topic_models.Topic.get_by_id(topic_id)

        if not topic:
            raise MissingExerciseException("Missing topic w/ id '%s'" % topic_id)

        self.redirect("/%s/e?%s" % 
                (topic.get_extended_slug(), self.request.query_string))

class ViewExercise(request_handler.RequestHandler):

    @user_util.open_access
    @ensure_xsrf_cookie
    def get(self, topic_path, exid=None):

        title = None
        description = None
        review_mode = "review" == topic_path

        practice_mode = bool(exid)
        practice_exercise = None

        topic = None
        topic_exercise_badge = None

        user_exercises = None

        if review_mode:

            title = "Review"

        else:

            topic_path_list = topic_path.split('/')
            topic_id = topic_path_list[-1]

            if len(topic_id) > 0:
                topic = topic_models.Topic.get_by_id(topic_id)

            # Topics are required
            if topic:
                title = topic.standalone_title
                topic_exercise_badge = topic.get_exercise_badge()

            if exid:
                practice_exercise = exercise_models.Exercise.get_by_name(exid)

                # Exercises are not required but must be valid if supplied
                if not practice_exercise:
                    raise MissingExerciseException("Missing exercise w/ exid '%s'" % exid)

                title = practice_exercise.display_name
                description = practice_exercise.description

        user_data = user_models.UserData.current() or user_models.UserData.pre_phantom()

        if practice_mode:
            # Practice mode involves a single exercise only
            user_exercises = exercise_models.UserExercise.next_in_practice(user_data, practice_exercise)
        elif review_mode:
            # Review mode sends down up to a certain limit of review exercises
            user_exercises = exercise_models.UserExercise.next_in_review(user_data, n=MAX_CARDS_PER_REVIEW_STACK)
        else:
            # Topics mode context switches between multiple exercises
            user_exercises = exercise_models.UserExercise.next_in_topic(user_data, topic)

        if len(user_exercises) == 0:
            # If something has gone wrong and we didn't get any UserExercises,
            # somebody could've hit the /review URL without any review problems
            # or we hit another issue. Send 'em back to the dashboard for now.
            self.redirect("/exercisedashboard")
            return

        stack = get_dummy_stack(review_mode)
        cards = (get_review_cards(user_exercises) if review_mode else
                get_problem_cards(user_exercises))

        # We have to compute this and save it before JSON-ifiying because it
        # modifies user_exercises, which we JSONify as well.
        problem_history_values = (self.problem_history_values(user_data,
                user_exercises[0]) if practice_mode else {})

        template_values = {
            "title": title,
            "description": description,
            "selected_nav_link": "practice",
            "renderable": True,
            "read_only": False,
            "stack_json": jsonify(stack, camel_cased=True),
            "cards_json": jsonify(cards, camel_cased=True),
            "review_mode_json": jsonify(review_mode, camel_cased=True),
            "practice_mode_json": jsonify(practice_mode, camel_cased=True),
            "topic_json": jsonify(topic, camel_cased=True),
            "topic_exercise_badge_json": jsonify(topic_exercise_badge, camel_cased=True),
            "practice_exercise_json": jsonify(practice_exercise, camel_cased=True),
            "user_data_json": jsonify(user_data, camel_cased=True),
            "user_exercises_json": jsonify(user_exercises, camel_cased=True),
            "show_intro": user_data.is_phantom or user_data.is_pre_phantom,
        }

        # Add disabled browser warnings
        template_values.update(self.browser_support_values())

        # Add history data to template context if we're viewing an old problem
        template_values.update(problem_history_values)

        self.render_jinja2_template("exercises/exercise_template.html", template_values)

    def browser_support_values(self):
        """ Returns a dictionary containing relevant browser support data
        for our interactive exercises
        """

        is_webos = self.is_webos()
        browser_disabled = is_webos or self.is_older_ie()

        return {
            "is_webos": is_webos,
            "browser_disabled": browser_disabled,
        }

    def problem_history_values(self, user_data, user_exercise):
        """ Returns a dictionary containing historical data, if requested, about 
        a particular problem done in user_exercise.
        """

        problem_number = self.request_int('problem_number', default=(user_exercise.total_done + 1))

        user_data_student = self.request_student_user_data() or user_data

        if user_data_student.user_id != user_data.user_id and not user_data_student.is_visible_to(user_data):
            user_data_student = user_data

        viewing_other = user_data_student.user_id != user_data.user_id

        # Can't view your own problems ahead of schedule
        if not viewing_other and problem_number > user_exercise.total_done + 1:
            problem_number = user_exercise.total_done + 1

        # When viewing another student's problem or a problem out-of-order, show read-only view
        read_only = viewing_other or problem_number != (user_exercise.total_done + 1)

        renderable = True

        if read_only:
            # Override current problem number and user being inspected
            # so proper exercise content will be generated
            user_exercise.total_done = problem_number - 1
            user_exercise.user = user_data_student.user
            user_exercise.read_only = True

            if not self.request_bool("renderable", True):
                # We cannot render old problems that were created in the v1 exercise framework.
                renderable = False

            query = exercise_models.ProblemLog.all()
            query.filter("user = ", user_data_student.user)
            query.filter("exercise = ", user_exercise.exercise)

            # adding this ordering to ensure that query is served by an existing index.
            # could be ok if we remove this
            query.order('time_done')
            problem_logs = query.fetch(500)

            problem_log = None
            for p in problem_logs:
                if p.problem_number == problem_number:
                    problem_log = p
                    break

            user_activity = []
            previous_time = 0

            if not problem_log or not hasattr(problem_log, "hint_after_attempt_list"):
                renderable = False
            else:
                # Don't include incomplete information
                problem_log.hint_after_attempt_list = filter(lambda x: x != -1, problem_log.hint_after_attempt_list)

                while len(problem_log.hint_after_attempt_list) and problem_log.hint_after_attempt_list[0] == 0:
                    user_activity.append([
                        "hint-activity",
                        "0",
                        max(0, problem_log.hint_time_taken_list[0] - previous_time)
                        ])

                    previous_time = problem_log.hint_time_taken_list[0]
                    problem_log.hint_after_attempt_list.pop(0)
                    problem_log.hint_time_taken_list.pop(0)

                # For each attempt, add it to the list and then add any hints
                # that came after it
                for i in range(0, len(problem_log.attempts)):
                    user_activity.append([
                        "correct-activity" if problem_log.correct else "incorrect-activity",
                        unicode(problem_log.attempts[i] if problem_log.attempts[i] else 0),
                        max(0, problem_log.time_taken_attempts[i] - previous_time)
                        ])

                    previous_time = 0

                    # Here i is 0-indexed but problems are numbered starting at 1
                    while (len(problem_log.hint_after_attempt_list) and
                            problem_log.hint_after_attempt_list[0] == i + 1):
                        user_activity.append([
                            "hint-activity",
                            "0",
                            max(0, problem_log.hint_time_taken_list[0] - previous_time)
                            ])

                        previous_time = problem_log.hint_time_taken_list[0]
                        # easiest to just pop these instead of maintaining
                        # another index into this list
                        problem_log.hint_after_attempt_list.pop(0)
                        problem_log.hint_time_taken_list.pop(0)

                user_exercise.user_activity = user_activity

                if problem_log.count_hints is not None:
                    user_exercise.count_hints = problem_log.count_hints

                user_exercise.current = problem_log.sha1 == user_exercise.exercise_model.sha1

                url_pattern = "/exercise/%s?student_email=%s&problem_number=%d"
                user_exercise.previous_problem_url = url_pattern % \
                    (user_exercise.exercise, user_data_student.email, problem_number - 1)
                user_exercise.next_problem_url = url_pattern % \
                    (user_exercise.exercise, user_data_student.email, problem_number + 1)

        return {
            "renderable": renderable,
            "read_only": read_only,
        }
