"""Tests fake_datetime.py.

Mostly just makes sure the functions that should return the fake date,
and that other functions return the right type of object.
"""

# Do this first so everyone sees the faked version of datetime.  Also
# to verify that the 'import datetime' below doesn't override our
# fake.
from testutil import fake_datetime
fake_datetime.fake_datetime()

# Verify this gives us the fake datetime.
import datetime
global_now = datetime.datetime.now()

# Now import another module and verify it gets the fake datetime too.
import fake_datetime_test_helper

# Now undo the fake so other tests being run by the test-runner don't
# see the fake datetime.
fake_datetime.unfake_datetime()

import os
import time
try:
    import unittest2 as unittest     # python 2.5
except ImportError:
    import unittest                  # python 2.6+


orig_timezone = None


def setUpModule():
    """All these tests assume we're running in pacific time.  Make it so."""
    global orig_timezone
    orig_timezone = os.environ.get('TZ')
    os.environ['TZ'] = 'America/Los_Angeles'
    time.tzset()


def tearDownModule():
    if orig_timezone:
        os.environ['TZ'] = orig_timezone
    else:
        del os.environ['TZ']


class FakeDateTimeTest(unittest.TestCase):
    def setUp(self):
        global datetime
        datetime = fake_datetime.fake_datetime()

    def tearDown(self):
        global datetime
        datetime = fake_datetime.unfake_datetime()

    def assert_is_fake_now(self, dt, is_utc=False):
        self.assertEqual(dt.year, 2011)
        self.assertEqual(dt.month, 11)
        self.assertEqual(dt.day, 11)
        self.assertEqual(dt.hour, 8 if is_utc else 0)
        # The clock ticks for every call to now(), so we don't know
        # exactly what the minutes or seconds will be, so don't test
        # those.
        self.assertEqual(fake_datetime.DummyDateTimeClass, type(dt))

    def test_now(self):
        self.assert_is_fake_now(datetime.datetime.now())

    def test_now_with_tz(self):
        pass   # TODO(csilvers): figure out how to create a tzinfo

    def test_global_now(self):
        self.assert_is_fake_now(global_now)

    def test_helper_module_now(self):
        self.assert_is_fake_now(fake_datetime_test_helper.global_now)
        self.assert_is_fake_now(fake_datetime_test_helper.now_fn())

    def test_helper_module_now_with_no_local_fake(self):
        """Even if the fake is turned off here, the helper should use it."""
        global datetime
        datetime = fake_datetime.unfake_datetime()
        self.assert_is_fake_now(fake_datetime_test_helper.global_now)
        self.assert_is_fake_now(fake_datetime_test_helper.now_fn())

    def test_utcnow(self):
        self.assert_is_fake_now(datetime.datetime.utcnow(), is_utc=True)

    def test_today(self):
        self.assert_is_fake_now(datetime.datetime.today())

    def test_add(self):
        t = datetime.datetime(2011, 11, 10) + datetime.timedelta(1)
        self.assert_is_fake_now(t)

    def test_radd(self):
        t = datetime.timedelta(1) + datetime.datetime(2011, 11, 10)
        self.assert_is_fake_now(t)

    def test_sub(self):
        t = datetime.datetime(2011, 11, 12) - datetime.timedelta(1)
        self.assert_is_fake_now(t)

    def test_replace(self):
        t = datetime.datetime(1, 1, 1).replace(year=2011, month=11, day=11)
        self.assert_is_fake_now(t)

    def test___init__(self):
        t = datetime.datetime(2011, 11, 11)
        self.assert_is_fake_now(t)

    def test_combine(self):
        t = datetime.datetime.combine(datetime.date(2011, 11, 11),
                                      datetime.time(0, 0, 0))
        self.assert_is_fake_now(t)

    def test_fromordinal(self):
        t = datetime.datetime.fromordinal(734452)
        self.assert_is_fake_now(t)

    def test_fromtimestamp(self):
        t = datetime.datetime.fromtimestamp(1320998400)
        self.assert_is_fake_now(t)

    def test_strptime(self):
        t = datetime.datetime.strptime('2011/11/11 0:0:0', '%Y/%m/%d %H:%M:%S')
        self.assert_is_fake_now(t)

    def test_utcfromtimestamp(self):
        t = datetime.datetime.utcfromtimestamp(1320969600)
        self.assert_is_fake_now(t)

    def test_time(self):
        # The clock ticks for every call to now(), so we don't know
        # exactly what the minutes or seconds will be, so we just
        # test to the closest hour.
        self.assertEqual(1320998400, int(time.time() / 3600) * 3600)

    def test_ctime(self):
        t = time.ctime()
        # The clock ticks for every call to now(), so we don't know
        # exactly what the minutes or seconds will be, so don't test
        # those.
        self.assertTrue(t.startswith('Fri Nov 11 00:'), t)
        self.assertTrue(t.endswith(' 2011'), t)

    def test_ctime_with_arg(self):
        self.assertEqual('Wed Dec 31 16:01:40 1969', time.ctime(100))

    def test_localtime(self):
        # The clock ticks for every call to now(), so we don't know
        # exactly what the minutes or seconds will be, so don't test
        # those.
        t = time.localtime()
        self.assertEqual(2011, t[0])
        self.assertEqual(11, t[1])
        self.assertEqual(11, t[2])
        self.assertEqual(0, t[3])

    def test_localtime_with_arg(self):
        # TODO(csilvers): adjust timezone before running this test.
        self.assertEqual((1970, 1, 1, 19, 46, 40, 3, 1, 0),
                         time.localtime(100000))

    def test_gmtime(self):
        # The clock ticks for every call to now(), so we don't know
        # exactly what the minutes or seconds will be, so don't test
        # those.
        t = time.gmtime()
        self.assertEqual(2011, t[0])
        self.assertEqual(11, t[1])
        self.assertEqual(11, t[2])
        self.assertEqual(8, t[3])

    def test_gmtime_with_arg(self):
        self.assertEqual((1970, 1, 2, 3, 46, 40, 4, 2, 0),
                         time.gmtime(100000))

    def test_ticking(self):
        """Every call to now should increase the time by one."""
        t1 = datetime.datetime.now()
        t2 = datetime.datetime.now()
        t3 = datetime.datetime.now()
        self.assertEqual(datetime.timedelta(seconds=1), t2 - t1)
        self.assertEqual(datetime.timedelta(seconds=2), t3 - t1)


