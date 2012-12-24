import badges
from exercise_badges import ExerciseBadge


# All badges awarded for completing a certain number of correct problems
# within a specific amount of time inherit from TimedProblemBadge
class TimedProblemBadge(ExerciseBadge):

    def is_satisfied_by(self, *args, **kwargs):
        user_exercise = kwargs.get("user_exercise", None)
        action_cache = kwargs.get("action_cache", None)

        if user_exercise is None or action_cache is None:
            return False

        c_logs = len(action_cache.problem_logs)
        if c_logs >= self.problems_required:

            time_taken = 0
            time_allotted = (self.problems_required *
                             user_exercise.seconds_per_fast_problem)

            for i in range(self.problems_required):

                problem = action_cache.get_problem_log(c_logs - i - 1)
                time_taken += problem.time_taken

                if (time_taken > time_allotted or
                        not problem.correct or
                        problem.exercise != user_exercise.exercise):
                    return False

            return time_taken <= time_allotted

        return False

    def extended_description(self):
        return ("Beantwoord snel & correct %s vaardigheden problemen achter elkaar "
                "(tijdslimiet hangt af van de moeilijkheidsgraad)" %
                str(self.problems_required))


@badges.active_badge
class NiceTimedProblemBadge(TimedProblemBadge):

    def __init__(self):
        TimedProblemBadge.__init__(self)
        self.problems_required = 5
        self.description = "De vaart erin"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 100


@badges.active_badge
class GreatTimedProblemBadge(TimedProblemBadge):

    def __init__(self):
        TimedProblemBadge.__init__(self)
        self.problems_required = 10
        self.description = "Going Transonic"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 500


@badges.active_badge
class AwesomeTimedProblemBadge(TimedProblemBadge):

    def __init__(self):
        TimedProblemBadge.__init__(self)
        self.problems_required = 20
        self.description = "Going Supersonic"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 750


@badges.active_badge
class RidiculousTimedProblemBadge(TimedProblemBadge):

    def __init__(self):
        TimedProblemBadge.__init__(self)
        self.problems_required = 42
        self.description = "Sub-light Speed"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 1500


@badges.active_badge
class LudicrousTimedProblemBadge(TimedProblemBadge):

    def __init__(self):
        TimedProblemBadge.__init__(self)
        self.problems_required = 75
        self.description = "299,792,458 meter per seconde"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 5000
