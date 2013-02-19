import badges


# All badges awarded for consecutively performing activity on the site
# inherit from ConsecutiveActivityBadge
class ConsecutiveActivityBadge(badges.Badge):

    def is_satisfied_by(self, *args, **kwargs):
        user_data = kwargs.get("user_data", None)
        if user_data is None:
            return False

        return (user_data.current_consecutive_activity_days() >=
                self.days_required)

    def extended_description(self):
        return ("Bekijk elke dag (een gedeelte van) een video of maak een oefening gedurende 5 opeenvolgende dagen") % self.days_required


@badges.active_badge
class FiveDayConsecutiveActivityBadge(ConsecutiveActivityBadge):
    def __init__(self):
        ConsecutiveActivityBadge.__init__(self)
        self.days_required = 5
        self.description = "Goede Gewoonten"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 0


@badges.active_badge
class FifteenDayConsecutiveActivityBadge(ConsecutiveActivityBadge):
    def __init__(self):
        ConsecutiveActivityBadge.__init__(self)
        self.days_required = 15
        self.description = "Op rolletjes"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 0


@badges.active_badge
class ThirtyDayConsecutiveActivityBadge(ConsecutiveActivityBadge):
    def __init__(self):
        ConsecutiveActivityBadge.__init__(self)
        self.days_required = 30
        self.description = "Atomic Clockwork"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 0


@badges.active_badge
class HundredDayConsecutiveActivityBadge(ConsecutiveActivityBadge):
    def __init__(self):
        ConsecutiveActivityBadge.__init__(self)
        self.days_required = 100
        self.description = "10,000 Year Clock"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0
