import badges


# All badges awarded for completing some specific count of exercises
# inherit from ExerciseCompletionCountBadge
class ExerciseCompletionCountBadge(badges.Badge):

    def is_satisfied_by(self, *args, **kwargs):
        user_data = kwargs.get("user_data", None)
        if user_data is None:
            return False

        return (len(user_data.all_proficient_exercises) >=
                self.required_exercises)

    def extended_description(self):
        return "Bekwaamheid in %d vaardigheden" % self.required_exercises


@badges.active_badge
class GettingStartedBadge(ExerciseCompletionCountBadge):
    def __init__(self):
        ExerciseCompletionCountBadge.__init__(self)
        self.required_exercises = 3
        self.description = "Net begonnen"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 100


@badges.active_badge
class MakingProgressBadge(ExerciseCompletionCountBadge):
    def __init__(self):
        ExerciseCompletionCountBadge.__init__(self)
        self.required_exercises = 7
        self.description = "Op dreef"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 1000


@badges.active_badge
class ProductiveBadge(ExerciseCompletionCountBadge):
    def __init__(self):
        ExerciseCompletionCountBadge.__init__(self)
        self.required_exercises = 15
        self.description = "Productief"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 2000


@badges.active_badge
class HardAtWorkBadge(ExerciseCompletionCountBadge):
    def __init__(self):
        ExerciseCompletionCountBadge.__init__(self)
        self.required_exercises = 25
        self.description = "Hard aan het werk"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 6000


@badges.active_badge
class WorkHorseBadge(ExerciseCompletionCountBadge):
    def __init__(self):
        ExerciseCompletionCountBadge.__init__(self)
        self.required_exercises = 50
        self.description = "Werkpaard"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 14000


@badges.active_badge
class MagellanBadge(ExerciseCompletionCountBadge):
    def __init__(self):
        ExerciseCompletionCountBadge.__init__(self)
        self.required_exercises = 100
        self.description = "Ferdinand Magellan"
        self.badge_category = badges.BadgeCategory.PLATINUM
        self.points = 30000


@badges.active_badge
class CopernicusBadge(ExerciseCompletionCountBadge):
    def __init__(self):
        ExerciseCompletionCountBadge.__init__(self)
        self.required_exercises = 200
        self.description = "Nicolaus Copernicus"
        self.badge_category = badges.BadgeCategory.PLATINUM
        self.points = 80000


@badges.active_badge
class KeplerBadge(ExerciseCompletionCountBadge):
    def __init__(self):
        ExerciseCompletionCountBadge.__init__(self)
        self.required_exercises = 300
        self.description = "Kepler"
        self.badge_category = badges.BadgeCategory.PLATINUM
        self.points = 125000


@badges.active_badge
class AtlasBadge(ExerciseCompletionCountBadge):
    def __init__(self):
        ExerciseCompletionCountBadge.__init__(self)
        self.required_exercises = 500
        self.description = "Atlas"
        self.badge_category = badges.BadgeCategory.DIAMOND
        self.points = 200000
        self.is_teaser_if_unknown = True
