"""
Annotations for unittest resource requirements

Decorate unit tests to indicate the difference between small, fast
tests and big, slow tests. Test runners will skip sizes that are not
allowed to run. By default, all test sizes run.

Test sizing guide:

 - Small tests run in less than one second
 - Medium tests run in less than one minute
 - Large tests run in one minute or more or use external resources such
   as a database, an actual network connection, and so on.
"""

import logging

try:
    import unittest2 as unittest
except ImportError:
    import unittest

_VALID_SIZES = set(['small', 'medium', 'large'])

_MAX_SIZE = 'large'
"""Tests of this size and smaller may run"""


def set_max_size(size):
    """The largest test size that may run ("small", "medium", "large")"""
    if size in _VALID_SIZES:
        global _MAX_SIZE
        _MAX_SIZE = size
    else:
        logging.warn('ignoring invalid test size "%s"' % size)


def small():
    """Skip unless small sized tests may run"""
    # small tests alway run
    return lambda func: func


def medium():
    """Skip unless medium sized tests may run"""
    if _MAX_SIZE in ('medium', 'large'):
        return lambda func: func
    return unittest.skip("skipping medium tests")


def large():
    """Skip unless large sized tests may run"""
    if _MAX_SIZE == 'large':
        return lambda func: func
    return unittest.skip("skipping large tests")
