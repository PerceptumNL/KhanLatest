import urllib

from google.appengine.ext import db
from google.appengine.api import taskqueue
from third_party.mapreduce import control

import discussion_models
from privileges import Privileges
from rate_limiter import VoteRateLimiter
import request_handler
from user_models import UserData
import user_util

from badges import util_badges
from badges.badge_context import BadgeContextType
from badges.badge_triggers import BadgeTriggerType
from badges.discussion_badges import FirstUpVoteBadge, FirstDownVoteBadge


class VotingSortOrder:
    HighestPointsFirst = 1
    NewestFirst = 2

    @staticmethod
    def sort(entities, sort_order=-1):
        if not sort_order in (VotingSortOrder.HighestPointsFirst,
                              VotingSortOrder.NewestFirst):
            sort_order = VotingSortOrder.HighestPointsFirst

        key_fxn = None

        if sort_order == VotingSortOrder.NewestFirst:
            key_fxn = lambda entity: entity.date
        else:
            key_fxn = lambda entity: entity.inner_score

        # Sort by desired sort order, then put hidden entities at end
        return sorted(sorted(entities, key=key_fxn, reverse=True),
                      key=lambda entity: entity.is_visible_to_public(),
                      reverse=True)


class UpdateQASort(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        user_data = UserData.current()
        sort = self.request_int("sort",
                                default=VotingSortOrder.HighestPointsFirst)

        if user_data:
            user_data.question_sort_order = sort
            user_data.put()

        readable_id = self.request_string("readable_id", default="")
        topic_title = self.request_string("topic_title", default="")

        if readable_id and topic_title:
            self.redirect("/video/%s?topic=%s&sort=%s" % (
                urllib.quote(readable_id), urllib.quote(topic_title), sort))
        else:
            self.redirect("/")


class VoteEntity(request_handler.RequestHandler):
    # You have to be logged in to vote
    @user_util.login_required_and(phantom_user_allowed=False)
    def post(self):
        user_data = UserData.current()
        if not user_data:
            return

        if user_data.is_child_account():
            self.render_json({"error": "You cannot vote yet."})
            return

        vote_type = self.request_int(
            "vote_type", default=discussion_models.FeedbackVote.ABSTAIN)

        if (vote_type == discussion_models.FeedbackVote.UP and
            not Privileges.can_up_vote(user_data)):
            self.render_json({
                "error": Privileges.need_points_desc(
                    Privileges.UP_VOTE_THRESHOLD, "up vote")
            })
            return
        elif (vote_type == discussion_models.FeedbackVote.DOWN and
              not Privileges.can_down_vote(user_data)):
            self.render_json({
                "error": Privileges.need_points_desc(
                    Privileges.DOWN_VOTE_THRESHOLD, "down vote")
            })
            return

        entity_key = self.request_string("entity_key", default="")
        if entity_key:
            entity = db.get(entity_key)
            if entity and entity.authored_by(user_data):
                self.render_json({
                    "error": "You cannot vote for your own posts."
                })
                return

        if vote_type != discussion_models.FeedbackVote.ABSTAIN:
            limiter = VoteRateLimiter(user_data)
            if not limiter.increment():
                self.render_json({"error": limiter.denied_desc()})
                return

        # We kick off a taskqueue item to perform the actual vote insertion
        # so we don't have to worry about fast writes to the entity group
        # causing contention problems for the HR datastore, because
        # the taskqueue will just retry w/ exponential backoff.
        # TODO(marcia): user_data.email may change. user_id is preferred
        taskqueue.add(
            url='/admin/discussion/finishvoteentity',
            queue_name='voting-queue',
            params={
                "email": user_data.email,
                "vote_type": self.request_int(
                    "vote_type",
                    default=discussion_models.FeedbackVote.ABSTAIN),
                "entity_key": entity_key
            }
        )


class FinishVoteEntity(request_handler.RequestHandler):
    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def post(self):
        user_data = self.request_user_data("email")
        if not user_data:
            return

        vote_type = self.request_int(
            "vote_type", default=discussion_models.FeedbackVote.ABSTAIN)

        key = self.request_string("entity_key", default="")
        if key:
            entity = db.get(key)
            if entity:
                FinishVoteEntity.perform_vote(entity, vote_type, user_data)

    @staticmethod
    def perform_vote(feedback, vote_type, voter):
        """Add a vote, updating stats and awarding associated badges."""
        author = feedback.get_author()

        # Sometimes Feedbacks don't have authors :(
        if author:
            stats = discussion_models.UserDiscussionStats.get_or_build_for(
                author)
            stats.forget(feedback)

        feedback.add_vote_by(vote_type, voter)

        if author:
            stats.record(feedback)
            stats.put()

            FinishVoteEntity.award_author_badges(feedback, author, stats)

        FinishVoteEntity.award_voter_badges(vote_type, voter)

    @staticmethod
    def award_voter_badges(vote_type, user_data):
        awarded = False

        if vote_type == discussion_models.FeedbackVote.UP:
            if not FirstUpVoteBadge().is_already_owned_by(user_data):
                FirstUpVoteBadge().award_to(user_data)
                awarded = True
        elif vote_type == discussion_models.FeedbackVote.DOWN:
            if not FirstDownVoteBadge().is_already_owned_by(user_data):
                FirstDownVoteBadge().award_to(user_data)
                awarded = True

        if awarded:
            user_data.put()

    @staticmethod
    def award_author_badges(entity, author, author_stats):
        awarded = util_badges.update_with_triggers(
            [BadgeTriggerType.VOTEE],
            user_data=author, user_discussion_stats=author_stats)

        possible_badges = util_badges.badges_with_context_type(
            BadgeContextType.FEEDBACK)

        for badge in possible_badges:
            if not badge.is_already_owned_by(
                    user_data=author, feedback=entity):
                if badge.is_satisfied_by(
                        user_data=author, feedback=entity):
                    badge.award_to(user_data=author, feedback=entity)
                    awarded = True

        if awarded:
            author.put()


class StartNewVoteMapReduce(request_handler.RequestHandler):

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def get(self):

        # Admin-only restriction is handled by /admin/* URL pattern
        # so this can be called by a cron job.

        # Start a new Mapper task for calling badge_update_map
        mapreduce_id = control.start_map(
            name="UpdateFeedbackVotes",
            handler_spec="discussion.voting.vote_update_map",
            reader_spec=(
                "third_party.mapreduce.input_readers.DatastoreInputReader"),
            mapper_parameters={
                "input_reader": {"entity_kind":
                                 "discussion.discussion_models.Feedback"},
                },
            queue_name="backfill-mapreduce-queue",
            )

        self.response.out.write("OK: " + str(mapreduce_id))


def vote_update_map(feedback):
    feedback.update_votes_and_score()


def add_vote_expando_properties(feedback, dict_votes):
    feedback.up_voted = False
    feedback.down_voted = False
    if feedback.key() in dict_votes:
        vote = dict_votes[feedback.key()]
        feedback.up_voted = vote.is_up()
        feedback.down_voted = vote.is_down()
