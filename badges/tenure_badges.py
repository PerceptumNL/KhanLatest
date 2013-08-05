import badges
import templatefilters
import util


# All badges awarded for completing being a member of the Khan Academy
# for various periods of time from TenureBadge
class TenureBadge(badges.Badge):

    def is_satisfied_by(self, *args, **kwargs):
        user_data = kwargs.get("user_data", None)
        if user_data is None:
            return False

        # Make sure they've been a member for at least X years
        if user_data.joined is None or (util.seconds_since(user_data.joined) <
                                        self.seconds_required):
            return False

        return True

    def extended_description(self):
        return ("Blijf lid van de Iktel voor %s" %
                templatefilters.seconds_to_time_string(self.seconds_required))


@badges.active_badge
class YearOneBadge(TenureBadge):
    def __init__(self):
        TenureBadge.__init__(self)
        self.seconds_required = 60 * 60 * 24 * 365
        self.description = "Eik"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 0


@badges.active_badge
class YearTwoBadge(TenureBadge):
    def __init__(self):
        TenureBadge.__init__(self)
        self.seconds_required = 60 * 60 * 24 * 365 * 2
        self.description = "Beuk"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 0


@badges.active_badge
class YearThreeBadge(TenureBadge):
    def __init__(self):
        TenureBadge.__init__(self)
        self.seconds_required = 60 * 60 * 24 * 365 * 3
        self.description = "Mammoetboom"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0
