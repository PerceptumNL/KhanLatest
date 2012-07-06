from __future__ import with_statement
import datetime
import mock

from google.appengine.ext import db

import custom_exceptions
import coaches
import exercise_models
import phantom_users.phantom_util
from testutil import gae_model
from testutil import mock_datetime
from coach_resources.coach_request_model import CoachRequest
from user_models import Capabilities, UserData, UniqueUsername, ParentChildPair
from user_models import _USER_KEY_PREFIX
from testutil import testsize
import setting_model

class UserDataCoachTest(gae_model.GAEModelTestCase):
    def setUp(self):
        super(UserDataCoachTest, self).setUp(db_consistency_probability=1)

    def make_user(self, email):
        return UserData.insert_for(email, email)

    def make_user_json(self, user, is_coaching):
        return {
            'email': user.key_email,
            'isCoachingLoggedInUser': is_coaching,
        }

    def test_add_a_coach(self):
        student = self.make_user('student@gmail.com')
        coach = self.make_user('coach@gmail.com')

        coaches_json = [self.make_user_json(coach, True)]
        coaches.update_coaches(student, coaches_json)

        self.assertEqual(1, len(student.coaches))
        self.assertTrue(student.is_visible_to(coach))
        self.assertTrue(coach.has_students())

    def test_add_multiple_coaches(self):
        bella = self.make_user('bella@gmail.com')
        jacob = self.make_user('jacob@gmail.com')
        edward = self.make_user('edward@gmail.com')

        coaches_json = [self.make_user_json(coach, True) for coach in
                [jacob, edward]]
        coaches.update_coaches(bella, coaches_json)

        self.assertEqual(2, len(bella.coaches))

        self.assertTrue(bella.is_visible_to(jacob))
        self.assertTrue(jacob.has_students())

        self.assertTrue(bella.is_visible_to(edward))
        self.assertTrue(edward.has_students())

    def test_remove_coach(self):
        bella = self.make_user('bella@gmail.com')
        jacob = self.make_user('jacob@gmail.com')

        jacob_json = [self.make_user_json(jacob, True)]
        coaches.update_coaches(bella, jacob_json)
        coaches.update_coaches(bella, [])

        self.assertEqual(0, len(bella.coaches))
        self.assertFalse(bella.is_visible_to(jacob))
        self.assertFalse(jacob.has_students())

    def test_return_no_requester_emails_on_update_coaches_when_coaching_logged_in_user(self):
        bella = self.make_user('bella@gmail.com')
        jacob = self.make_user('jacob@gmail.com')

        jacob_json = [self.make_user_json(jacob, True)]
        requester_emails = coaches.update_coaches(bella, jacob_json)

        self.assertEqual([], requester_emails)

    def test_return_requester_email_on_update_coaches_when_not_coaching_logged_in_user(self):
        bella = self.make_user('bella@gmail.com')
        jacob = self.make_user('jacob@gmail.com')

        jacob_json = [self.make_user_json(jacob, False)]
        requester_emails = coaches.update_coaches(bella, jacob_json)

        self.assertEqual([jacob.key_email], requester_emails)

    def test_raises_exception_on_add_nonexistent_coach(self):
        bella = self.make_user('bella@gmail.com')
        coaches_json = [{
            'email': 'legolas@gmail.com',
            'isCoachingLoggedInUser': True,
        }]
        self.assertRaises(custom_exceptions.InvalidEmailException,
            coaches.update_coaches,
            bella,
            coaches_json)

    def test_noop_on_update_requests_with_email(self):
        bella = self.make_user('bella@gmail.com')
        jacob = self.make_user('jacob@gmail.com')

        CoachRequest.get_or_insert_for(jacob, bella, 'bella@gmail.com')

        coaches.update_requests(bella, [jacob.key_email])

        requests_for_bella = CoachRequest.get_for_student(bella).fetch(1000)
        self.assertEqual(1, len(requests_for_bella))

        requests_by_jacob = CoachRequest.get_for_coach(jacob).fetch(1000)
        self.assertEqual(1, len(requests_by_jacob))

    def test_requesting_by_username_doesnt_leak_email(self):
        bella = self.make_user('bella@gmail.com')
        self.assertTrue(bella.claim_username('bella'))
        jacob = self.make_user('jacob@gmail.com')

        # Request is made using username.
        CoachRequest.get_or_insert_for(jacob, bella, 'bella')

        requests_for_bella = CoachRequest.get_for_student(bella).fetch(1000)
        self.assertEqual(1, len(requests_for_bella))
        self.assertEqual(bella.username,
                         requests_for_bella[0].student_requested_identifier)

        requests_by_jacob = CoachRequest.get_for_coach(jacob).fetch(1000)
        self.assertEqual(1, len(requests_by_jacob))
        self.assertEqual(bella.username,
                         requests_by_jacob[0].student_requested_identifier)

    def test_clear_request_on_update_requests_with_no_email(self):
        bella = self.make_user('bella@gmail.com')
        edward = self.make_user('edward@gmail.com')
        CoachRequest.get_or_insert_for(edward, bella, 'bella@gmail.com')

        coaches.update_requests(bella, [])

        requests_for_bella = CoachRequest.get_for_student(bella).fetch(1000)
        self.assertEqual(0, len(requests_for_bella))

        requests_by_edward = CoachRequest.get_for_coach(edward).fetch(1000)
        self.assertEqual(0, len(requests_by_edward))

    def test_noop_on_update_when_not_coaching_logged_in_user(self):
        # Bella + Edward's daughter,
        # (Spoiler Alert!) who Jacob falls in love with in Book 4
        renesmee = self.make_user('renesmee@gmail.com')
        jacob = self.make_user('jacob@gmail.com')
        CoachRequest.get_or_insert_for(jacob, renesmee, 'renesmee@gmail.com')
        requests_for_renesmee = CoachRequest.get_for_student(renesmee).fetch(1000)
        self.assertEqual(1, len(requests_for_renesmee))

        coaches_json = [self.make_user_json(jacob, False)]
        coaches.update_coaches_and_requests(renesmee, coaches_json)

        self.assertFalse(renesmee.is_visible_to(jacob))
        requests_for_renesmee = CoachRequest.get_for_student(renesmee).fetch(1000)
        self.assertEqual(1, len(requests_for_renesmee))

    def test_accept_request_on_update_when_coaching_logged_in_user(self):
        renesmee = self.make_user('renesmee@gmail.com')
        jacob = self.make_user('jacob@gmail.com')
        CoachRequest.get_or_insert_for(jacob, renesmee, 'renesmee@gmail.com')

        coaches_json = [self.make_user_json(jacob, True)]
        coaches.update_coaches_and_requests(renesmee, coaches_json)

        self.assertTrue(renesmee.is_visible_to(jacob))
        requests_for_renesmee = CoachRequest.get_for_student(renesmee).fetch(1000)
        self.assertEqual(0, len(requests_for_renesmee))

    def test_ignore_nonexistent_requester_email_on_update_requests(self):
        renesmee = self.make_user('renesmee@gmail.com')
        jacob = self.make_user('jacob@gmail.com')
        CoachRequest.get_or_insert_for(jacob, renesmee, 'renesmee@gmail.com')

        coaches_json = [{
            'email': 'legolas@gmail.com',
            'isCoachingLoggedInUser': False,
        }]
        coaches.update_requests(renesmee, coaches_json)
        requests_for_renesmee = CoachRequest.get_for_student(renesmee).fetch(1000)
        self.assertEqual(0, len(requests_for_renesmee))


