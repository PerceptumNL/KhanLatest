"""Used to fake out the time across all services.

Everyone who calls a datetime.datetime method (or time.time) will
receive our fake datetime object back instead, and now() will return a
hard-coded datetime.

This is best imported first, before any other imports, so everyone has
our definition of datetime.  Sadly, we can't use normal
monkey-patching because datetime.datetime is a built-in.  c.f.
   http://stackoverflow.com/questions/4481954/python-trying-to-mock-datetime-date-today-but-not-working
   http://stackoverflow.com/questions/2658026/how-to-change-the-date-time-in-python-for-all-modules

By default, we hard-code in the fake time as midnight, Nov 11, 2011
(local time).  We also code in the fact that time calls are made once
per second -- every call to now() or utcnow() will increase the clock
by one second.

Be careful using this!  We create a fake datetime class, so pickling
won't work as expected, and we affect all datetime calls globally
throughout the program.

To unpatch, call unfake_datetime().

USAGE:
   import fake_datetime
   datetime = fake_datetime.fake_datetime()

   [...]

   datetime = fake_datetime.unfake_datetime()   # if desired

ALTERNATE USAGE:
   import fake_datetime
   fake_datetime.fake_datetime()
   import datetime    # will import the 'fake' datetime as datetime

   [...]

   datetime = fake_datetime.unfake_datetime()   # if desired


SPECIFYING A TIME:
   import fake_datetime
   datetime = fake_datetime.fake_datetime(2011, 11, 5, 13, 56)
   [...]
"""

import datetime as orig_datetime
import sys
import time


orig_time = time.time
orig_ctime = time.ctime
orig_localtime = time.localtime
orig_gmtime = time.gmtime


_DEFAULT_NOW = orig_datetime.datetime(2011, 11, 11)
_NOW = _DEFAULT_NOW
_NUM_NOW_CALLS = 0


class DummyDateTimeClass(orig_datetime.datetime):
    @staticmethod
    def _to_dummydt(dt):
        """Converts a datetime.datetime object to a DummyDateTimeClass."""
        return DummyDateTimeClass(dt.year, dt.month, dt.day,
                                  dt.hour, dt.minute, dt.second,
                                  dt.microsecond, dt.tzinfo)

    @staticmethod
    def _as_dummydt(fn_name, *args, **kwargs):
        """fn_name normally returns a datetime; we make it return an us."""
        fn = getattr(orig_datetime.datetime, fn_name)
        return DummyDateTimeClass._to_dummydt(fn(*args, **kwargs))

    # These methods will use the fake date.

    @staticmethod
    def _fake_now(delta=orig_datetime.timedelta(0)):
        """Every time now() is called, pretend another second has elapsed."""
        global _NUM_NOW_CALLS
        _NUM_NOW_CALLS += 1
        fake_now = (_NOW + orig_datetime.timedelta(seconds=_NUM_NOW_CALLS)
                    + delta)
        # We need to return a DummyDateTimeClass object, not a datetime object.
        return DummyDateTimeClass._to_dummydt(fake_now)

    @staticmethod
    def now(tz=None):
        # This is how tz is interpreted according to
        # http://docs.python.org/library/datetime.html
        if tz:
            return tz.fromutc(DummyDateTimeClass.utcnow().replace(tzinfo=tz))
        return DummyDateTimeClass._fake_now()

    @staticmethod
    def utcnow():
        utc_offset = (orig_datetime.datetime.utcnow() -
                      orig_datetime.datetime.now())
        return DummyDateTimeClass._fake_now(delta=utc_offset)

    @staticmethod
    def today():
        return DummyDateTimeClass.now()

    # These methods don't need to be faked in any way, but do need to
    # be patched to return our fake datetime object rather than a
    # normal datetime object.

    def __add__(*args, **kwargs):
        return DummyDateTimeClass._as_dummydt('__add__', *args, **kwargs)
        
    def __radd__(*args, **kwargs):
        return DummyDateTimeClass._as_dummydt('__radd__', *args, **kwargs)
        
    def __sub__(*args, **kwargs):
        # We only need to patch datetime - delta, which returns a
        # datetime, not dt - dt, which returns a delta.
        if isinstance(args[1], orig_datetime.timedelta):
            return DummyDateTimeClass._as_dummydt('__sub__', *args, **kwargs)
        return orig_datetime.datetime.__sub__(*args, **kwargs)

    def replace(*args, **kwargs):
        return DummyDateTimeClass._as_dummydt('replace', *args, **kwargs)

    # The alternate constructors.

    @staticmethod
    def combine(*args, **kwargs):
        return DummyDateTimeClass._as_dummydt('combine', *args, **kwargs)

    @staticmethod
    def fromordinal(*args, **kwargs):
        return DummyDateTimeClass._as_dummydt('fromordinal', *args, **kwargs)

    @staticmethod
    def fromtimestamp(*args, **kwargs):
        return DummyDateTimeClass._as_dummydt('fromtimestamp', *args, **kwargs)

    @staticmethod
    def strptime(*args, **kwargs):
        return DummyDateTimeClass._as_dummydt('strptime', *args, **kwargs)

    @staticmethod
    def utcfromtimestamp(*args, **kwargs):
        return DummyDateTimeClass._as_dummydt('utcfromtimestamp',
                                              *args, **kwargs)


class DummyDateTimeModule(sys.__class__):
    """Dummy class, for faking datetime module -- we override now()."""
    def __init__(self):
        sys.modules['datetime'] = self

    def __getattr__(self, attr):
        if attr == 'datetime':
            return DummyDateTimeClass
        else:
            return getattr(orig_datetime, attr)


def fake_datetime(*args):
    """args are the same as the constructor args for datetime.datetime."""
    global _NOW, _NUM_NOW_CALLS

    if args:
        _NOW = orig_datetime.datetime(*args)
    else:
        _NOW = _DEFAULT_NOW
    _NUM_NOW_CALLS = 0

    datetime = DummyDateTimeModule()

    # Have to do these outside the class; it doesn't compile inside.
    datetime.datetime.min = DummyDateTimeClass._to_dummydt(
        orig_datetime.datetime.min)

    datetime.datetime.max = DummyDateTimeClass._to_dummydt(
        orig_datetime.datetime.max)

    time.time = lambda: time.mktime(datetime.datetime.now().timetuple())

    # time.ctime(), time.localtime(), and time.gmtime() take an implicit
    # time.time() argument.  Sadly, it's not actually implemented that
    # way, so we need to fix it up so it is.
    time.ctime = lambda *args: apply(orig_ctime, args or (time.time(),))

    time.localtime = lambda *args: apply(orig_localtime,
                                         args or (time.time(),))

    time.gmtime = lambda *args: apply(orig_gmtime, args or (time.time(),))

    return datetime


def unfake_datetime():
    sys.modules['datetime'] = orig_datetime
    time.time = orig_time
    time.ctime = orig_ctime
    time.localtime = orig_localtime
    time.gmtime = orig_gmtime
    return orig_datetime
