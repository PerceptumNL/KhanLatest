import logging

from api.decorators import protobuf_encode, protobuf_decode
import discussion_models
import layer_cache
import request_cache
import user_models
import voting


def feedback_query(target_key):
    query = discussion_models.Feedback.all()
    query.filter("targets =", target_key)
    query.order('-date')
    return query


@request_cache.cache_with_key_fxn(
    discussion_models.Feedback.cache_key_for_video)
@protobuf_decode
@layer_cache.cache_with_key_fxn(discussion_models.Feedback.cache_key_for_video,
                                layer=layer_cache.Layers.Datastore)
@protobuf_encode
def get_feedback_for_video(video):
    return feedback_query(video.key()).fetch(1000)


@request_cache.cache_with_key_fxn(lambda v, ud: str(v) + str(ud))
def get_feedback_for_video_by_user(video_key, user_data_key):
    return feedback_query(video_key).ancestor(user_data_key).fetch(20)


def get_feedback_by_type_for_video(video, feedback_type, user_data=None):
    feedback = [f for f in get_feedback_for_video(video)
                if feedback_type in f.types]
    feedback_dict = dict([(f.key(), f) for f in feedback])

    # Fetch user feedback separately using an ancestor query to ensure
    # datastore consistency
    user_feedback = []
    if user_data:
        user_feedback = get_feedback_for_video_by_user(video.key(),
                                                       user_data.key())
    user_feedback_dict = dict([(f.key(), f) for f in user_feedback
                               if feedback_type in f.types])

    feedback_dict.update(user_feedback_dict)
    feedback = feedback_dict.values()

    # Filter out all deleted or flagged feedback (uses hellban technique)
    feedback = filter(lambda f: f.is_visible_to(user_data), feedback)

    return sorted(feedback, key=lambda s: s.date, reverse=True)


def get_feedback_count_by_author(type, user_data, viewer_data):
    """Get feedback count of specified type authored by the specified user."""
    stats = discussion_models.UserDiscussionStats.get_or_build_for(user_data)
    # If the user is visible to the viewer, count should included
    # deleted feedbacks.
    if viewer_data and user_data.is_visible_to(viewer_data):
        return stats.count_of_type(type, True)
    else:
        return stats.count_of_type(type, False)


def get_all_feedback_by_author(type, user_data,
        sort=voting.VotingSortOrder.NewestFirst):
    """Get all feedback of specified type authored by the specified user."""
    return get_feedback_by_author(type, user_data, sort=sort)


def get_feedback_by_author(type, user_data, page=1, limit=-1,
        sort=voting.VotingSortOrder.NewestFirst):
    """Get feedback of specified type authored by the specified user."""
    query = discussion_models.Feedback.all()
    query.filter('author_user_id =', user_data.user_id)
    query.filter('types =', type)
    if sort == voting.VotingSortOrder.HighestPointsFirst:
        query.order('-sum_votes')
    query.order('-date')
    if limit > 0:
        return query.fetch(limit, offset=(page - 1) * limit)
    return [q for q in query]


def is_post_allowed(user_data, request):
    """Determine whether a request to post discussion content is allowed.

    There may be multiple reasons why a post to create content is disallowed,
    based on actor privileges or spam detection."""

    if not user_data:
        return False

    if user_data.is_child_account():
        logging.warn("Received unexpected post to create discussion content "
                     "by user with id [%s]" % user_data.user_id)
        return False

    return True


class ClientFeedback(object):
    """Transient object derived from a discussion_models.Feedback entity,
    with extra properties as required by the client to render.

    Additional client properties include "key", "appears_as_deleted",
    "question_key", "show_author_controls", and "sum_votes_incremented".
    """
    @staticmethod
    def from_feedback(feedback, with_extra_vote_properties=False,
            with_moderation_properties=False):
        client_feedback = ClientFeedback()
        client_feedback.key = str(feedback.key())
        client_feedback.content = feedback.content

        if feedback.is_type(discussion_models.FeedbackType.Question):
            client_feedback.answers = [ClientFeedback.from_feedback(answer)
                    for answer in feedback.children_cache]
        elif feedback.is_type(discussion_models.FeedbackType.Answer):
            client_feedback.question_key = feedback.question_key()

        client_feedback.author_user_id = feedback.author_user_id
        client_feedback.author_nickname = feedback.author_nickname

        client_feedback.date = feedback.date

        current_user_data = user_models.UserData.current()

        client_feedback.appears_as_deleted = feedback.appears_as_deleted_to(
                current_user_data)
        client_feedback.show_author_controls = feedback.authored_by(
                current_user_data)

        client_feedback.sum_votes_incremented = feedback.sum_votes_incremented
        client_feedback.flags = feedback.flags

        if with_extra_vote_properties:
            client_feedback.up_voted = feedback.up_voted
            client_feedback.down_voted = feedback.down_voted

        if with_moderation_properties:
            client_feedback.flagged_by = feedback.flagged_by
            client_feedback.type = feedback.types[0]
            client_feedback.low_quality_score = feedback.low_quality_score

            # TODO(marcia): Consider prefetching, as in http://blog.notdot.net
            # /2010/01/ReferenceProperty-prefetching-in-App-Engine
            video = feedback.video()
            if video:
                client_feedback.video_url = "/v/%s" % video.readable_id

        return client_feedback