class UsernameTest(gae_model.GAEModelTestCase):
    def tearDown(self):
        # Clear all usernames just to be safe
        for u in UniqueUsername.all():
            u.delete()
        super(UsernameTest, self).tearDown()

    def validate(self, username):
        return UniqueUsername.is_valid_username(username)

    def test_user_name_validates_length_requirement(self):
        # This test verifies that the multiple places that verify a username's
        # length are in sync.
        for i in range(10):
            candidate = 'a' * i
            self.assertEquals(
                    not UniqueUsername.is_username_too_short(candidate),
                    self.validate(candidate))

    def test_user_name_fuzzy_match(self):
        """ Tests user name search can ignore periods properly. """
        def k(n):
            return UniqueUsername.build_key_name(n)

        self.assertEqual(k('mr.pants'), k('mrpants'))
        self.assertEqual(k('mr.pants...'), k('mrpants'))
        self.assertEqual(k('mrpants'), k('mrpants'))
        self.assertEqual(k('MrPants'), k('mrpants'))

    def test_bad_user_name_fails_validation(self):
        self.assertFalse(self.validate(''))
        self.assertFalse(self.validate('a'))  # Too short
        self.assertFalse(self.validate('4score7yrs'))  # Must start with letter
        self.assertFalse(self.validate('.dotsarebadtoo'))
        self.assertFalse(self.validate('!nvalid'))
        self.assertFalse(self.validate('B@dCharacters'))
        self.assertFalse(self.validate('I cannot read instructions'))
        self.assertFalse(self.validate(u'h\u0400llojello'))  # Cyrillic chars
        self.assertFalse(self.validate('mrpants@khanacademy.org'))

    def test_good_user_name_validates(self):
        self.assertTrue(self.validate('poopybutt'))
        self.assertTrue(self.validate('mrpants'))
        self.assertTrue(self.validate('instructionsareeasy'))
        self.assertTrue(self.validate('coolkid1983'))

    def make_user(self, email):
        u = UserData.insert_for(email, email)
        u.put()
        return u

    def test_claiming_username_works(self):
        u1 = self.make_user("bob")
        u2 = self.make_user("robert")

        # Free
        self.assertTrue(u1.claim_username("superbob"))
        self.assertEqual("superbob", u1.username)

        # Now it's taken
        self.assertFalse(u2.claim_username("superbob"))

        # But something completely different should still be good
        self.assertTrue(u2.claim_username("sadbob"))
        self.assertEqual("sadbob", u2.username)

    def test_releasing_usernames(self):
        clock = mock_datetime.MockDatetime()
        u1 = self.make_user("bob")
        u2 = self.make_user("robert")

        # u1 gets "superbob", but changes his mind.
        self.assertTrue(u1.claim_username("superbob", clock))
        self.assertEqual("superbob", u1.username)
        self.assertTrue(u1.claim_username("ultrabob", clock))
        self.assertEqual("ultrabob", u1.username)

        # TOTAL HACK - for some reason without this read (which shouldn't
        # actually have any side effect), the following assert fails because
        # there's no strong consistency ensured on the HRD.
        db.get([u1.key()])
        self.assertEqual(
                u1.user_id,
                UserData.get_from_username("ultrabob").user_id)
        self.assertEqual(
                None,
                UserData.get_from_username("superbob"))

        # Usernames go into a holding pool, even after they're released
        self.assertFalse(u2.claim_username("superbob", clock))

        # Note that the original owner can't even have it back
        self.assertFalse(u1.claim_username("superbob", clock))

        # Still no good at the border of the holding period
        clock.advance(UniqueUsername.HOLDING_PERIOD_DELTA)
        self.assertFalse(u2.claim_username("superbob", clock))

        # OK - now u2 can have it.
        clock.advance_days(1)
        self.assertTrue(u2.claim_username("superbob", clock))
        self.assertEqual("superbob", u2.username)

        db.get([u2.key()])
        self.assertEqual(
                u2.user_id,
                UserData.get_from_username("superbob").user_id)

    def test_usernames_dont_match_if_invalid(self):
        self.assertFalse(UniqueUsername.matches(None, None))
        self.assertFalse(UniqueUsername.matches("superbob", None))
        self.assertFalse(UniqueUsername.matches("superbob", "i n v a l id"))

    def test_username_matching(self):
        self.assertTrue(UniqueUsername.matches("superbob", "super.bob"))
        self.assertTrue(UniqueUsername.matches("superbob", "SuperBob"))
        self.assertFalse(UniqueUsername.matches("superbob", "fakebob"))

    def test_deleting_user_releases_username(self):
        clock = mock_datetime.MockDatetime()
        u1 = self.make_user("bob")

        self.assertTrue(u1.claim_username("bob"))
        self.assertFalse(UniqueUsername.is_available_username("bob",
                                                              clock=clock))
        u1.delete(clock=clock)

        # We don't do anything special to delete it immediately, so it's still
        # in the holding period.
        clock.advance(UniqueUsername.HOLDING_PERIOD_DELTA)
        clock.advance(datetime.timedelta(1))
        self.assertTrue(UniqueUsername.is_available_username("bob",
                                                             clock=clock))


