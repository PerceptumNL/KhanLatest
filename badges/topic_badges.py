from badges import Badge, BadgeContextType


# All badges that may be awarded once-per-Topic inherit from TopicBadge
class TopicBadge(Badge):

    def __init__(self):
        Badge.__init__(self)
        self.badge_context_type = BadgeContextType.TOPIC

    def is_already_owned_by(self, user_data, *args, **kwargs):
        user_topic = kwargs.get("user_topic", None)
        if user_topic is None:
            return False

        return (self.name_with_target_context(user_topic.title) in
                user_data.badges)

    def award_to(self, user_data, *args, **kwargs):
        user_topic = kwargs.get("user_topic", None)
        if user_topic is None:
            return False

        self.complete_award_to(user_data, None,
                user_topic.title,
                user_topic.title)
