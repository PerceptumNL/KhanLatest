import badges
import discussion.discussion_models


# All badges that may be awarded once-per-Feedback inherit from FeedbackBadge
class FeedbackBadge(badges.Badge):

    def __init__(self):
        badges.Badge.__init__(self)
        self.badge_context_type = badges.BadgeContextType.FEEDBACK

    def is_manually_awarded(self):
        return True

    @property
    def hide_context(self):
        return True

    def is_already_owned_by(self, user_data, *args, **kwargs):
        feedback = kwargs.get("feedback", None)
        if feedback is None:
            return False

        return (self.name_with_target_context(str(feedback.key().id_or_name()))
                in user_data.badges)

    def award_to(self, user_data, *args, **kwargs):
        feedback = kwargs.get("feedback", None)
        if feedback is None:
            return False

        self.complete_award_to(user_data, feedback,
                str(feedback.key().id_or_name()),
                str(feedback.key().id_or_name()))


class FeedbackVoteCountBadge(FeedbackBadge):

    def is_satisfied_by(self, *args, **kwargs):
        feedback = kwargs.get("feedback", None)
        if feedback is None:
            return False

        if not feedback.is_type(self.required_feedback_type()):
            return False

        # sum_votes starts at 0, but users see additional +1 vote
        # (creator's implicit vote)
        return feedback.sum_votes + 1 >= self.required_votes


class AnswerVoteCountBadge(FeedbackVoteCountBadge):

    def required_feedback_type(self):
        return discussion.discussion_models.FeedbackType.Answer

    def extended_description(self):
        return ("Post an answer that earns %d+ votes" %
                self.required_votes)


class QuestionVoteCountBadge(FeedbackVoteCountBadge):

    def required_feedback_type(self):
        return discussion.discussion_models.FeedbackType.Question

    def extended_description(self):
        return ("Ask a question that earns %d+ votes" %
                self.required_votes)


@badges.active_badge
class LevelOneAnswerVoteCountBadge(AnswerVoteCountBadge):
    def __init__(self):
        AnswerVoteCountBadge.__init__(self)
        self.required_votes = 10
        self.description = "Good Answer"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 0


@badges.active_badge
class LevelTwoAnswerVoteCountBadge(AnswerVoteCountBadge):
    def __init__(self):
        AnswerVoteCountBadge.__init__(self)
        self.required_votes = 25
        self.description = "Great Answer"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0


@badges.active_badge
class LevelThreeAnswerVoteCountBadge(AnswerVoteCountBadge):
    def __init__(self):
        AnswerVoteCountBadge.__init__(self)
        self.required_votes = 50
        self.description = "Incredible Answer"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0


@badges.active_badge
class LevelOneQuestionVoteCountBadge(QuestionVoteCountBadge):
    def __init__(self):
        QuestionVoteCountBadge.__init__(self)
        self.required_votes = 10
        self.description = "Good Question"
        self.badge_category = badges.BadgeCategory.SILVER
        self.points = 0


@badges.active_badge
class LevelTwoQuestionVoteCountBadge(QuestionVoteCountBadge):
    def __init__(self):
        QuestionVoteCountBadge.__init__(self)
        self.required_votes = 25
        self.description = "Great Question"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0


@badges.active_badge
class LevelThreeQuestionVoteCountBadge(QuestionVoteCountBadge):
    def __init__(self):
        QuestionVoteCountBadge.__init__(self)
        self.required_votes = 50
        self.description = "Incredible Question"
        self.badge_category = badges.BadgeCategory.GOLD
        self.points = 0