class ProfileSegmentTest(gae_model.GAEModelTestCase):
    def to_url(self, user):
        return user.profile_root

    def from_url(self, url):
        # Profile URLs are of the form "/profile/segment"
        return UserData.get_from_url_segment(url[9:-1])

    def create_phantom(self):
        user_id = phantom_users.phantom_util._create_phantom_user_id()
        return UserData.insert_for(user_id, user_id)

    def test_url_segment_generation(self):
        # Pre-phantom users can't have profile URLs
        prephantom = UserData.pre_phantom()
        self.assertTrue(self.from_url(self.to_url(prephantom)) is None)

        # Phantom users can't have profile URLs
        phantom = self.create_phantom()
        self.assertTrue(self.from_url(self.to_url(phantom)) is None)

        # Normal users are cool, though.
        bob = UserData.insert_for(
                "http://googleid.khanacademy.org/1234",
                "bob@gmail.com")
        bob.put()
        self.assertEqual(
                self.from_url(self.to_url(bob)).user_id,
                bob.user_id)

        sally = UserData.insert_for(
                "http://facebookid.khanacademy.org/1234",
                "http://facebookid.khanacademy.org/1234")
        sally.put()
        self.assertEqual(
                self.from_url(self.to_url(sally)).user_id,
                sally.user_id)

    def test_return_key_in_profile_root_for_users_without_username(self):
        bob = UserData.insert_for(
            "http://googleid.khanacademy.org/1234",
            "bob@gmail.com")

        desired_profile_root = ("/profile/" + _USER_KEY_PREFIX + str(bob.key())
                + "/")
        self.assertEquals(desired_profile_root, bob.profile_root)

    def test_return_username_in_profile_root_if_exists(self):
        bob = UserData.insert_for(
            "http://googleid.khanacademy.org/1234",
            "bob@gmail.com")

        username = "bobby"
        bob.claim_username(username)

        desired_profile_root = "/profile/" + username + "/"

        self.assertEquals(desired_profile_root, bob.profile_root)

