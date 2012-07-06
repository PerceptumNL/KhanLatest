from testutil import fake_user
from testutil import gae_model
import util_profile


class UserProfileTest(gae_model.GAEModelTestCase):

    def test_user_profile_is_visible_to_self(self):
        user = fake_user.private_user("user", "user@gmail.com")
        profile = util_profile.UserProfile.from_user(user, user)
        # Everything is visible to self.
        self.assertEqual(profile.is_activity_accessible, True)

    def test_user_profile_is_visible_to_coach(self):
        user = fake_user.private_user("user", "user@gmail.com")
        coach = fake_user.private_user("coach", "coach@gmail.com")
        user.add_coach(coach)
        profile = util_profile.UserProfile.from_user(user, coach)
        # Everything is visible to the coach.
        self.assertEqual(profile.is_activity_accessible, True)

    def test_public_user_profile_is_visible_to_actor(self):
        user = fake_user.public_user(1, "user@gmail.com", "user")
        actor = fake_user.private_user("actor", "actor@gmail.com")
        profile = util_profile.UserProfile.from_user(user, actor)
        # Except activity, everything else is visible to actor for
        # a public user.
        self.assertEqual(profile.is_activity_accessible, False)

    def test_private_user_profile_is_visible_to_actor(self):
        user = fake_user.private_user("user", "user@gmail.com")
        actor = fake_user.private_user("actor", "actor@gmail.com")
        profile = util_profile.UserProfile.from_user(user, actor)
        # Private user profile is visible only partially to the actor.
        self.assertEquals(profile.is_activity_accessible, False)
