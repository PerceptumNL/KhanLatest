from google.appengine.ext import db

from profiles import suggested_activity
import discussion_models
import notification
import util_discussion
import user_models
import user_util
import video_models
import voting


def get_user_questions(user_data, viewer_data, page, sort, limit=-1):
    """Return a list of util_discussion.UserQuestion entities, representing a
    user's questions.

    Arguments:
        user_data: The user whose questions need to be fetched
        viewer_data: The user who is going to view the questions
        page: The desired page number (>=1)
        sort: one of possible sort orders in voting.VotingSortOrder
        limit: Upper bound for the number of questions to return
    """
    if not (1 <= limit <= 10):
        limit = 10

    questions = util_discussion.get_feedback_by_author(
        discussion_models.FeedbackType.Question,
        user_data, page, limit, sort)

    return filter(lambda x: x is not None,
                [util_discussion.UserQuestion.from_question(
                question, viewer_data) for question in questions])


def get_user_answers(user_data, viewer_data, page, sort, limit=-1):
    """Returns a list of util_discussion.UserAnswer entities, representing a
    user's answers.

    Arguments:
        user_data: The user whose answers need to be fetched
        viewer_data: The user who is going to view the answers
        page: The desired page number (>=1)
        sort: one of possible sort orders in voting.VotingSortOrder
        limit: Upper bound for the number of answers to return
    """
    if not (1 <= limit <= 10):
        limit = 10

    answers = util_discussion.get_feedback_by_author(
        discussion_models.FeedbackType.Answer,
        user_data, page, limit, sort)

    user_answers = filter(lambda x: x is not None,
        [util_discussion.UserAnswer.from_answer(
        answer, viewer_data) for answer in answers])

    # If any answers without a question were removed,
    # fetch all answers and remove the ones without a question,
    # then return the answers respective to the limit and page.
    # Don't do this if the number of answers fetched is less than
    # the fetch limit.
    answers_count = len(answers)
    if answers_count == limit and len(user_answers) < answers_count:
        answers = util_discussion.get_all_feedback_by_author(
            discussion_models.FeedbackType.Answer,
            user_data, sort)

        user_answers = filter(lambda x: x is not None,
            [util_discussion.UserAnswer.from_answer(
            answer, viewer_data) for answer in answers])

        # Filter out answers based on the page and limit.
        start = ((page - 1) * limit)
        end = (page * limit)
        user_answers = user_answers[start:end]

    return user_answers


def get_user_comments(user_data, viewer_data, page, sort, limit=-1):
    """Returns a list of util_discussion.UserComment entities, representing a
    user's comments.

    Arguments:
        user_data: The user whose comments need to be fetched
        viewer_data: The user who is going to view the comments
        page: The desired page number (>=1)
        sort: one of possible sort orders in voting.VotingSortOrder
        limit: Upper bound for the number of comments to return
    """
    if not (1 <= limit <= 10):
        limit = 10

    comments = util_discussion.get_feedback_by_author(
        discussion_models.FeedbackType.Comment,
        user_data, page, limit, sort)

    return filter(lambda x: x is not None,
                [util_discussion.UserComment.from_comment(
                comment, viewer_data) for comment in comments])


def get_user_notifications(user_data, page, limit=-1):
    """Returns a list of util_discussion.UserQuestion entities, representing
    a user's questions. They are sorted based on most recently answered.

    Arguments:
        user_data: The user whose questions need to be fetched
        page: The desired page number (>=1)
        sort: one of possible sort orders in voting.VotingSortOrder
        limit: Upper bound for the number of notifications to return
    """
    added_question_keys = []

    # Final set of questions to return.
    user_questions = []

    # Get new notification feedback items.
    feedbacks = discussion_models.FeedbackNotification.get_feedback_for(
        user_data)

    # Sort by newest notification feedback items first.
    feedbacks = voting.VotingSortOrder.sort(feedbacks,
        voting.VotingSortOrder.NewestFirst)

    for feedback in feedbacks:
        question_key = str(feedback.question_key())
        if not question_key in added_question_keys:
            user_question = util_discussion.UserQuestion.from_question(
                feedback.question(), user_data)
            if user_question:
                added_question_keys.append(question_key)
                user_question.mark_has_unread()
                user_questions.append(user_question)

    # Get all the questions.
    questions = util_discussion.get_all_feedback_by_author(
        discussion_models.FeedbackType.Question,
        user_data)

    # Collect questions with at least one new answer.
    questions_without_updates = []

    for question in questions:
        question_key = str(question.key())
        if not question_key in added_question_keys:
            user_question = util_discussion.UserQuestion.from_question(
                question, user_data)

            if (user_question and user_question.answerer_count > 0):
                questions_without_updates.append(user_question)

    # Sort questions based on the last update.
    key_fxn = lambda entity: entity.last_updated
    questions_without_updates = sorted(questions_without_updates,
        key=key_fxn, reverse=True)

    # Append the questions without updates to the ones with updates.
    user_questions.extend(questions_without_updates)

    return {
        "questions": user_questions
    }


