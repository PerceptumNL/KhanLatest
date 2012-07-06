from badges import Badge
from models_badges import CustomBadgeType


class CustomBadge(Badge):

    @staticmethod
    def all():
        return [CustomBadge(badge_type) for badge_type
                in CustomBadgeType.all()]

    def __init__(self, custom_badge_type):
        Badge.__init__(self)
        self.is_hidden_if_unknown = True

        self.name = custom_badge_type.key().name()
        self.description = custom_badge_type.description
        self.full_description = custom_badge_type.full_description
        self.points = custom_badge_type.points
        self.badge_category = custom_badge_type.category
        self.custom_icon_src = custom_badge_type.icon_src

    def is_manually_awarded(self):
        return True

    def extended_description(self):
        return self.full_description

    @property
    def compact_icon_src(self):
        if self.custom_icon_src:
            return self.custom_icon_src
        return super(CustomBadge, self).compact_icon_src

    @property
    def icon_src(self):
        if self.custom_icon_src:
            return self.custom_icon_src
        return super(CustomBadge, self).icon_src