class UserDataCreationTest(gae_model.GAEModelTestCase):
    def flush(self, items):
        """ Ensures items are flushed in the HRD. """
        db.get([item.key() for item in items if item])

    def insert_user(self, user_id, email, username=None, password=None):
        return UserData.insert_for(user_id, email, username, password)

    def test_creation_without_username(self):
        added = [
            self.insert_user("larry", "email1@gmail.com"),
            self.insert_user("curly", "email2@gmail.com"),
            self.insert_user("moe", "email3@gmail.com"),
        ]
        # We don't care about consistency policy issues - we just want proper
        # counts and such.
        self.flush(added)
        self.assertEqual(3, UserData.all().count())
        self.assertEqual(set(["larry", "curly", "moe"]),
                         set(user.user_id for user in UserData.all()))

        # "Re-adding" moe doesn't duplicate.
        self.flush([self.insert_user("moe", "email3@gmail.com")])
        self.assertEqual(3, UserData.all().count())

    def test_creation_with_bad_username(self):
        self.assertTrue(self.insert_user("larry", "email1@gmail.com", "!!!!!")
                        is None)

    def test_creation_with_existing_username(self):
        self.flush([self.insert_user("larry", "email1@gmail.com", "larry")])
        self.assertEqual(1, UserData.all().count())
        self.assertEqual("larry", UserData.all()[0].user_id)
        self.assertEqual("larry", UserData.all()[0].username)

        self.assertTrue(self.insert_user("larry2", "tooslow@gmail.com",
            "larry") is None)

    @testsize.medium()
    def test_creation_with_password(self):
        self.flush([self.insert_user("larry",
                                     "email1@gmail.com",
                                     "larry",
                                     "Password1")])
        self.assertEqual(1, UserData.all().count())
        retrieved = UserData.all()[0]
        self.assertEqual("larry", retrieved.user_id)
        self.assertTrue(retrieved.validate_password("Password1"))
        self.assertFalse(retrieved.validate_password("Password2"))


class UserConsumptionTest(gae_model.GAEModelTestCase):

    def make_exercise(self, name):
        exercise = exercise_models.Exercise(name=name)
        exercise.put()
        return exercise

    @testsize.medium()
    def test_user_identity_consumption(self):
        superman = UserData.insert_for(
                "superman@gmail.krypt",
                email="superman@gmail.krypt",
                username="superman",
                password="Password1",
                gender="male",
                )

        clark = UserData.insert_for(
                "clark@kent.com",
                email="clark@kent.com",
                username=None,
                password=None,
                )

        clark.consume_identity(superman)
        self.assertEqual("superman@gmail.krypt", clark.user_id)
        self.assertEqual("superman@gmail.krypt", clark.email)
        self.assertEqual(clark.key(),
                         UserData.get_from_username("superman").key())
        self.assertEqual(clark.key(),
                         UserData.get_from_user_id("superman@gmail.krypt").key())
        self.assertTrue(clark.validate_password("Password1"))

    def test_user_exercise_preserved_after_consuming(self):
        # A user goes on as a phantom...
        phantom = UserData.insert_for("phantom", "phantom")
        exercises = [
                self.make_exercise("Adding 1"),
                self.make_exercise("Multiplication yo"),
                self.make_exercise("All about chickens"),
                ]

        # Does some exercises....
        for e in exercises:
            ue = phantom.get_or_insert_exercise(e)
            ue.total_done = 7
            ue.put()

        # Signs up!
        jimmy = UserData.insert_for("justjoinedjimmy@gmail.com",
                                    email="justjoinedjimmy@gmail.com")
        phantom.consume_identity(jimmy)

        # Make sure we can still see the old user exercises
        shouldbejimmy = UserData.get_from_user_id("justjoinedjimmy@gmail.com")
        user_exercises = (exercise_models.UserExercise.
                          get_for_user_data(shouldbejimmy).fetch(100))
        self.assertEqual(len(exercises), len(user_exercises))
        for ue in user_exercises:
            self.assertEqual(7, ue.total_done)


