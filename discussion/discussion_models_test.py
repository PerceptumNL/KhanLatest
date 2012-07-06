from third_party.agar.test import BaseTest

# TODO(marcia): Not sure why user_models has to come first
import user_models
import discussion_models
import notification
import video_models


class FeedbackTest(BaseTest):
    def make_video(self):
        video = video_models.Video()
        video.topic_string_keys = "irrelevant, but can't be None"
        video.put()
        return video

    def make_question(self, content, video, user_data):
        return discussion_models.Feedback.insert_feedback(content,
            discussion_models.FeedbackType.Question, video, user_data)

    def make_user_data(self, email):
        return user_models.UserData.insert_for(email, email)

    def make_answer(self, content, question, user_data):
        return discussion_models.Feedback.insert_feedback(content,
            discussion_models.FeedbackType.Answer, question, user_data)


class FeedbackFlagTest(FeedbackTest):
    def test_hide_from_public_after_two_people_flag(self):
        video = self.make_video()
        asker = self.make_user_data('hawkeye@gmail.com')
        question = self.make_question("What's up, Black Widow?", video, asker)

        self.assertEqual(True, question.is_visible_to_public())

        responsible_user = self.make_user_data('captainamerica@gmail.com')
        question.add_flag_by(discussion_models.FeedbackFlag.DoesNotBelong,
                responsible_user)

        self.assertEqual(True, question.is_visible_to_public())

        another_responsible_user = self.make_user_data('thor@gmail.com')
        question.add_flag_by(discussion_models.FeedbackFlag.DoesNotBelong,
                another_responsible_user)

        self.assertEqual(False, question.is_visible_to_public())

    def test_count_flag_attempts_by_same_person_as_one_flag(self):
        video = self.make_video()
        asker = self.make_user_data('hawkeye@gmail.com')
        question = self.make_question("What's up, Black Widow?", video, asker)

        self.assertEqual(True, question.is_visible_to_public())

        responsible_user = self.make_user_data('captainamerica@gmail.com')
        question.add_flag_by(discussion_models.FeedbackFlag.DoesNotBelong,
                responsible_user)

        question.add_flag_by(discussion_models.FeedbackFlag.DoesNotBelong,
                responsible_user)

        self.assertEqual(1, len(question.flags))
        self.assertEqual(1, len(question.flagged_by))

    def test_clear_flags(self):
        video = self.make_video()
        asker = self.make_user_data('hawkeye@gmail.com')
        question = self.make_question("What's up, Black Widow?", video, asker)

        responsible_user = self.make_user_data('captainamerica@gmail.com')
        question.add_flag_by(discussion_models.FeedbackFlag.DoesNotBelong,
                responsible_user)

        question.clear_flags()

        self.assertEqual(0, len(question.flags))
        self.assertEqual(0, len(question.flagged_by))


class FeedbackNotificationTest(FeedbackTest):
    def test_increase_notification_count_with_new_answer(self):
        video = self.make_video()
        asker = self.make_user_data('weasley@gmail.com')
        answerer = self.make_user_data('hermione@gmail.com')

        question = self.make_question("Where did Harry go?", video, asker)
        self.make_answer("He went to the loo.", question, answerer)

        self.assertEqual(1, asker.feedback_notification_count())

    def test_reset_notification_count_upon_read(self):
        video = self.make_video()
        asker = self.make_user_data('weasley@gmail.com')
        answerer = self.make_user_data('hermione@gmail.com')

        question = self.make_question("Where did Harry go?", video, asker)
        self.make_answer("He went to the loo.", question, answerer)

        notification.clear_notification_for_question(question.key(), asker)

        self.assertEqual(0, asker.feedback_notification_count())

    def test_have_one_notification_for_answers_on_same_question(self):
        video = self.make_video()
        asker = self.make_user_data('weasley@gmail.com')
        answerer = self.make_user_data('hermione@gmail.com')
        other_answerer = self.make_user_data('harry@gmail.com')

        question = self.make_question("Where did Harry go?", video, asker)
        self.make_answer("He went to the loo.", question, answerer)
        self.make_answer("No, I'm right here!", question, other_answerer)

        self.assertEqual(1, asker.feedback_notification_count())

    def test_no_notification_for_answering_own_question(self):
        video = self.make_video()
        asker = self.make_user_data('weasley@gmail.com')
        question = self.make_question("Where did Harry go?", video, asker)
        self.make_answer("Oh, I know where he went.", question, asker)

        self.assertEqual(0, asker.feedback_notification_count())

    def test_no_notification_for_question_changed_to_comment(self):
        video = self.make_video()
        asker = self.make_user_data('weasley@gmail.com')
        answerer = self.make_user_data('hermione@gmail.com')

        question = self.make_question("Where did Harry go?", video, asker)
        self.make_answer("He went to the loo.", question, answerer)

        question.change_type(discussion_models.FeedbackType.Comment)
        self.assertEqual(0, asker.feedback_notification_count())

    def test_get_notification_for_question_changed_to_comment_and_back(self):
        video = self.make_video()
        asker = self.make_user_data('weasley@gmail.com')
        answerer = self.make_user_data('hermione@gmail.com')

        question = self.make_question("Where did Harry go?", video, asker)
        self.make_answer("He went to the loo.", question, answerer)

        question.change_type(discussion_models.FeedbackType.Comment)
        question.change_type(discussion_models.FeedbackType.Question)
        self.assertEqual(1, asker.feedback_notification_count())

    def test_no_notification_if_answer_is_deleted(self):
        video = self.make_video()
        asker = self.make_user_data('weasley@gmail.com')
        answerer = self.make_user_data('hermione@gmail.com')

        question = self.make_question("Where did Harry go?", video, asker)
        answer = self.make_answer("He went to the loo.", question, answerer)

        answer.delete()
        self.assertEqual(0, asker.feedback_notification_count())

    def test_no_notification_if_answer_is_marked_as_deleted(self):
        video = self.make_video()
        asker = self.make_user_data('weasley@gmail.com')
        answerer = self.make_user_data('hermione@gmail.com')

        question = self.make_question("Where did Harry go?", video, asker)
        answer = self.make_answer("He went to the loo.", question, answerer)

        answer.deleted = True
        answer.put()

        self.assertEqual(0, asker.feedback_notification_count())

    def test_no_notification_if_question_is_deleted(self):
        video = self.make_video()
        asker = self.make_user_data('weasley@gmail.com')
        answerer = self.make_user_data('hermione@gmail.com')

        question = self.make_question("Where did Harry go?", video, asker)
        self.make_answer("He went to the loo.", question, answerer)

        question.delete()
        self.assertEqual(0, asker.feedback_notification_count())
