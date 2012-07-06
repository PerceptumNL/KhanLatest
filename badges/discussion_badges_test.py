from discussion import discussion_models_test
import discussion_badges


class TimestampReferenceBadgesTest(discussion_models_test.FeedbackTest):
    def test_matching(self):
        qbadge = discussion_badges.QuestionTimestampReferenceBadge()
        abadge = discussion_badges.AnswerTimestampReferenceBadge()

        video = self.make_video()

        texts = {
            "Just saving the world!": False,
            "See 3:22 for the surprise answer!": True,
            "not really7:12 a timestamp": False,
            "neither 2:33is this": False,
            "nor this: 5:92": False,
            "but this is! 20:12": True,
            "1:23 <- as is that": True,
            ":23 2:0": False,
        }

        asker = self.make_user_data('hawkeye@avengers.org')
        answerer = self.make_user_data('black.widow@avengers.org')

        for text, satisfied in texts.iteritems():
            question = self.make_question(text, video, asker)
            answer = self.make_answer(text, question, answerer)

            self.assertEqual(satisfied,
                    qbadge.is_satisfied_by(feedback=question))
            self.assertEqual(satisfied,
                    abadge.is_satisfied_by(feedback=answer))

            # Wrong type of feedback for the badge
            self.assertFalse(abadge.is_satisfied_by(feedback=question))
            self.assertFalse(qbadge.is_satisfied_by(feedback=answer))

    def test_auto_award(self):
        qbadge = discussion_badges.QuestionTimestampReferenceBadge()
        abadge = discussion_badges.AnswerTimestampReferenceBadge()

        video = self.make_video()

        asker = self.make_user_data('tony@stark.com')
        self.assertFalse(qbadge.is_already_owned_by(asker))
        question = self.make_question("3:14 is pi time", video, asker)
        self.assertTrue(qbadge.is_already_owned_by(asker))
        self.assertFalse(abadge.is_already_owned_by(asker))

        answerer = self.make_user_data('pepper@stark.com')
        self.assertFalse(abadge.is_already_owned_by(answerer))
        self.make_answer("and 6:28 is tau time", question, answerer)
        self.assertFalse(qbadge.is_already_owned_by(answerer))
        self.assertTrue(abadge.is_already_owned_by(answerer))
