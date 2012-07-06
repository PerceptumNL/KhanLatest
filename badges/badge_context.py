class BadgeContextType:
    """The types of contexts in which badges can be earned.

    Attributes:
        NONE: Context-less badges, which means they can only be earned once.
        EXERCISE: Exercise badges (can earn one for every Exercise).
        TOPIC: Topic badges (one for every Topic).
        FEEDBACK: Feedback badges (one for every piece of discussion Feedback).
    """
    NONE = 0
    EXERCISE = 1
    TOPIC = 2
    FEEDBACK = 3
