import badges
from badge_triggers import BadgeTriggerType
import discussion.discussion_models


class DiscussionQualityCountBadge(badges.Badge):
    """Badges of the form, "Post 9000 answers that earn 17 or more votes"."""

    def __init__(self):
        badges.Badge.__init__(self)
        self.badge_triggers.add(BadgeTriggerType.VOTEE)

    def is_satisfied_by(self, *args, **kwargs):
        user_data = kwargs.get("user_data", None)
        if user_data is None:
            return False

        user_discussion_stats = kwargs.get("user_discussion_stats", None)
        if user_discussion_stats is None:
            return False

        type_stats = user_discussion_stats.vote_frequencies.get(
            self.required_feedback_type(), {})
        count = sum([freq for votes, freq in type_stats.iteritems()
                     if votes >= self.required_sum_votes])

        return count >= self.required_count


class AnswersQualityCountBadge(DiscussionQualityCountBadge):

    def required_feedback_type(self):
        return discussion.discussion_models.FeedbackType.Answer

    def extended_description(self):
        return ("Post %d answers that earn %d+ votes" %
                (self.required_count, self.required_sum_votes + 1))


class QuestionQualityCountBadge(DiscussionQualityCountBadge):

    def required_feedback_type(self):
        return discussion.discussion_models.FeedbackType.Question

    def extended_description(self):
        return ("Ask %d questions that earn %d+ votes" %
                (self.required_count, self.required_sum_votes + 1))


@badges.active_badge
class LevelOneAnswerQualityCountBadge(AnswersQualityCountBadge):
    def __init__(self):
        AnswersQualityCountBadge.__init__(self)
        self.required_sum_votes = 2
        self.required_count = 10
        self.description = "Guru"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0


@badges.active_badge
class LevelTwoAnswerQualityCountBadge(AnswersQualityCountBadge):
    def __init__(self):
        AnswersQualityCountBadge.__init__(self)
        self.required_sum_votes = 2
        self.required_count = 100
        self.description = "Oracle"
        self.badge_category = badges.BadgeCategory.PLATINUM
        self.points = 0


@badges.active_badge
class LevelOneQuestionQualityCountBadge(QuestionQualityCountBadge):
    def __init__(self):
        QuestionQualityCountBadge.__init__(self)
        self.required_sum_votes = 2
        self.required_count = 10
        self.description = "Investigator"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0


@badges.active_badge
class LevelTwoQuestionQualityCountBadge(QuestionQualityCountBadge):
    def __init__(self):
        QuestionQualityCountBadge.__init__(self)
        self.required_sum_votes = 2
        self.required_count = 100
        self.description = "Detective"
        self.badge_category = badges.BadgeCategory.PLATINUM
        self.points = 0
