#!/usr/bin/python
# -*- coding: utf-8 -*-
from collections import Counter
import logging

from google.appengine.ext import db
from google.appengine.ext import deferred

from app import App
from badges import util_badges
from badges.badge_triggers import BadgeTriggerType
import backup_model
import layer_cache
import object_property
import request_cache
import user_models


def _update_author_nickname(user_id):
    """Update user's feedback entities with her new nickname.

    Runs as a background task.
    """
    query = Feedback.all()
    query = query.filter('author_user_id =', user_id)

    user_data = user_models.UserData.get_from_user_id(user_id)

    updated_feedbacks = []
    batch_size = 250
    for feedback in query.run(batch_size=batch_size):
        feedback.author_nickname = user_data.nickname
        updated_feedbacks.append(feedback)
        if len(updated_feedbacks) == batch_size:
            db.put(updated_feedbacks)
            updated_feedbacks = []

    if updated_feedbacks:
        db.put(updated_feedbacks)


class FeedbackType:
    Question = 'question'
    Answer = 'answer'
    Comment = 'comment'

    @staticmethod
    def all_types():
        return [FeedbackType.Question,
                FeedbackType.Answer,
                FeedbackType.Comment]

    @staticmethod
    def is_valid(feedback_type):
        return feedback_type in FeedbackType.all_types()


class FeedbackFlag:
    # 2 or more flags immediately hides feedback
    HIDE_LIMIT = 2

    Inappropriate = 'inappropriate'
    LowQuality = 'lowquality'
    DoesNotBelong = 'doesnotbelong'
    Spam = 'spam'

    @staticmethod
    def is_valid(flag):
        return (flag == FeedbackFlag.Inappropriate or
                flag == FeedbackFlag.LowQuality or
                flag == FeedbackFlag.DoesNotBelong or
                flag == FeedbackFlag.Spam)

    @staticmethod
    def count_flags_by_user(user_data):
        query = Feedback.all()
        query.filter('flagged_by =', user_data.key_email)
        return query.count(10000)