class UserQuestion(object):
    """Transient object for data associated with a user's question, including
    the target video and number of answerers, or None if the associated video
    no longer exists.
    """
    @staticmethod
    def from_question(question, viewer_user_data):
        """Construct a UserQuestion from a Feedback entity."""
        if not question.is_visible_to(viewer_user_data):
            return None

        video = question.video()
        if not video:
            return None

        user_question = UserQuestion()
        user_question.video = video

        # qa_expand_key is later used as a url parameter on the video page
        # to expand the question and its answers
        user_question.qa_expand_key = str(question.key())
        user_question.content = question.content
        user_question.date = question.date
        user_question.author_nickname = question.author_nickname
        user_question.sum_votes_incremented = question.sum_votes_incremented

        # TODO(ankit): Should we get all the topics here?
        user_question.topic = video.first_topic()
        user_question.set_answer_data(question, viewer_user_data)

        if question.appears_as_deleted_to(viewer_user_data):
            user_question.deleted = question.deleted

        return user_question

    def mark_has_unread(self):
        self.has_unread = True

    def set_answer_data(self, question, viewer_user_data):
        """Set answerer count and last date as seen by the specified viewer.
        """
        query = feedback_query(question.key())
        self.answer_count = 0
        self.answerer_count = 0
        self.last_date = question.date

        # We assume all answers have been read until we see a notification
        self.has_unread = False

        if query.count():
            viewable_answers = [answer for answer in query if
                    not answer.appears_as_deleted_to(viewer_user_data)]

            self.answer_count = len(viewable_answers)

            answerer_user_ids = set(answer.author_user_id for answer
                    in viewable_answers)
            self.answerer_count = len(answerer_user_ids)

            # If there are no visible answers, last_updated is
            # set to the date the question was posted.
            if self.answer_count > 0:
                self.last_updated = max(
                    [answer.date for answer in viewable_answers])
            else:
                self.last_updated = question.date


class UserAnswer(object):
    """Transform the given answer object to include relevant information,
    including the answer's question and question key.
    """

    @staticmethod
    def from_answer(answer, viewer_user_data):
        """Construct a UserAnswer from a Feedback entity."""
        if not answer.is_visible_to(viewer_user_data):
            return None

        user_answer = UserAnswer()
        question = answer.question()

        if not question:
            # If the answer does not have a question, delete it.
            stats = discussion_models.UserDiscussionStats.get_or_build_for(
                answer.get_author())
            stats.forget(answer)
            stats.put()
            answer.delete()
            return None

        user_answer.question_key = answer.question_key()
        user_answer.question = UserQuestion.from_question(question,
            viewer_user_data)

        user_answer.content = answer.content
        user_answer.date = answer.date
        user_answer.author_nickname = answer.author_nickname
        user_answer.sum_votes_incremented = answer.sum_votes_incremented
        user_answer.content = answer.content
        user_answer.key = answer.key()

        if answer.appears_as_deleted_to(viewer_user_data):
            user_answer.deleted = answer.deleted

        return user_answer


class UserComment(object):
    """Transform the given comment object to include relevant information,
    including the comment's question.
    """

    @staticmethod
    def from_comment(comment, viewer_user_data):
        """Construct a UserComment from a Feedback entity."""
        if not comment.is_visible_to(viewer_user_data):
            return None

        user_comment = UserComment()

        video = comment.video()
        if not video:
            return None

        user_comment.video_key = comment.video_key()
        user_comment.video = video
        user_comment.topic = video.first_topic()
        user_comment.content = comment.content
        user_comment.date = comment.date
        user_comment.author_nickname = comment.author_nickname
        user_comment.sum_votes_incremented = comment.sum_votes_incremented
        user_comment.content = comment.content
        if comment.appears_as_deleted_to(viewer_user_data):
            user_comment.deleted = comment.deleted

        return user_comment
