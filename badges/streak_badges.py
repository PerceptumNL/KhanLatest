import badges
from exercise_badges import ExerciseBadge


# All badges awarded for completing a streak of certain length inherit
# from StreakBadge
class StreakBadge(ExerciseBadge):

    def is_satisfied_by(self, *args, **kwargs):
        user_exercise = kwargs.get("user_exercise", None)
        if user_exercise is None:
            return False

        return user_exercise.longest_streak >= self.streak_required

    def extended_description(self):
        return ("Beantwoord %s vragen op rij juist" %
                str(self.streak_required))


@badges.active_badge
class NiceStreakBadge(StreakBadge):
    def __init__(self):
        StreakBadge.__init__(self)
        self.streak_required = 20
        self.description = "Mooie reeks"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 0


@badges.active_badge
class GreatStreakBadge(StreakBadge):
    def __init__(self):
        StreakBadge.__init__(self)
        self.streak_required = 40
        self.description = "Goede reeks"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 0


@badges.active_badge
class AwesomeStreakBadge(StreakBadge):
    def __init__(self):
        StreakBadge.__init__(self)
        self.streak_required = 60
        self.description = "Geweldige reeks"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 0


@badges.active_badge
class RidiculousStreakBadge(StreakBadge):
    def __init__(self):
        StreakBadge.__init__(self)
        self.streak_required = 80
        self.description = "Belachelijke reeks"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 0


@badges.active_badge
class LudicrousStreakBadge(StreakBadge):
    def __init__(self):
        StreakBadge.__init__(self)
        self.streak_required = 100
        self.description = "Bespottelijke reeks"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 0
