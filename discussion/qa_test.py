from third_party.agar.test import BaseTest

import qa
import discussion_models
import topic_models
import user_models
import video_models
import voting


class QATest(BaseTest):
    # TODO(ankit): Make testutil/fake_video.py. Some of these methods are also
    # used in discussion_models_test.py.
    def make_topic(self):
        topic = topic_models.Topic.insert(
            title='title',
            parent=None,
            version=topic_models.TopicVersion.create_new_version())
        topic.put()
        return topic

    def make_video(self, topic):
        video = video_models.Video()
        video.topic_string_keys = [str(topic.key())]
        video.put()
        return video

    def make_question(self, content, video, user_data):
        return discussion_models.Feedback.insert_feedback(content,
            discussion_models.FeedbackType.Question,
            video,
            user_data)

    def make_user_data(self, email):
        return user_models.UserData.insert_for(email, email)

    def make_answer(self, content, question, user_data):
        return discussion_models.Feedback.insert_feedback(content,
            discussion_models.FeedbackType.Answer,
            question,
            user_data)

    def make_answers(self, content, question, user_data, count):
        answers = []
        for i in range(count):
            answers.append(
                discussion_models.Feedback.insert_feedback(content,
                    discussion_models.FeedbackType.Answer,
                    question,
                    user_data))
        return answers


class QAGetUserAnswersTest(QATest):
    def test_cleaning_up_all_answers_without_question(self):
        topic = self.make_topic()
        video = self.make_video(topic)
        user = self.make_user_data('user@gmail.com')

        question = self.make_question("What is reality?", video, user)
        self.make_answers(
            "It is what you perceive.", question, user, 20)

        # This question will not be deleted.
        stable_question = self.make_question("What is reality?", video, user)
        self.make_answers(
            "It is what you perceive.", stable_question, user, 2)

        # Don't delete the questions answers', so calling the super.delete()
        # method.
        super(discussion_models.Feedback, question).delete()

        # Get the latest 5 answers, 3 of which won't have questions.
        user_answers = qa.get_user_answers(user, user, 1,
            voting.VotingSortOrder.NewestFirst, 5)

        # Check the answer count, should be 2.
        self.assertEquals(len(user_answers), 2)
