from auth.age_util import get_age
import datetime
try:
    import unittest2 as unittest
except ImportError:
    import unittest


class AgeTest(unittest.TestCase):

    def age(self, bday, today):
        """ shorthand for calling get_age with strings. """
        def d(s):
            return datetime.datetime.strptime(s, "%Y-%m-%d").date()

        return get_age(d(bday), today=d(today))

    def test_get_age(self):
        self.assertEqual(9, self.age(bday="2000-01-02",    # Jan 2
                                     today="2010-01-01"))  # Jan 1

        self.assertEqual(10, self.age(bday="2000-01-02",    # Jan 2
                                      today="2010-01-02"))  # Jan 2

    def test_get_age_on_leap_year(self):
        self.assertEqual(4, self.age(bday="2004-02-29",    # Leap day
                                     today="2008-02-29"))  # Leap day

        self.assertEqual(4, self.age(bday="2004-02-28",    # Feb 28
                                     today="2008-02-29"))  # Leap day

        self.assertEqual(3, self.age(bday="2004-03-01",    # Mar 1
                                     today="2008-02-29"))  # Leap day

    def test_get_age_bday_is_leap(self):
        self.assertEqual(4, self.age(bday="2004-02-29",    # Leap day
                                     today="2009-02-28"))  # Feb 28

        self.assertEqual(5, self.age(bday="2004-02-29",    # Leap day
                                     today="2009-03-01"))  # Mar 1

        self.assertEqual(4, self.age(bday="2004-02-29",    # Leap day
                                     today="2009-02-28"))  # Feb 28
