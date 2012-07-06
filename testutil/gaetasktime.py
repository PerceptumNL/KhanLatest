"""
Functions for unit testing delayed tasks

Mimics GAE dev server and testbed idiosyncracies for task queue times.
"""
import datetime
import time

from google.appengine.api.taskqueue.taskqueue import _UTC


def utcnow():
    """Timezone aware datetime in UTC"""
    # Implementation derived from API 1.6.2:
    #   google.appengine.api.taskqueue.taskqueue.Task.__determine_eta_posix()
    #   google.appengine.api.taskqueue.taskqueue.Task.eta()
    utcnow = datetime.datetime.utcnow()
    timestamp = time.mktime(utcnow.timetuple()) + utcnow.microsecond * 1e-6
    return datetime.datetime.fromtimestamp(timestamp, _UTC)


def eta(dt):
    """Tasks drop microseconds on their eta"""
    # Implementation derived from API 1.6.2:
    #   google.appengine.api.taskqueue.taskqueue_stub._UsecToSec()
    return dt.replace(microsecond=0)


def eta_utcnow():
    """Datetime for task eta of 'now'"""
    return eta(utcnow())
