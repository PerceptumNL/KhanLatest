# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

import badges
import exercise_models


# All badges awarded for completing some subset of exercises inherit from
# ExerciseCompletionBadge
class ExerciseCompletionBadge(badges.Badge):

    def __init__(self):
        super(ExerciseCompletionBadge, self).__init__()
        self.is_goal = True

    def is_satisfied_by(self, *args, **kwargs):
        user_data = kwargs.get("user_data", None)
        if user_data is None:
            return False

        if len(self.exercise_names_required) <= 0:
            return False

        for exercise_name in self.exercise_names_required:
            if not user_data.is_proficient_at(exercise_name):
                return False

        return True

    def goal_objectives(self):
        if self.exercise_names_required:
            return json.dumps(self.exercise_names_required)
        return json.dumps([])

    def extended_description(self):
        badges = []
        total_len = 0

        for exercise_name in self.exercise_names_required:
            long_name = exercise_models.Exercise.to_display_name(
                exercise_name)
            short_name = exercise_models.Exercise.to_short_name(exercise_name)

            display_name = long_name if (total_len < 80) else short_name

            badges.append(display_name)
            total_len += len(display_name)

        s_exercises = ", ".join(badges)

        return "Bereik bekwaamheid in %s" % s_exercises


class ChallengeCompletionBadge(ExerciseCompletionBadge):

    def __init__(self):
        super(ChallengeCompletionBadge, self).__init__()
        self.is_goal = False

    def extended_description(self):
        s_exercises = ""
        for exercise_name in self.exercise_names_required:
            if len(s_exercises) > 0:
                s_exercises += ", "
            s_exercises += exercise_models.Exercise.to_display_name(
                exercise_name)
        return "Maak de %s" % s_exercises

    @property
    def compact_icon_src(self):
        return self.icon_src


@badges.active_badge
class LevelOneArithmeticianBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'addition_1', 'subtraction_1', 'multiplication_1', 'division_1']
        self.description = "Pupil rekenaar"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 100


@badges.active_badge
class LevelTwoArithmeticianBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'addition_4', 'subtraction_4', 'multiplication_4', 'division_4']
        self.description = "Ontwikkelde rekenaar"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 500


@badges.active_badge
class LevelThreeArithmeticianBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'multiplying_decimals', 'dividing_decimals',
            'multiplying_fractions', 'dividing_fractions']
        self.description = "Gevorderde rekenaar"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 750


@badges.active_badge
class TopLevelArithmeticianBadge(badges.RetiredBadge,
                                 ChallengeCompletionBadge):
    def __init__(self):
        ChallengeCompletionBadge.__init__(self)
        self.exercise_names_required = ['arithmetic_challenge']
        self.description = "Meester rekenaar"
        self.badge_category = badges.BadgeCategory.MASTER
        self.points = 10000

    @property
    def icon_src(self):
        return "/images/badges/Arithmetic.png"


@badges.active_badge
class LevelOneTrigonometricianBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'angles_2', 'distance_formula', 'pythagorean_theorem_1']
        self.description = "pupil in trigoniometrie"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 100


@badges.active_badge
class LevelTwoTrigonometricianBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'pythagorean_theorem_2', 'trigonometry_1']
        self.description = "Ontwikkeld in trigoniometrie"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 500


@badges.active_badge
class LevelThreeTrigonometricianBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'trigonometry_2', 'graphs_of_sine_and_cosine',
            'inverse_trig_functions', 'trig_identities_1']
        self.description = "Gevorderd in trigoniometrie"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 750


@badges.active_badge
class TopLevelTrigonometricianBadge(badges.RetiredBadge,
                                    ChallengeCompletionBadge):
    def __init__(self):
        ChallengeCompletionBadge.__init__(self)
        self.exercise_names_required = ['trigonometry_challenge']
        self.description = "Meester in trigoniometrie"
        self.badge_category = badges.BadgeCategory.MASTER
        self.points = 10000

    @property
    def icon_src(self):
        return "/images/badges/Geometry-Trig.png"


@badges.active_badge
class LevelOnePrealgebraistBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'exponents_1', 'adding_and_subtracting_negative_numbers',
            'adding_and_subtracting_fractions']
        self.description = "Apprentice Pre-algebraist"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 100


@badges.active_badge
class LevelTwoPrealgebraistBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'exponents_2', 'multiplying_and_dividing_negative_numbers',
            'multiplying_fractions', 'dividing_fractions']
        self.description = "Journeyman Pre-algebraist"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 500


@badges.active_badge
class LevelThreePrealgebraistBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'exponents_3', 'order_of_operations', 'ordering_numbers',
            'scientific_notation', 'units', 'simplifying_radicals']
        self.description = "Artisan Pre-algebraist"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 750


@badges.active_badge
class TopLevelPrealgebraistBadge(badges.RetiredBadge,
                                 ChallengeCompletionBadge):
    def __init__(self):
        ChallengeCompletionBadge.__init__(self)
        self.exercise_names_required = ['pre-algebra_challenge']
        self.description = "Master of Pre-algebra"
        self.badge_category = badges.BadgeCategory.MASTER
        self.points = 10000

    @property
    def icon_src(self):
        return "/images/badges/Pre-Algebra.png"


@badges.active_badge
class LevelOneAlgebraistBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'exponents_3', 'exponent_rules', 'logarithms_1',
            'linear_equations_1', 'percentage_word_problems_1', 'functions_1']
        self.description = "Apprentice Algebraist"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 100


@badges.active_badge
class LevelTwoAlgebraistBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'linear_equations_2', 'percentage_word_problems_2',
            'functions_2', 'domain_of_a_function', 'even_and_odd_functions',
            'shifting_and_reflecting_functions']
        self.description = "Journeyman Algebraist"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 500


@badges.active_badge
class LevelThreeAlgebraistBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'linear_equations_3', 'systems_of_equations',
            'multiplying_expressions_1', 'even_and_odd_functions',
            'inverses_of_functions', 'slope_of_a_line', 'midpoint_formula',
            'line_relationships', 'functions_3']
        self.description = "Artisan I Algebraist"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 750


@badges.active_badge
class LevelFourAlgebraistBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'linear_equations_4', 'linear_inequalities',
            'average_word_problems', 'equation_of_a_line',
            'solving_quadratics_by_factoring', 'quadratic_equation',
            'solving_for_a_variable', 'expressions_with_unknown_variables']
        self.description = "Artisan II Algebraist"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 1000


@badges.active_badge
class LevelFiveAlgebraistBadge(ExerciseCompletionBadge):
    def __init__(self):
        ExerciseCompletionBadge.__init__(self)
        self.exercise_names_required = [
            'new_definitions_1', 'new_definitions_2',
            'expressions_with_unknown_variables_2',
            'absolute_value_equations', 'radical_equations',
            'rate_problems_1']
        self.description = "Artisan III Algebraist"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 1000


@badges.active_badge
class TopLevelAlgebraistBadge(badges.RetiredBadge, ChallengeCompletionBadge):
    def __init__(self):
        ChallengeCompletionBadge.__init__(self)
        self.exercise_names_required = ['algebra_challenge']
        self.description = "Master of Algebra"
        self.badge_category = badges.BadgeCategory.MASTER
        self.points = 10000

    @property
    def icon_src(self):
        return "/images/badges/Algebra.png"