class Feedback(backup_model.BackupModel):
    author = db.UserProperty()
    author_user_id = db.StringProperty()
    author_nickname = db.StringProperty()
    content = db.TextProperty()
    date = db.DateTimeProperty(auto_now_add=True)
    deleted = db.BooleanProperty(default=False)

    # Always includes the corresponding video's key
    # If a FeedbackType.Answer, there is a second key for the question
    targets = db.ListProperty(db.Key)

    # TODO(alpert): This always contains a single string; maybe
    # abstract over it to ensure not screwing things up?
    types = db.StringListProperty()

    is_flagged = db.BooleanProperty(default=False)

    # TODO(alpert): can this be a computed property?
    is_hidden_by_flags = db.BooleanProperty(default=False)

    flags = db.StringListProperty(default=None)
    flagged_by = db.StringListProperty(default=None)
    sum_votes = db.IntegerProperty(default=0)

    # If the entity is a question, inner_score is the sum of the entity's vote
    # count and half of the answers votes. Otherwise, it's just the entity's
    # vote count and is equal to sum_votes.
    inner_score = db.FloatProperty(default=0.0)

    # This field is calculated by combining a variety of heuristics. High
    # scores signify lower-quality posts. The score's range is [0, inf).
    low_quality_score = db.FloatProperty(default=0.0)

    # Signifies whether a moderator has approved the feedback entity
    # in the moderator queue
    definitely_not_spam = db.BooleanProperty(default=False)

    def __init__(self, *args, **kwargs):
        super(Feedback, self).__init__(*args, **kwargs)
        # For caching each question's answers during render
        self.children_cache = []

    @staticmethod
    def cache_key_for_video(video):
        return 'videofeedbackcache:%s' % video.key()

    @staticmethod
    def insert_feedback(text, feedback_type, feedback_parent, user_data):
        """Create a Feedback entity.

        Questions and comments must have videos as their parents and answers
        must have questions as their parents.

        Arguments:
            text: the question text.
            feedback_type: either FeedbackType's Question, Answer, or Comment
            feedback_parent: the video/question below which this entity was
                             posted.
            user_data: the user_data who asked the question.
        """
        feedback = Feedback(parent=user_data)
        feedback.types = [feedback_type]

        feedback.set_author(user_data)
        feedback.content = text

        if feedback_type == FeedbackType.Answer:
            feedback.targets = [feedback_parent.video_key(),
                feedback_parent.key()]
        else:
            feedback.targets = [feedback_parent.key()]

        feedback.low_quality_score = Heuristics.get_low_quality_score(text,
            feedback_type)

        if user_data.discussion_banned:
            # Hellbanned users' posts are automatically hidden
            feedback.deleted = True

        feedback.put()

        if util_badges.update_with_triggers([BadgeTriggerType.POST],
                user_data=user_data, feedback=feedback):
            user_data.put()

        # Create notification for new answers if the user isn't hellbanned
        # and if the answer author isn't the question author.
        if (feedback_type == FeedbackType.Answer and
                not user_data.discussion_banned and
                feedback.author_user_id != feedback_parent.author_user_id):
            FeedbackNotification.create_notification_for_new_answer(
                feedback_parent, feedback)

        return feedback

    @staticmethod
    def delete_answers_for(question):
        """Delete answers for a Feedback entity of type
        FeedbackType.Question.
        """
        query = Feedback.all()
        query.filter("targets = ", question.key())
        for q in query:
            stats = UserDiscussionStats.get_or_build_for(
                q.get_author())
            stats.forget(q)
            stats.put()
            q.delete()
        return

    def clear_cache_for_video(self):
        video = self.video()
        if video:
            layer_cache.ChunkedResult.delete(
                Feedback.cache_key_for_video(video), namespace=App.version,
                cache_class=layer_cache.KeyValueCache)

    def delete(self):
        """Feedback entities can only be deleted by the original author.

        They can "appear as deleted" but not actually deleted if the author
        is hellbanned or if the specific feedback was moderated as such.
        """
        # If a question is deleted, delete all the answers for that question.
        if self.is_type(FeedbackType.Question):
            Feedback.delete_answers_for(self)
        super(Feedback, self).delete()
        FeedbackNotification.delete_notifications_for_feedback(self)
        self.clear_cache_for_video()

    def put(self):
        super(Feedback, self).put()
        if self.deleted and self.is_type(FeedbackType.Answer):
            FeedbackNotification.delete_notifications_for_answer(self)

        self.clear_cache_for_video()

    def set_author(self, user_data):
        self.author = user_data.user
        self.author_nickname = user_data.nickname
        self.author_user_id = user_data.user_id

    @staticmethod
    def update_author_nickname(user_data):
        """Defer updating a user's feedback entities with her new nickname."""
        # TODO(marcia): When possible, use a backend for this feedback update,
        # since we don't want to block a user facing request with this task
        deferred.defer(_update_author_nickname, user_data.user_id,
                       _queue='slow-background-queue')

    def authored_by(self, user_data):
        return user_data and self.author == user_data.user

    def is_visible_to_public(self):
        return (not self.deleted and not self.is_hidden_by_flags)

    def is_visible_to(self, user_data):
        """Return true if this post should be visible to user_data.

        If the post has been deleted or flagged, it's only visible to the
        original author and developers.
        """
        return (self.is_visible_to_public() or
                self.authored_by(user_data) or
                (user_data and user_data.developer))

    def appears_as_deleted_to(self, user_data):
        """Return true if the post should appear as deleted to user_data.

        This should only be true for posts that are marked as deleted and
        being viewed by developers.
        """
        return (user_data and
                (user_data.developer or user_data.moderator) and
                not self.is_visible_to_public())

    @property
    def sum_votes_incremented(self):
        # Always add an extra vote when displaying vote counts to convey the
        # author's implicit "vote" and make the site a little more positive.
        return self.sum_votes + 1

    @property
    def stats_type(self):
        """Return the feedback type as far as the stat-tracking code is
        concerned. In particular, add a _hidden suffix if the feedback item is
        hidden.
        """
        ftype = self.types[0]
        if not self.is_visible_to_public():
            ftype += '_hidden'
        return ftype

    def is_type(self, type):
        return type in self.types

    def change_type(self, target_type, clear_flags=False):
        """Change the FeedbackType and optionally clear flags.

        Currently used by mods to change between comments and questions.
        """
        if FeedbackType.is_valid(target_type):
            self.types = [target_type]

            if clear_flags:
                self.clear_flags()

            self.put()

            author_user_data = user_models.UserData.get_from_user(self.author)
            if author_user_data:
                # Recalculate author's notification count since
                # comments don't have answers
                author_user_data.mark_feedback_notification_count_as_stale()

    def question_key(self):
        if self.targets:
            return self.targets[-1]  # last target is always the question
        return None

    def question(self):
        return db.get(self.question_key())

    def children_keys(self):
        keys = db.Query(Feedback, keys_only=True)
        keys.filter('targets = ', self.key())
        return keys

    def video_key(self):
        if self.targets:
            return self.targets[0]
        return None

    def video(self):
        video_key = self.video_key()
        if video_key:
            video = db.get(video_key)
            if video and video.has_topic():
                return video
        return None

    def add_vote_by(self, vote_type, user_data):
        FeedbackVote.add_vote(self, vote_type, user_data)
        self.update_votes_and_score()

    def update_votes_and_score(self):
        self.recalculate_votes()
        self.recalculate_score()
        self.put()

        if self.is_type(FeedbackType.Answer):
            question = self.question()
            if question:
                question.recalculate_score()
                question.put()

    def recalculate_votes(self):
        self.sum_votes = FeedbackVote.count_votes(self)

    def recalculate_score(self):
        score = float(self.sum_votes)

        if self.is_type(FeedbackType.Question):
            for answer in db.get(self.children_keys().fetch(1000)):
                score += 0.5 * float(answer.sum_votes)

        self.inner_score = float(score)

    def add_flag_by(self, flag_type, user_data):
        if user_data.key_email in self.flagged_by:
            return False

        self.flags.append(flag_type)
        self.flagged_by.append(user_data.key_email)
        self.recalculate_flagged()
        return True

    def clear_flags(self):
        self.deleted = False
        self.flags = []
        self.flagged_by = []
        self.recalculate_flagged()

        # Once an entity's flags have been cleared, it will not appear in the
        # moderator queue anymore and will not be able to be flagged again
        self.definitely_not_spam = True

    def recalculate_flagged(self):
        num_times_flagged = len(self.flags or [])
        self.is_flagged = num_times_flagged > 0
        self.is_hidden_by_flags = num_times_flagged >= FeedbackFlag.HIDE_LIMIT

    def get_author_user_id(self):
        if self.author_user_id is not None:
            return self.author_user_id
        else:
            user_data = user_models.UserData.get_from_user(self.author)
            if user_data is not None:
                return user_data.user_id
            else:
                return ''

    def get_author(self):
        return user_models.UserData.get_from_user_id(self.author_user_id)


