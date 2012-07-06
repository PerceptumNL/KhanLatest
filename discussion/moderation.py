import discussion_models
import util_discussion


def get_flagged_feedback(feedback_type, offset, sort):
    """Return up to 50 flagged but not deleted feedback entities, starting at
    offset."""
    feedback_query = discussion_models.Feedback.all()
    feedback_query = feedback_query.filter('deleted = ', False)
    feedback_query = feedback_query.filter('types = ', feedback_type)

    if (sort == ModerationSortOrder.LowQualityFirst):
        feedback_query = feedback_query.filter('definitely_not_spam = ',
            False)
    else:
        feedback_query = feedback_query.filter('is_flagged = ', True)

    feedback_query = ModerationSortOrder.order(feedback_query, sort)

    feedbacks = feedback_query.fetch(limit=50, offset=offset)

    return [util_discussion.ClientFeedback.from_feedback(f,
            with_moderation_properties=True) for f in feedbacks]


class ModAction(object):
    """The different actions that a moderator can take on a feedback entity.

    Must be kept in sync with the client's representation in moderation.js.
    """
    CLEAR_FLAGS = 'clearflags'
    CHANGE_TYPE = 'changetype'
    UNDELETE = 'undelete'


class ModerationSortOrder:
    # Keep in sync with constants in moderation.js
    LowQualityFirst = 1  # uses heuristics
    LowestVotesFirst = 2

    @staticmethod
    def order(query, sort_order=-1):
        """Order the results of a query by the specified sort order"""
        if not sort_order in (ModerationSortOrder.LowQualityFirst,
                              ModerationSortOrder.LowestVotesFirst):
            sort_order = ModerationSortOrder.LowQualityFirst

        if sort_order == ModerationSortOrder.LowQualityFirst:
            return query.order('-low_quality_score')
        else:
            return query.order('sum_votes')
