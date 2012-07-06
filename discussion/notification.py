import os

from google.appengine.api import users
from google.appengine.ext import db

from app import App
import app
import user_util
import util
import util_discussion
import request_handler
import user_models
import discussion_models
import voting


def clear_notification_for_question(question_key, user_data=None):
    """Clear a notification, if it exists, for specified question and user.
    
    Returns:
        0 in case any of any missing data, otherwise the notification count
        for user_data after having potentially cleared a notification.
    """
    if not question_key:
        return 0

    if not user_data:
        user_data = user_models.UserData.current()
        if not user_data:
            return 0

    question = discussion_models.Feedback.get(question_key)

    if not question:
        return 0

    count = user_data.feedback_notification_count()
    should_recalculate_count = False

    answer_keys = question.children_keys()
    for answer_key in answer_keys:
        notification = discussion_models.FeedbackNotification.gql(
            "WHERE user = :1 AND feedback = :2", user_data.user, answer_key)

        if notification.count():
            should_recalculate_count = True
            db.delete(notification)

    if should_recalculate_count:
        user_data.mark_feedback_notification_count_as_stale()
        # We choose not to call user_data.feedback_notification_count()
        # right away because the FeedbackNotification indices may be stale,
        # and we want to show the user the right # when clicking through
        # an expando video-question link.
        if count > 0:
            count = count - 1

    return count