class Heuristics(object):
    """Hold functions that automatically classify a discussion entity's
    low-quality measure using heuristics when it is posted to the site.

    New heuristics can be added in get_low_quality_score().
    """

    @staticmethod
    def get_low_quality_score(text, feedback_type):
        """Combine a variety of heuristics to make a low-quality score.

        High scores signify lower-quality posts. Value's range: (0, inf).
        """

        # TODO(drew): Division by zero with empty posts?
        # TODO(drew): What's the smallest value possible?
        # TODO(drew): Consider linebreaks.
        # TODO(drew): Consider phrases like "Copy and paste".

        # The following is an array of functions and their corresponding
        # weights (grouped together as tuples). The functions take the
        # entity's text and feedback_type as arguments, and return a number.
        COMPONENTS_AND_WEIGHTS = [
            (Heuristics.upper_lower_ratio, 0.01),
            (Heuristics.longest_repeat, 5),
            (Heuristics.occurrences('vote'), 10),
            (Heuristics.occurrences('lol'), 100),
            (Heuristics.length(comments=1, questions=20, answers=20), 1)
        ]

        # Run each function from COMPONENTS_AND_WEIGHTS and add the return
        # value (multiplied by the corresponding weight) to the score.
        score = 0
        for pair in COMPONENTS_AND_WEIGHTS:
            fnc, weight = pair
            score += fnc(text, feedback_type) * weight
        return score

    @staticmethod
    def upper_lower_ratio(text, feedback_type):
        """Find the difference between the uppercase-to-lowercase ratio in
        English books (http://english.stackexchange.com/questions/43563)
        and in this text.

        The difference is multiplied by the length of the text. Thus, shorter
        entities that don't match the desired uppercase-to-lowercase ratio
        exactly won't be penalized too heavily.

        Entities that are all uppercase are given an extra penalty.
        """
        upper, lower = 0, 0
        for c in text:
            if c.islower():
                lower += 1
            elif c.isupper():
                upper += 1

        if lower == 0:
            return upper * 10
        else:
            return abs(0.026 - upper / lower) * float(len(text))

    @staticmethod
    def longest_repeat(text, feedback_type):
        """Get length of longest repeated character string, represented as a
        fraction of the entire text's length.

        Ignore digits, spaces, and hyphens.
        """
        longest = 1
        count = 0
        char = ''
        for c in text:
            if (c == char and not c.isdigit() and not c.isspace() and
                c != '-'):
                count += 1
            else:
                count = 1
            longest = max(count, longest)
            char = c
        return longest / float(len(text))

    @staticmethod
    def occurrences(phrase):
        """Generate a function that returns the ratio of the number of
        occurrences of a given phrase to the entire text length.

        Arguments:
            phrase: the phrase to count occurrences of
        """
        def get_occurrences(text, feedback_type):
            return text.count(phrase) / float(len(text))

        return get_occurrences

    @staticmethod
    def length(comments, questions, answers):
        """Generate a function that returns (x / length) where x is a number
        derived by the feedback entity's type and 'length' is the text length.

        This is used for penalizing shorter entities.

        Arguments:
            comments: value of x for comments
            questions: value of x for questions
            answers: value of x for answers
        """
        def get_length(text, feedback_type):
            length_ = float(len(text))

            if feedback_type == FeedbackType.Comment:
                return comments / length_
            elif feedback_type == FeedbackType.Question:
                return questions / length_
            else:
                return answers / length_

        return get_length