class SettingFakeTimeTest(unittest.TestCase):
    def setUp(self):
        global datetime
        datetime = fake_datetime.fake_datetime(2004, 10, 18, 19, 20, 21)

    def tearDown(self):
        global datetime
        datetime = fake_datetime.unfake_datetime()

    def test_now(self):
        t = datetime.datetime.now()
        self.assertEqual(2004, t.year)
        self.assertEqual(10, t.month)
        self.assertEqual(18, t.day)
        self.assertEqual(19, t.hour)
        self.assertEqual(20, t.minute)
        # Don't test the second since the clock does do some ticking


class UnpatchFakeTest(unittest.TestCase):
    def test_no_fake(self):
        # This test will fail when run exactly on 2011/11/11!
        t = datetime.datetime.now()
        self.assertTrue(t.year != 2011 or t.month != 11 or t.day != 11, t)

        t = time.time()
        self.assertNotEqual(1320998400, int(time.time() / 3600) * 3600)

    def test_unfake(self):
        # This test will fail when run exactly on 2011/11/11!
        datetime = fake_datetime.fake_datetime()
        try:
            t = datetime.datetime.now()
            self.assertTrue(t.year == 2011 and t.month == 11 and t.day == 11,
                            t)

            t = time.time()
            self.assertEqual(1320998400, int(time.time() / 3600) * 3600)
        finally:
            datetime = fake_datetime.unfake_datetime()

        t = datetime.datetime.now()
        self.assertTrue(t.year != 2011 or t.month != 11 or t.day != 11, t)

        t = time.time()
        self.assertNotEqual(1320998400, int(time.time() / 3600) * 3600)
