import os
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from google.appengine.ext import testbed
from google.appengine.datastore import datastore_stub_util

import request_cache as instance_cache
from testutil import rootdir


def _copy_to_fd(infile, out_fd, length=(64 * 1024)):
    """Copy infile into out_fd, using buffering to reduce memory cost."""
    while True:
        buf = infile.read(length)
        if not buf:
            break
        os.write(out_fd, buf)


class GAEModelTestCase(unittest.TestCase):
    """A test case that stubs out much appengine functionality.

    When a test inherits from GAEModelTestCase, it can make appengine
    calls in a way that's easy to test.  The calls still work as
    normal: db calls will still store stuff in a database, taskqueue
    calls will still run, but there's a bit more manual control
    allowed, and you can peek at the internals to make sure everything
    is working as you expect.

    While this class provides some defaults for these knobs, most
    tests will probably want to subclass setUp and call the superclass
    (our) setUp with appropriate flags.
    """
    def setUp(self,
              db_consistency_probability=0,
              use_test_db=False,
              test_db_filename='testutil/test_db.sqlite',
              queue_yaml_dir='.',
              app_id='dev~khan-academy'):
        """Initialize a testbed for appengine, and also initialize the cache.

        This sets up the backend state (databases, queues, etc) to a known,
        pure state before each test.

        Arguments:
          db_consistency_probability: a number between 0 and 1
              indicating the percent of times db writes are
              immediately visible.  If set to 1, then the database
              seems consistent.  If set to 0, then writes are never
              visible until a commit-causing command is run:
              get()/put()/delete()/ancestor queries.  0 is the
              default, and does the best testing that the code does
              not make assumptions about immediate consistency.  See
                https://developers.google.com/appengine/docs/python/datastore/overview#Datastore_Writes_and_Data_Visibility
              for details on GAE's consistency policies with the High
              Replication Datastore (HRD).

          use_test_db: if True, then initialize the datastore with the
              contents of testutil/test_db.sqlite, rather than being
              empty.  This routine makes a copy of the db file (in /tmp)
              so changes from one test won't affect another.

          test_db_filename: the file to use with use_test_db, relative
              to the project root (that is, the directory with
              app.yaml in it).  It is ignored if use_test_db is False.
              It is unusual to want to change this value from the
              default, but it can be done if you have another test-db
              in a non-standard location.

          queue_yaml_dir: the directory where queue.yaml lives, relative
              to the project root.  If set, we will initialize the
              taskqueue stub.  This is needed if you wish to run
              mapreduces in your test.  This will almost always be '.'.

          app_id: what we should pretend our app-id is.  The default
              matches the app-id used to make test_db.sqlite, so
              database lookups on that file will succeed.
        """
        self.testbed = testbed.Testbed()
        # This lets us use testutil's test_db.sqlite if we want to.
        self.testbed.setup_env(app_id=app_id)
        self.testbed.activate()

        # Create a consistency policy that will simulate the High
        # Replication consistency model.
        self.policy = datastore_stub_util.PseudoRandomHRConsistencyPolicy(
            probability=db_consistency_probability)
        if use_test_db:
            root = rootdir.project_rootdir()
            (fd, self.datastore_filename) = tempfile.mkstemp(prefix='test_db_',
                                                             suffix='.sqlite')
            _copy_to_fd(open(os.path.join(root, test_db_filename)), fd)
            os.close(fd)
        else:
            self.datastore_filename = None

        self.testbed.init_datastore_v3_stub(
            consistency_policy=self.policy,
            datastore_file=self.datastore_filename,
            use_sqlite=(self.datastore_filename is not None))

        self.testbed.init_user_stub()

        self.testbed.init_memcache_stub()

        if queue_yaml_dir:
            root = rootdir.project_rootdir()
            self.testbed.init_taskqueue_stub(
                root_path=os.path.join(root, queue_yaml_dir),
                auto_task_running=True)

        instance_cache.flush()

    def tearDown(self):
        self.testbed.deactivate()
        if self.datastore_filename:
            os.unlink(self.datastore_filename)

    def _truncate_value(self, a):
        max_length = 100
        str_a = str(a)
        if len(str_a) <= max_length:
            return str_a
        else:
            return "%s(%i): '%s...%s'" % (
                a.__class__.__name__, 
                len(a), 
                str_a[:max_length / 2], 
                str_a[-max_length / 2:])

    def assertEqualTruncateError(self, a, b):
        assert a == b, "%s != %s" % (self._truncate_value(a), 
                                     self._truncate_value(b))