class FeedbackNotification(db.Model):
    """ A FeedbackNotification entity is created for each answer to a
    question, unless the question and answer authors are the same user
    """
    # The answer that provoked a notification
    feedback = db.ReferenceProperty(Feedback)

    # The question author and recipient of the notification
    user = db.UserProperty()

    @staticmethod
    def create_notification_for_new_answer(question, answer):
        notification = FeedbackNotification()
        notification.user = question.author
        notification.feedback = answer

        user_data = user_models.UserData.get_from_db_key_email(
                notification.user.email())
        if not user_data:
            return

        notification.put()
        user_data.mark_feedback_notification_count_as_stale()

    @staticmethod
    def delete_notifications_for_feedback(feedback):
        if feedback.is_type(FeedbackType.Question):
            FeedbackNotification.delete_notifications_for_question(feedback)
        elif feedback.is_type(FeedbackType.Answer):
            FeedbackNotification.delete_notifications_for_answer(feedback)

    @staticmethod
    def delete_notifications_for_question(question):
        if not question:
            return

        answer_keys = question.children_keys()
        for answer_key in answer_keys:
            answer = db.get(answer_key)
            FeedbackNotification.delete_notifications_for_answer(answer)

    @staticmethod
    def delete_notifications_for_answer(answer):
        if not answer:
            return

        query = FeedbackNotification.all()
        query.filter('feedback =', answer)
        notification = query.get()

        if not notification:
            return

        user_data = user_models.UserData.get_from_user(notification.user)
        user_data.mark_feedback_notification_count_as_stale()

        notification.delete()

    @staticmethod
    def get_feedback_for(user_data):
        """Get feedback corresponding to notifications for a user."""
        all_feedback = []
        notifications = FeedbackNotification.gql("WHERE user = :1",
                                                 user_data.user)

        for notification in notifications:
            feedback = None
            try:
                feedback = notification.feedback
                all_feedback.append(feedback)
            except db.ReferencePropertyResolveError:
                # TODO(marcia): We error here because we didn't delete
                # associated notifications when an answer was deleted.
                # Fixed 19 Apr 2012 and will be cleaned up organically or we
                # could run a MR job.
                notification_id = notification.key().id()
                message = ('Reference error w FeedbackNotification: %s' %
                            notification_id)
                logging.warning(message)

                notification.delete()

        return all_feedback