def get_user_discussion_statistics(user_data, viewer_data):
    """Return the discussion statistics for a user, which includes
    the number of questions, answers, comments, votes and flags cast.
    """
    statistics = {}
    statistics['questions'] = util_discussion.get_feedback_count_by_author(
        discussion_models.FeedbackType.Question, user_data, viewer_data)
    statistics['answers'] = util_discussion.get_feedback_count_by_author(
        discussion_models.FeedbackType.Answer, user_data, viewer_data)
    statistics['comments'] = util_discussion.get_feedback_count_by_author(
        discussion_models.FeedbackType.Comment, user_data, viewer_data)
    statistics['votes'] = discussion_models.FeedbackVote.count_votes_by_user(
        user_data)
    statistics['flags'] = discussion_models.FeedbackFlag.count_flags_by_user(
        user_data)
    return statistics


# TODO(ankit): Very naive for now. Make this smarter.
def get_user_question_suggestions(user_data):
    """Returns suggestions for videos on which the user might have questions,
    based on videos watched recently.
    """
    # If the user watched any videos recently, return the most recent two.
    user_videos = video_models.UserVideo.get_recently_watched_user_videos(
            user_data, 2)

    # If the user hasn't watched any videos, return the ones from the
    # suggestions list.
    if len(user_videos) == 0:
        has_watched_videos = False
        videos = suggested_activity.SuggestedActivity.get_videos_for(
                user_data)
    else:
        has_watched_videos = True
        videos = []
        for user_video in user_videos:
            video = {}
            video['name'] = user_video.video.title
            video['url'] = user_video.video.relative_url
            videos.append(video)

    return {
        'videos': videos,
        'has_watched_videos': has_watched_videos
    }


def get_user_answer_suggestions(user_data):
    """Returns suggestions for videos for which user might be able to
    answer questions, based on videos watched recently.
    """
    return get_user_question_suggestions(user_data)


def get_questions_for_video(readable_id, qa_expand_key, page, sort):
    """Get a list of util_discussion.ClientFeedback entities corresponding to
    the questions and answers below the specified video.

    Arguments:
        qa_expand_key: the key of a question to be included in the response
        page: the desired page number
        sort: one of possible sort orders in voting.VotingSortOrder
    """
    video = video_models.Video.get_for_readable_id(readable_id)
    if not video:
        return None

    user_data = user_models.UserData.current()
    count = user_data.feedback_notification_count() if user_data else 0
    restrict_posting = user_data and user_data.is_child_account()

    if qa_expand_key:
        # Clear unread answer notification for expanded question
        count = notification.clear_notification_for_question(qa_expand_key)

    if video:
        context = video_qa_context(user_data,
                                   video,
                                   page,
                                   qa_expand_key,
                                   sort)

        context['questions'] = [util_discussion.ClientFeedback.from_feedback(
                question, with_extra_vote_properties=True) for question in
                context['questions']]
        context['count_notifications'] = count
        context['temp_video_key'] = str(video.key())
        context['show_mod_controls'] = user_data and user_data.moderator
        context['restrict_posting'] = restrict_posting
        return context
    return None


