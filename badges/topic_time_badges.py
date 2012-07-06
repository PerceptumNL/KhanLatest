import badges
import templatefilters
from topic_badges import TopicBadge


# All badges awarded for watching a specific amount of topic time
# inherit from TopicTimeBadge
class TopicTimeBadge(TopicBadge):

    def __init__(self):
        TopicBadge.__init__(self)

        # Backwards compatibility with old playlist badges requires
        # that the badge name isn't changed (which currently relies on
        # __class__.__name__ not changing)
        self.name = self.name.replace("topictimebadge", "playlisttimebadge")

    def is_satisfied_by(self, *args, **kwargs):
        user_topic = kwargs.get("user_topic", None)

        if user_topic is None:
            return False

        return user_topic.seconds_watched >= self.seconds_required

    def extended_description(self):
        return ("Watch %s of video in a single topic" %
                templatefilters.seconds_to_time_string(self.seconds_required))


@badges.active_badge
class NiceTopicTimeBadge(TopicTimeBadge):
    def __init__(self):
        TopicTimeBadge.__init__(self)
        self.seconds_required = 60 * 15
        self.description = "Nice Listener"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 0


@badges.active_badge
class GreatTopicTimeBadge(TopicTimeBadge):
    def __init__(self):
        TopicTimeBadge.__init__(self)
        self.seconds_required = 60 * 30
        self.description = "Great Listener"
        self.badge_category = badges.BadgeCategory.BRONZE
        self.points = 0


@badges.active_badge
class AwesomeTopicTimeBadge(TopicTimeBadge):
    def __init__(self):
        TopicTimeBadge.__init__(self)
        self.seconds_required = 60 * 60
        self.description = "Awesome Listener"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 0


@badges.active_badge
class RidiculousTopicTimeBadge(TopicTimeBadge):
    def __init__(self):
        TopicTimeBadge.__init__(self)
        self.seconds_required = 60 * 60 * 4
        self.description = "Ridiculous Listener"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0


@badges.active_badge
class LudicrousTopicTimeBadge(TopicTimeBadge):
    def __init__(self):
        TopicTimeBadge.__init__(self)
        self.seconds_required = 60 * 60 * 10
        self.description = "Ludicrous Listener"
        self.badge_category = badges.BadgeCategory.PLATINUM
        self.points = 0
