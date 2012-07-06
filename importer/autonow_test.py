from __future__ import absolute_import
from __future__ import with_statement

from datetime import timedelta
import time
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from google.appengine.ext import db
from google.appengine.ext import testbed

from importer.handlers import AutoNowDisabled
from testutil import testsize


class TestModel(db.Model):
    updated_on = db.DateTimeProperty(auto_now=True)


class UpdatedOnTest(unittest.TestCase):
    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()

    def tearDown(self):
        self.testbed.deactivate()

    @testsize.medium()
    def test_auto_now(self):
        t = TestModel()
        dt_before_put = t.updated_on
        t.put()
        dt_after_put = t.updated_on

        # we don't rely on this, but it's useful to know
        self.assertEqual(dt_before_put, dt_after_put)

        t = TestModel.all().get()
        dt_after_read = t.updated_on

        self.assertGreater(dt_after_read, dt_after_put)

        time.sleep(1)
        t.put()
        t = TestModel.all().get()
        dt_after_delayed_put = t.updated_on

        self.assertGreater(dt_after_delayed_put - dt_after_read,
                           timedelta(0, 1, 0))

    @testsize.medium()
    def test_auto_now_disabled(self):
        t = TestModel()
        t.put()
        t = TestModel.all().get()
        dt_after_read = t.updated_on

        time.sleep(1)
        with AutoNowDisabled(TestModel):
            t.put()

        t = TestModel.all().get()
        dt_after_delayed_put = t.updated_on

        self.assertEqual(dt_after_delayed_put, dt_after_read)