class FeedbackVote(db.Model):
    DOWN = -1
    ABSTAIN = 0
    UP = 1

    # Feedback reference stored in parent property
    video = db.ReferenceProperty()
    user = db.UserProperty()
    vote_type = db.IntegerProperty(default=0)

    @staticmethod
    def add_vote(feedback, vote_type, user_data):
        if not feedback or not user_data:
            return

        vote = FeedbackVote.get_or_insert(
                key_name='vote_by_%s' % user_data.key_email,
                parent=feedback,
                video=feedback.video_key(),
                user=user_data.user,
                vote_type=vote_type)

        if vote and vote.vote_type != vote_type:
            # If vote already existed and user has changed vote, update
            vote.vote_type = vote_type
            vote.put()

    @staticmethod
    @request_cache.cache_with_key_fxn(
            lambda user_data, video: 'voting_dict_for_%s' % video.key())
    def get_dict_for_user_data_and_video(user_data, video):

        if not user_data:
            return {}

        query = FeedbackVote.all()
        query.filter('user =', user_data.user)
        query.filter('video =', video)
        votes = query.fetch(1000)

        dict = {}
        for vote in votes:
            dict[vote.parent_key()] = vote

        return dict

    @staticmethod
    def get_dict_for_feedback(feedback, user_data):
        """Return a dict with one entry where the key is the feedback's key
        and the value is the FeedbackVote entity corresponding to the user's
        vote, or an empty dict if the user didn't cast a vote.
        """
        if not feedback or not user_data:
            return {}

        query = FeedbackVote.all().ancestor(feedback).filter('user =',
                                                             user_data.user)
        feedback_vote = query.get()

        if feedback_vote:
            return {
                feedback_vote.parent_key(): feedback_vote,
            }

        return {}

    @staticmethod
    def count_votes(feedback):
        if not feedback:
            return 0

        query = FeedbackVote.all()
        query.ancestor(feedback)
        votes = query.fetch(100000)

        count_up = len(filter(lambda vote: vote.is_up(), votes))
        count_down = len(filter(lambda vote: vote.is_down(), votes))

        return count_up - count_down

    @staticmethod
    def count_votes_by_user(user_data):
        if not user_data:
            return 0

        query = FeedbackVote.all()
        query.filter('user =', user_data.user)
        return query.count(10000)

    def is_up(self):
        return self.vote_type == FeedbackVote.UP

    def is_down(self):
        return self.vote_type == FeedbackVote.DOWN


