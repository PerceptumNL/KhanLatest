import copy
import datetime


class MockDatetime(object):
    """ A utility for mocking out the current time.

    Exposes methods typically found in Python's normal datetime library,
    and attempts to be compatible with all API's there so that it
    can be a drop-in for datetime.
    """

    def __init__(self, initial_value_utc=None):
        self.value = initial_value_utc or datetime.datetime.utcfromtimestamp(0)

    def utcnow(self):
        """ Returns a Python datetime.datetime object for the current clock's
        value.

        """
        return copy.copy(self.value)

    def advance(self, delta):
        """ Advances by a datetime.timedelta """
        self.value = self.value + delta

    def advance_days(self, days):
        """ Advances by a specified number of days """
        self.value = self.value + datetime.timedelta(days)
