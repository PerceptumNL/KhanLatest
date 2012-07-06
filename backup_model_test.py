import datetime
import time

from third_party.agar.test import BaseTest
from google.appengine.ext import db

import backup_model
from testutil import testsize


class BackupModelTest(BaseTest):
    """Tests for verifying the auto-timestamping of BackupModel.

    Since this relies on a feature deep in GAE's implementation, it's hard
    to mock out the timestamping, so these tests rely on time.sleep() and
    just compares relative times for sanity.
    """

    def tearDown(self):
        super(BackupModelTest, self).tearDown()

    @testsize.medium()
    def test_backup_auto_updates_timestamp(self):
        class Monkey(backup_model.BackupModel):
            pass
        george = Monkey()
        key = george.put()

        retrieved = Monkey.get(key)
        first_timestamp = retrieved.backup_timestamp
        self.assertTrue(first_timestamp is not None)

        # Simulate some time ellapsed.
        time.sleep(1)

        # Another put() should update the timestamp again.
        george.put()
        retrieved = Monkey.get(key)
        second_timestamp = retrieved.backup_timestamp
        self.assertTrue(second_timestamp is not None)
        self.assertTrue(second_timestamp > first_timestamp)

    def test_backup_adds_timestamps_to_existing_models(self):
        # This is just a normal model for now.
        class ExistingModel(db.Model):
            pass
        instance = ExistingModel()
        key = instance.put()

        retrieved = ExistingModel.get(key)
        # We don't expect to have a timestamp, since it's a normal Model.
        self.assertFalse(hasattr(retrieved, 'backup_timestamp'))

        # Pretend the code got updated to have this model inherit BackupModel
        class ExistingModel(backup_model.BackupModel):
            pass

        # Retrieving an existing entity and calling put() should add
        # a timestamp to existing entities.
        retrieved = ExistingModel.get(key)
        self.assertTrue(isinstance(retrieved, backup_model.BackupModel))
        key = retrieved.put()

        retrieved = ExistingModel.get(key)
        self.assertTrue(retrieved.backup_timestamp is not None)

    def test_backup_timestamp_auto_populates(self):
        """
        This is a test to document the behaviour of an auto_now field auto
        populating in App Engine.

        WARNING: since auto_now fields auto-populate, you cannot rely on
        reading a property of an instance to determine the backup_timestamp.
        """

        class Monkey(backup_model.BackupModel):
            pass
        monkey = Monkey()
        
        # Even before this entity is saved to the datastore, GAE will auto
        # populate any date properties with auto_now=True, meaning we can't
        # distinguish whether or not we manually set that property or not!
        # This means models that claimed to have been backed up, might not have
        # actually been backed up!
        first_timestamp = monkey.backup_timestamp
        self.assertTrue(first_timestamp is not None)

    @testsize.medium()
    def test_backup_timestamp_cant_be_written_to(self):
        """
        This is a test to document the behaviour of an auto_now field not
        actually being able to be set in App Engine.
        """

        class Monkey(backup_model.BackupModel):
            name = db.StringProperty()
            
        fixed_timestamp = datetime.datetime.now()
        
        monkey = Monkey()
        monkey.backup_timestamp = fixed_timestamp
        key = monkey.put()

        time.sleep(1)
        
        # Retrieve it again and modify some stuff.
        monkey = Monkey.get(key)
        monkey.name = "george"
        monkey.put()

        monkey = Monkey.get(key)
        retrieved_timestamp = monkey.backup_timestamp
        self.assertNotEquals(fixed_timestamp, retrieved_timestamp)

    @testsize.medium()
    def test_can_filter_by_backup_timestamp(self):
        # This is the real test of BackupModel - can we actually query and
        # filter by the backup_timestamp so that we can do the backup!
        class Monkey(backup_model.BackupModel):
            name = db.StringProperty()
        
        a = Monkey(key_name="a")
        b = Monkey(key_name="b")
        c = Monkey(key_name="c")
        d = Monkey(key_name="d")
        db.put([a, b, c, d])

        # Pretend we do a backup and now we have info on all 4 monkeys
        last_backup_time = datetime.datetime.now()
        
        time.sleep(1)

        # Pretend to update one of the monkeys
        d = Monkey.get_by_key_name("d")
        d.name = "george"
        d.put()
        
        monkeys_to_backup = (Monkey.all().
                             filter("backup_timestamp >", last_backup_time).
                             fetch(100))
        self.assertEquals(1, len(monkeys_to_backup))
        self.assertEquals(d.key(), monkeys_to_backup[0].key())
