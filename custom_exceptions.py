class QuietException(Exception):
    """ QuietExceptions are only logged via logging.info(),
        not as full stack-trace-including exception()s.
    """
    pass


class MissingVideoException(QuietException):
    pass


class MissingExerciseException(Exception):
    pass


class TumblrException(Exception):
    pass


class SmartHistoryLoadException(QuietException):
    pass


class InvalidEmailException(QuietException):
    pass


class PageNotFoundException(QuietException):
    pass


class ClosedBetaException(QuietException):
    pass
