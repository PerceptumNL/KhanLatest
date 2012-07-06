"""Helper module used by fake_datetime_test.py.

One of the things we want to test in fake_datetime_test is that when
you use the fake datetime and import other modules, they see the fake
datetime too, even if they don't do anything special.  Here's where we
test that.
"""

# It's important we don't import anything else, because we don't want
# to accidentally pollute system modules with the fake datetime.
import datetime

global_now = datetime.datetime.now()


def now_fn():
    return datetime.datetime.now()