def add_feedback(text, feedback_type, parent_key_or_id):
    """Add a question to a video, or an answer to a question.

    Returns a util_discussion.ClientFeedback entity for the added feedback, if
    successful, or None.

    Arguments:
        text: the desired feedback text property
        feedback_type: either FeedbackType.Question or FeedbackType.Answer
        parent_key_or_id: readable_id if adding a question, question_key if
                          adding an answer
    """
    user_data = user_models.UserData.current()
    if not util_discussion.is_post_allowed(user_data, None):
        return None

    if feedback_type == discussion_models.FeedbackType.Question:
        parent = video_models.Video.get_for_readable_id(parent_key_or_id)
    else:
        parent = db.get(parent_key_or_id)

    if parent and text:
        # TODO(drew): see if answers need to be truncated
        # Truncate feedback to a maximum length of 500 characters
        text = text[:500]

        # Grab stats before putting the feedback in case of building stats now
        # and double-counting
        stats = discussion_models.UserDiscussionStats.get_or_build_for(
            user_data)

        feedback = discussion_models.Feedback.insert_feedback(text,
            feedback_type, parent, user_data)

        stats.record(feedback)
        stats.put()

        voting.add_vote_expando_properties(feedback, {})
        return util_discussion.ClientFeedback.from_feedback(feedback,
            with_extra_vote_properties=True)

    return None


def update_feedback(feedback_key, text, feedback_type,
    parent_key_or_id=None):
    """Update the text of a question or answer.

    Returns a util_discussion.ClientFeedback entity for the added feedback, if
    successful, or None.

    Arguments:
        feedback_key: the key of feedback that is to be updated
        text: the desired feedback text property
        feedback_type: either FeedbackType.Question or FeedbackType.Answer
        parent_key_or_id: readable_id if adding a question, question_key if
                          adding an answer
    """
    user_data = user_models.UserData.current()

    # parent will only be initialized if parent_key_or_id was initialized
    if parent_key_or_id:
        parent = video_models.Video.get_for_readable_id(parent_key_or_id)

    feedback = db.get(feedback_key)

    is_answer = feedback_type == discussion_models.FeedbackType.Answer

    # TODO(drew): Do we really need to use video here?
    if feedback and text and (is_answer or parent):
        if (feedback.authored_by(user_data) or
            user_util.is_current_user_moderator()):
            feedback.content = text

            # If a moderator rewrote the content, then it's not spam.
            # Otherwise, reset the var to false (it could have turned into
            # spam)
            feedback.definitely_not_spam = (user_util.
                is_current_user_moderator())

            # Recalculate the low quality metric as the content changed
            feedback.low_quality_score = (discussion_models.
                Heuristics.get_low_quality_score(text, feedback_type))

            feedback.put()

        if is_answer:
            dict_votes = discussion_models.FeedbackVote.get_dict_for_feedback(
                feedback, user_data)

        else:
            dict_votes = (discussion_models.
                FeedbackVote.get_dict_for_user_data_and_video(
                user_data, parent))

        voting.add_vote_expando_properties(feedback, dict_votes)
        return util_discussion.ClientFeedback.from_feedback(feedback,
            with_extra_vote_properties=True)

    return None


def hide_feedback(feedback_key):
    """Hide the specified feedback entity from the general public.

    If initiated by the entity author, the entity is deleted from the
    datastore.
    If initiated by a moderator, the entity is marked as deleted and thus
    hidden from the general public but not from the author.
    """
    if not feedback_key:
        return

    feedback = db.get(feedback_key)

    if not feedback:
        return

    user_data = user_models.UserData.current()
    client_feedback = None

    stats = discussion_models.UserDiscussionStats.get_or_build_for(
        feedback.get_author())
    stats.forget(feedback)

    if feedback.authored_by(user_data):
        stats.put()
        # Entity authors can completely delete their posts. Posts that are
        # flagged as deleted by moderators won't show up as deleted to
        # authors, so we just completely delete in this special case.
        feedback.delete()
    elif user_util.is_current_user_moderator():
        feedback.deleted = True
        stats.record(feedback)
        stats.put()
        feedback.put()  # Feedback put does extra stuff so don't multi-put
        client_feedback = util_discussion.ClientFeedback.from_feedback(
            feedback)

    return client_feedback


def clear_feedback_flags(feedback_key):
    """Clear flags on the specified feedback.

    Also, undeletes the entity and sets the definitely_not_spam field to true.
    """
    feedback = db.get(feedback_key)

    if feedback:
        stats = discussion_models.UserDiscussionStats.get_or_build_for(
            feedback.get_author())
        stats.forget(feedback)
        feedback.clear_flags()
        stats.record(feedback)
        feedback.put()  # Feedback put does extra stuff so don't multi-put
        stats.put()
        return util_discussion.ClientFeedback.from_feedback(feedback)


