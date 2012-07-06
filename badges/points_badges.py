import badges
import util


# All badges awarded for getting a certain number of points inherit
# from PointBadge
class PointBadge(badges.Badge):

    def is_satisfied_by(self, *args, **kwargs):
        user_data = kwargs.get("user_data", None)
        if user_data is None:
            return False

        return user_data.points >= self.required_points

    def extended_description(self):
        return ("Earn %s energy points" %
                util.thousands_separated_number(self.required_points))


@badges.active_badge
class TenThousandaireBadge(PointBadge):
    def __init__(self):
        PointBadge.__init__(self)
        self.required_points = 10000
        self.description = "Ten to the Fourth"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 0


@badges.active_badge
class HundredThousandaireBadge(PointBadge):
    def __init__(self):
        PointBadge.__init__(self)
        self.required_points = 100000
        self.description = "Ten to the Fifth"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 0


@badges.active_badge
class FiveHundredThousandaireBadge(PointBadge):
    def __init__(self):
        PointBadge.__init__(self)
        self.required_points = 500000
        self.description = "Five Times Ten to the Fifth"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0


@badges.active_badge
class MillionaireBadge(PointBadge):
    def __init__(self):
        PointBadge.__init__(self)
        self.required_points = 1000000
        self.description = "Millionaire"
        self.badge_category = badges.BadgeCategory.PLATINUM
        self.points = 0


@badges.active_badge
class TenMillionaireBadge(PointBadge):
    def __init__(self):
        PointBadge.__init__(self)
        self.required_points = 10000000
        self.description = "Tesla"
        self.badge_category = badges.BadgeCategory.DIAMOND
        self.points = 0
        self.is_teaser_if_unknown = True