class ParentChildPairTest(gae_model.GAEModelTestCase):
    def make_user(self, email):
        return UserData.insert_for(email, email)

    def make_child_account(self, parent, username):
        # TODO(benkomalo): figure out a way to stub out datetime.date.today
        # nicely so this doesn't break in 2015
        child = parent.spawn_child(username,
                                   datetime.date(2012, 1, 1),
                                   password="childpassword")
        return child

    def test_basic_child_creation(self):
        parent = self.make_user("parent@gmail.com")
        # TODO(benkomalo): figure out a way to stub out datetime.date.today
        # nicely so this doesn't break in 2015
        child = parent.spawn_child(username="childuser",
                                   birthdate=datetime.date(2012, 1, 1),
                                   password="childpassword")

        self.assertTrue(child is not None)
        self.assertTrue(child.is_child_account())

        # Note that child accounts can't collect real names, so it falls back
        # to username.
        self.assertEquals("childuser", child.nickname)
        self.assertEquals("childuser", child.username)

    def test_basic_bond(self):
        parent = self.make_user("parent@gmail.com")
        child = self.make_child_account(parent, "child")

        retrieved_bonds = ParentChildPair.get_for_parent(parent)
        self.assertEquals(1, len(retrieved_bonds.fetch(1000)))
        self.assertEquals(child.key(),
                          retrieved_bonds[0].resolve_child().key())

        retrieved_parent_bond = ParentChildPair.get_for_child(child)
        self.assertEquals(parent.key(),
                          retrieved_parent_bond.resolve_parent().key())

    def test_invalid_bonds(self):
        too_old = self.make_user("oops@gmail.com")
        parent = self.make_user("parent@gmail.com")
        with mock.patch("logging.error") as errorlog:
            self.assertFalse(ParentChildPair.make_bond(parent, too_old))
            self.assertEquals(1, errorlog.call_count)

    def test_cant_have_multiple_parent_accounts(self):
        parent = self.make_user("parent@gmail.com")
        parent2 = self.make_user("parent2@gmail.com")
        child = self.make_child_account(parent, "child")

        with mock.patch("logging.error") as errorlog:
            # Going to fail because the child already has a parent.
            self.assertFalse(ParentChildPair.make_bond(parent2, child))
            self.assertEquals(1, errorlog.call_count)

        self.assertTrue(ParentChildPair.is_pair(parent, child))
        self.assertFalse(ParentChildPair.is_pair(parent2, child))

    def assertFullyCoached(self, child, parent):
        self.assertTrue(child.is_coached_by(parent))
        self.assertTrue(child.is_visible_to(parent))
        self.assertTrue(parent.has_students())
        self.assertTrue(any(student.key() == child.key()
                            for student in parent.get_students_data()))
        self.assertTrue(any(coach.key() == parent.key()
                            for coach in child.get_coaches_data()))

    def test_parent_is_automatic_coach(self):
        parent = self.make_user("parent@gmail.com")
        child = self.make_child_account(parent, "child")
        self.assertFullyCoached(child, parent)

    def test_ensure_parents_cant_be_removed_via_coach_interfaces(self):
        parent = self.make_user("parent@gmail.com")
        child = self.make_child_account(parent, "child")
        child.set_can_modify_coaches()

        coaches.update_coaches(child, [])  # Remove all normal coaches
        self.assertFullyCoached(child, parent)


class CapabilitiesTest(gae_model.GAEModelTestCase):
    def test_basic_addition_removal(self):
        capabilities = []
        self.assertFalse(Capabilities._list_includes(capabilities, 'foo'))

        capabilities = Capabilities._set_capability_in_list(
                capabilities, 'foo', allow=True)
        self.assertTrue(Capabilities._list_includes(capabilities, 'foo'))

        # Adding is idempotent - subsequent calls shouldn't do much.
        capabilities = Capabilities._set_capability_in_list(
                capabilities, 'foo', allow=True)
        self.assertTrue(Capabilities._list_includes(capabilities, 'foo'))

        capabilities = Capabilities._set_capability_in_list(
                capabilities, 'foo', allow=False)
        self.assertFalse(Capabilities._list_includes(capabilities, 'foo'))