def undelete(feedback_key):
    """Undelete specified feedback by setting the deleted field to False."""
    feedback = db.get(feedback_key)

    if feedback:
        stats = discussion_models.UserDiscussionStats.get_or_build_for(
            feedback.get_author())
        stats.forget(feedback)
        feedback.deleted = False
        stats.record(feedback)
        feedback.put()  # Feedback put does extra stuff so don't multi-put
        stats.put()
        return util_discussion.ClientFeedback.from_feedback(feedback)


def change_feedback_type(feedback_key, target_type):
    """Change feedback type to target discussion_models.FeedbackType."""
    feedback = db.get(feedback_key)

    if (not feedback or
        not discussion_models.FeedbackType.is_valid(target_type)):
        return

    stats = discussion_models.UserDiscussionStats.get_or_build_for(
        feedback.get_author())
    stats.forget(feedback)
    feedback.change_type(target_type, clear_flags=True)
    stats.record(feedback)
    stats.put()


def video_qa_context(user_data, video, page=0, qa_expand_key=None,
        sort_override=-1):
    limit_per_page = 5

    if page <= 0:
        page = 1

    sort_order = voting.VotingSortOrder.HighestPointsFirst
    if user_data:
        sort_order = user_data.question_sort_order
    if sort_override >= 0:
        sort_order = sort_override

    questions = util_discussion.get_feedback_by_type_for_video(video,
            discussion_models.FeedbackType.Question, user_data)
    questions = voting.VotingSortOrder.sort(questions, sort_order=sort_order)

    if qa_expand_key:
        # If we're showing an initially expanded question,
        # make sure we're on the correct page
        question = discussion_models.Feedback.get(qa_expand_key)
        if question:
            count_preceding = 0
            for question_test in questions:
                if question_test.key() == question.key():
                    break
                count_preceding += 1
            page = 1 + (count_preceding / limit_per_page)

    answers = util_discussion.get_feedback_by_type_for_video(video,
            discussion_models.FeedbackType.Answer, user_data)

    # Answers are initially in date descending, and we want ascending
    # before we sort by points
    answers.reverse()

    answers = voting.VotingSortOrder.sort(answers)

    dict_votes = \
            discussion_models.FeedbackVote.get_dict_for_user_data_and_video(
                    user_data, video)

    count_total = len(questions)
    start = ((page - 1) * limit_per_page)
    end = (page * limit_per_page)
    questions = questions[start:end]

    dict_questions = {}
    # Store each question in this page in a dict for answer population
    for question in questions:
        voting.add_vote_expando_properties(question, dict_votes)
        dict_questions[question.key()] = question

    # Just grab all answers for this video and cache in page's questions
    for answer in answers:
        # Grab the key only for each answer to avoid running a ful gql query
        # on the ReferenceProperty
        question_key = answer.question_key()
        if (question_key in dict_questions):
            question = dict_questions[question_key]
            voting.add_vote_expando_properties(answer, dict_votes)
            question.children_cache.append(answer)

    pages_total = max(1, ((count_total - 1) / limit_per_page) + 1)
    sorted_by_date = (sort_order == voting.VotingSortOrder.NewestFirst)

    return {
            "is_mod": user_util.is_current_user_moderator(),
            "video": video,
            "questions": questions,
            "count_total": count_total,
            "pages": range(1, pages_total + 1),
            "pages_total": pages_total,
            "prev_page_1_based": page - 1,
            "current_page_1_based": page,
            "next_page_1_based": page + 1,
            "show_page_controls": pages_total > 1,
            "qa_expand_key": qa_expand_key,
            "sorted_by_date": sorted_by_date,
           }


def add_template_values(dict, request):
    dict["comments_page"] = (int(request.get("comments_page"))
            if request.get("comments_page") else 0)
    dict["qa_page"] = (int(request.get("qa_page"))
            if request.get("qa_page") else 0)
    dict["qa_expand_key"] = request.get("qa_expand_key")
    dict["sort"] = int(request.get("sort")) if request.get("sort") else -1

    return dict
