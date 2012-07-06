from discussion import discussion_models_test
import feedback_badges


class AnswerVoteCountBadgeTest(discussion_models_test.FeedbackTest):
    def test_level_one(self):
        # Requires 10 upvotes on an answer
        badge = feedback_badges.LevelOneAnswerVoteCountBadge()

        video = self.make_video()
        asker = self.make_user_data('hawkeye@gmail.com')
        question = self.make_question("What's up, Black Widow?", video, asker)
        answerer = self.make_user_data('black.widow@avengers.org')
        answer = self.make_answer("Just saving the world!", question, answerer)

        votes = {
            0: False,
            1: False,
            8: False,
            9: True,  # implicit 1 vote, so this is really "10 votes"
            10: True,
            1000: True,
        }

        for sv in votes:
            question.sum_votes = sv
            question.put()
            answer.sum_votes = sv
            answer.put()

            # Questions don't earn answer badges ever
            self.assertFalse(badge.is_satisfied_by(feedback=question))
            self.assertEqual(votes[sv], badge.is_satisfied_by(feedback=answer))

        self.assertFalse(badge.is_already_owned_by(answerer, feedback=answer))
        badge.award_to(answerer, feedback=answer)
        self.assertTrue(badge.is_already_owned_by(answerer, feedback=answer))


class QuestionVoteCountBadgeTest(discussion_models_test.FeedbackTest):
    def test_level_one(self):
        # Requires 10 upvotes on a question
        badge = feedback_badges.LevelOneQuestionVoteCountBadge()

        video = self.make_video()
        asker = self.make_user_data('hawkeye@gmail.com')
        question = self.make_question("What's up, Black Widow?", video, asker)
        answerer = self.make_user_data('black.widow@avengers.org')
        answer = self.make_answer("Just saving the world!", question, answerer)

        votes = {
            0: False,
            1: False,
            8: False,
            9: True,  # implicit 1 vote, so this is really "10 votes"
            10: True,
            1000: True,
        }

        for sv in votes:
            question.sum_votes = sv
            question.put()
            answer.sum_votes = sv
            answer.put()

            self.assertEqual(votes[sv],
                    badge.is_satisfied_by(feedback=question))
            # Answers don't earn question badges ever
            self.assertFalse(badge.is_satisfied_by(feedback=answer))

        self.assertFalse(badge.is_already_owned_by(asker, feedback=question))
        badge.award_to(asker, feedback=question)
        self.assertTrue(badge.is_already_owned_by(asker, feedback=question))