class UserDiscussionStats(backup_model.BackupModel):
    """Hold statistics for each user for how many feedback items (by type)
    have some number votes. Example:

        vote_frequencies[FeedbackType.Answer] = {
            2: 7,
            3: 2,
        }

    means that the user has

        * 7 answers with sum_votes = 2 and
        * 2 answers with sum_votes = 3.

    The author's implicit vote is ignored.
    """

    # the parent entity is the associated UserData

    vote_frequencies = object_property.ObjectProperty()

    @staticmethod
    def get_or_build_for(user_data):
        """Return the UserDiscussionStats for a user, if it exists, creating it
        from scratch if it does not.
        """
        stats = UserDiscussionStats._get_for(user_data)

        if stats is None:
            stats = UserDiscussionStats._build_for(user_data)
            stats.put()

        return stats

    @staticmethod
    def _key_name(user_data):
        return 'stats:%s' % user_data.user_id

    @staticmethod
    def _get_for(user_data):
        """Return the UserDiscussionStats for a user, if it exists."""
        return UserDiscussionStats.get_by_key_name(
            UserDiscussionStats._key_name(user_data),
            parent=user_data)

    @staticmethod
    def _build_for(user_data):
        """Return a new freshly-updated UserDiscussionStats for a user."""
        stats = UserDiscussionStats(
            key_name=UserDiscussionStats._key_name(user_data),
            parent=user_data,
            vote_frequencies={})
        stats._update()
        return stats

    def _update(self):
        """Update vote_frequencies using all Feedback items for a user."""
        user_data = self.parent()
        freq = self.vote_frequencies

        for feedback_type in FeedbackType.all_types():
            if feedback_type not in freq:
                freq[feedback_type] = {}
            if feedback_type + '_hidden' not in freq:
                freq[feedback_type + '_hidden'] = {}

        query = Feedback.all()
        query.filter('author_user_id =', user_data.user_id)

        for feedback in query.run(batch_size=1000):
            ftype = feedback.stats_type
            votes = int(feedback.sum_votes)
            old = freq[ftype].get(votes, 0)
            freq[ftype][votes] = old + 1

        self._normalize_vote_frequencies()

    def record(self, feedback):
        """Record stats for a feedback entity -- call right after creation.

        Also see forget.

        You can also do fancier things like:
            stats.forget(feedback)
            feedback.add_vote_by(...)
            stats.record(feedback)
        """
        self._add_to_vote_frequencies({
            feedback.stats_type: {feedback.sum_votes: 1}
        })

    def forget(self, feedback):
        """Forget stats for a feedback entity -- call right before deletion.
        Also see record.
        """
        self._add_to_vote_frequencies({
            feedback.stats_type: {feedback.sum_votes: -1}
        })

    def _add_to_vote_frequencies(self, new_freq):
        """Update vote_frequencies by "adding" a dictionary to it, matching up
        the feedback types and vote counts. You probably want to use the
        record/forget functions instead.
        """
        for ftype in new_freq:
            # Use collections.Counter to add frequency dictionaries
            self.vote_frequencies[ftype] = dict(
                Counter(self.vote_frequencies.get(ftype, {})) +
                Counter(new_freq[ftype]))

        self._normalize_vote_frequencies()

    def _normalize_vote_frequencies(self):
        """From each frequency dictionary, delete nonpositive entries, then
        delete empty dictionaries by type.
        """
        for ftype, freqs in self.vote_frequencies.items():
            for v, f in freqs.items():
                if f <= 0:
                    del freqs[v]
            if freqs == {}:
                del self.vote_frequencies[ftype]

    def count_of_type(self, ftype, include_hidden):
        """Return the number of feedback items of the given type a user has.

        Example:
            stats = discussion_models.UserDiscussionStats.get_for(user_data)
            print stats.count_of_type(
                discussion_models.FeedbackType.Answer, True)
        """
        count = sum(self.vote_frequencies.get(ftype, {}).values())
        if include_hidden:
            count += self.count_of_type(ftype + '_hidden', False)
        return count
