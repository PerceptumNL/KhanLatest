class BadgeTriggerType:
    """Actions in response to which a badge might be earned, stored in a
    badge's badge_triggers property.

    Attributes:

        VOTEE: For badges that can be earned (by the feedback author) by having
        a feedback item that gets voted on.
        When using update_with_triggers, include user_data (of the author) and
        user_discussion_stats.

        POST: For badges that can be earned (by the author) by posting a
        feedback item.
        When using update_with_triggers, include user_data and feedback.
    """
    VOTEE = 0
    POST = 1
