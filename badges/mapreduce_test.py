"""Test the badges mapreduce.

We do this by stubbing out lots of stuff, calling the same mapreduce
code that util_badges.StartNewBadgeMapReduce calls, on the test-db,
and then checking that the test-db was updated appropriately.
"""

# Ugh, we can't do 'from badges import models_badges'/'util_badges'
# because badges/badges.py confuses the import system.  We have to do
# a relative import, relying on the fact we're in the same dir as
# util_badges.
import models_badges
import util_badges
from exercises import exercise_util
import exercise_models
from testutil import mapreduce_stub
import user_models


class BadgesMapreduceTestCase(mapreduce_stub.MapreduceTestCase):
    def setUp(self):
        super(BadgesMapreduceTestCase, self).setUp(use_test_db=True)

    def test_new_badge_mapreduce(self):
        # Setting up the data is a bit complicated.  First, we have to
        # have a user do 5 correct exercises in a row, to earn the
        # easiest streak-badge.  But we have to do it in a way that
        # the code doesn't award the badge right away.  Then we can
        # run the mapreduce, which should award the badge then.  To do
        # this, we stub out the call that would normally award the
        # badge right away.
        orig_update_fn = util_badges.update_with_user_exercise
        try:
            util_badges.update_with_user_exercise = lambda *args, **kw: None
            new_user = user_models.UserData.insert_for('badgeuser',
                                                       'bu@example.com')
            exercise = exercise_models.Exercise.get_by_name('exponent_rules')
            user_exercise = new_user.get_or_insert_exercise(exercise)
            for i in xrange(1, 10):    # 5 is enough, but we'll do 10
                exercise_util.attempt_problem(new_user, user_exercise,
                                              i, 1, "firsttry", "sha1", "seed",
                                              True, 0, 3, False, False,
                                              "obsolete", "127.0.0.1", {},
                                              "TEST", "TEST", 1, 7,
                                              async_problem_log_put=False,
                                              async_stack_log_put=False)
        finally:
            util_badges.update_with_user_exercise = orig_update_fn

        # The badges info should be empty.
        b = models_badges.UserBadge.all().filter('user =', new_user.user).get()
        self.assertEqual(None, b)

        util_badges.start_new_badge_mapreduce()   # runs control.start_map()
        mapreduce_stub.run_all_mapreduces(self.testbed)

        # Now, the badges info should no longer be empty!
        b = models_badges.UserBadge.all().filter('user =', new_user.user).get()
        self.assertNotEqual(None, b)
