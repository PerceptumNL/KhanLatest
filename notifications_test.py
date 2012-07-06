#!/user/bin/env python

from google.appengine.ext import db

from discussion import discussion_models_test  # used to award Feedback badges
import notifications
from phantom_users import phantom_util
from phantom_users import util_notify


class NotificationsTest(discussion_models_test.FeedbackTest):

    def make_phantom_user_data(self, name):
        return self.make_user_data(
                phantom_util.PHANTOM_ID_EMAIL_PREFIX + name)

    def award_feedback_badge_to(self, user_data):
        # This should award a QuestionTimestampReferenceBadge...
        video = self.make_video()
        self.make_question("3:14 is pi time", video, user_data)

        # Put user's updated .has_notification and flush HRD consistency issues
        user_data.put()
        db.get(user_data.key())

    def send_phantom_notification_to(self, user_data):
        # Start by awarding the user's first badge...
        self.award_feedback_badge_to(user_data)

        # ...then kick off a phantom user notification about receiving a badge
        util_notify.update(user_data, None, gotBadge=True)

        # Put user's updated .has_notification and flush HRD consistency issues
        user_data.put()
        db.get(user_data.key())

    def test_badge_notification(self):
        user_data = self.make_user_data("mr.talky@gmail.com")
        self.award_feedback_badge_to(user_data)

        # We should now have a BadgeNotification waiting.
        note_dict = notifications.Notifier.pop_for_user_data(user_data)
        badge_notes = note_dict.get("badges", [])

        self.assertEqual(1, len(badge_notes))
        self.assertTrue(isinstance(
            badge_notes[0], notifications.BadgeNotification))

    def test_has_notification_flag(self):
        user_data = self.make_user_data("mr.talky@gmail.com")
        self.award_feedback_badge_to(user_data)

        user_data_test_1 = self.make_user_data("mr.talky@gmail.com")
        self.assertTrue(user_data_test_1.has_notification)

        # After popping, has_notification flag should flip to False
        notifications.Notifier.pop_for_user_data(user_data)

        user_data_test_2 = self.make_user_data("mr.talky@gmail.com")
        self.assertFalse(user_data_test_2.has_notification)

    def test_has_notification_flag_phantom(self):
        user_data = self.make_phantom_user_data("armadillo")
        self.award_feedback_badge_to(user_data)

        user_data_test_1 = self.make_phantom_user_data("armadillo")
        self.assertTrue(user_data_test_1.has_notification)

        # After popping, has_notification flag should stay True for phantom
        # users (the phantom notification is persistent)
        notifications.Notifier.pop_for_user_data(user_data)

        user_data_test_2 = self.make_phantom_user_data("armadillo")
        self.assertTrue(user_data_test_2.has_notification)

    def test_badge_notification_clear(self):
        user_data = self.make_user_data("mr.talky@gmail.com")
        self.award_feedback_badge_to(user_data)

        notifications.BadgeNotification.clear(user_data)

        note_dict = notifications.Notifier.pop_for_user_data(user_data)
        badge_notes = note_dict.get("badges", [])
        self.assertEqual(0, len(badge_notes))

    def test_clear_all(self):
        user_data_1 = self.make_phantom_user_data("monkey")
        self.send_phantom_notification_to(user_data_1)

        user_data_2 = self.make_phantom_user_data("gorilla")
        self.send_phantom_notification_to(user_data_2)

        notifications.Notification.clear_all(user_data_1)

        note_dict_1 = notifications.Notifier.pop_for_user_data(user_data_1)
        note_dict_2 = notifications.Notifier.pop_for_user_data(user_data_2)

        badge_notes_1 = note_dict_1.get("badges", [])
        phantom_notes_1 = note_dict_1.get("phantoms", [])
        badge_notes_2 = note_dict_2.get("badges", [])
        phantom_notes_2 = note_dict_2.get("phantoms", [])

        # User 1's notifications should be empty
        self.assertEqual(0, len(badge_notes_1))
        self.assertEqual(0, len(phantom_notes_1))

        # User 2's notifications should still exist
        self.assertEqual(1, len(badge_notes_2))
        self.assertEqual(1, len(phantom_notes_2))

    def test_phantom_notification(self):
        user_data = self.make_phantom_user_data("anteater")
        self.send_phantom_notification_to(user_data)

        # We should now have a BadgeNotification and PhantomNotification
        note_dict = notifications.Notifier.pop_for_user_data(user_data)
        badge_notes = note_dict.get("badges", [])
        phantom_notes = note_dict.get("phantoms", [])

        self.assertEqual(1, len(badge_notes))
        self.assertEqual(1, len(phantom_notes))

        self.assertTrue(isinstance(
            badge_notes[0], notifications.BadgeNotification))
        self.assertTrue(isinstance(
            phantom_notes[0], notifications.PhantomNotification))

    def test_notification_persistence(self):
        user_data = self.make_phantom_user_data("chimpanzee")
        self.send_phantom_notification_to(user_data)

        # We should now have a BadgeNotification and PhantomNotification
        note_dict = notifications.Notifier.pop_for_user_data(user_data)

        # ...but after the second pop, only PhantomNotifications should persist
        note_dict = notifications.Notifier.pop_for_user_data(user_data)

        badge_notes = note_dict.get("badges", [])
        phantom_notes = note_dict.get("phantoms", [])

        self.assertEqual(0, len(badge_notes))  # badge notes aren't persisent
        self.assertEqual(1, len(phantom_notes))  # ...but phantom notes are
