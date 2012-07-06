from discussion import discussion_models
from discussion import discussion_models_test
from discussion import voting
import discussion_quality_count_badges
import user_models


class DiscussionQualityCountBadgesTest(discussion_models_test.FeedbackTest):
    def test_badges(self):
        qbadge = (discussion_quality_count_badges.
                  LevelOneQuestionQualityCountBadge())

        video = self.make_video()
        asker = self.make_user_data('eater@khanacademy.org')

        voters = [self.make_user_data("voter%d@gmail.com" % i)
                  for i in range(2)]

        questions = [self.make_question("My car is also a spaceship?",
                                        video, asker)
                     for i in range(10)]

        for q in questions:
            for v in voters:
                stats = discussion_models.UserDiscussionStats.get_or_build_for(
                    asker)

                self.assertFalse(qbadge.is_satisfied_by(
                    user_data=asker, user_discussion_stats=stats))

                # Re-fetch Eater from the datastore because he may have changed
                asker = user_models.UserData.get_from_db_key_email(
                    'eater@khanacademy.org')
                self.assertFalse(qbadge.is_already_owned_by(asker))

                voting.FinishVoteEntity.perform_vote(
                    q, discussion_models.FeedbackVote.UP, v)

        stats = discussion_models.UserDiscussionStats.get_or_build_for(asker)
        self.assertTrue(qbadge.is_satisfied_by(
            user_data=asker, user_discussion_stats=stats))

        # Re-fetch Eater from the datastore because he may have changed
        asker = user_models.UserData.get_from_db_key_email(
            'eater@khanacademy.org')
        self.assertTrue(qbadge.is_already_owned_by(asker))
