import logging
import datetime
import sys

from google.appengine.ext import db

# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

from third_party.mapreduce import control

from api.jsonify import jsonify
import badges
import custom_badges
import exercise_models
import last_action_cache
import layer_cache
import models_badges
import notifications
import setting_model
import topic_exercise_badges
import topic_models
import user_models

# Import the modules containing each badge so that all of the @active_badge
# decorators get run and thus badges.static_badges is properly populated.
import consecutive_activity_badges  # @UnusedImport
import discussion_badges  # @UnusedImport
import discussion_quality_count_badges  # @UnusedImport
import exercise_completion_badges  # @UnusedImport
import exercise_completion_count_badges  # @UnusedImport
import feedback_badges  # @UnusedImport
import points_badges  # @UnusedImport
import power_time_badges  # @UnusedImport
import profile_badges  # @UnusedImport
import recovery_problem_badges  # @UnusedImport
import streak_badges  # @UnusedImport
import tenure_badges  # @UnusedImport
import timed_problem_badges  # @UnusedImport
import topic_time_badges  # @UnusedImport
import unfinished_exercise_badges  # @UnusedImport
import video_time_badges  # @UnusedImport


@layer_cache.cache_with_key_fxn(lambda: "all_badges:%s"
                                % setting_model.Setting.topic_tree_version())
def all_badges():
    """Authoritative list of all badges."""

    # Add custom badges and topic exercise badges, which both correspond
    # to datastore entities, to the collection of all badges.
    return (badges.static_badges +
        custom_badges.CustomBadge.all() +
        topic_exercise_badges.TopicExerciseBadge.all())


@layer_cache.cache_with_key_fxn(lambda: "all_badges_dict:%s"
                                % setting_model.Setting.topic_tree_version())
def all_badges_dict():
    return dict((b.name, b) for b in all_badges())


@layer_cache.cache_with_key_fxn(lambda: "all_badges_slug_dict:%s"
                                % setting_model.Setting.topic_tree_version())
def all_badges_slug_dict():
    return dict((b.slug, b) for b in all_badges())


def badges_with_context_type(badge_context_type):
    return filter(lambda badge: badge.badge_context_type
                    == badge_context_type, all_badges())


def badges_with_triggers(badge_triggers):
    """Return badges which list a badge trigger in common with the argument
    badge_triggers.

    For example,
        badges_with_triggers([BadgeTriggerType.VOTE,
                              BadgeTriggerType.POST])
    gives all badges which list either VOTE or POST as an trigger.
    """
    badge_triggers = set(badge_triggers)
    return [badge for badge in all_badges() if badge.badge_triggers &
            badge_triggers]


def get_badge_counts(user_data):

    count_dict = badges.BadgeCategory.empty_count_dict()

    if not user_data:
        return count_dict

    badges_dict = all_badges_dict()

    for badge_name_with_context in user_data.badges:
        badge_name = (badges.Badge
                        .remove_target_context(badge_name_with_context))
        badge = badges_dict.get(badge_name)
        if badge:
            count_dict[badge.badge_category] += 1

    return count_dict


def get_badge_notifications_json():
    """ Retrieves the list of UserBadge objects just earned by the current
        user. Returns a jsonified list of the associated badge objects.
    """
    notifications_dict = notifications.Notifier.pop()

    badge_names = [n.badge_name for n in notifications_dict["badges"]]
    if len(badge_names) <= 0:
        return None

    return jsonify({"badges": get_badges(badge_names)}, camel_cased=True)


def get_badges(badge_names):
    """Return badge objects corresponding to list of badge names."""
    return [all_badges_dict().get(b) for b in badge_names]


def get_grouped_user_badges(user_data=None):
    """ Retrieves the list of user-earned badges grouped into GroupedUserBadge
    objects. Also returns the list of possible badges along with them.

    """

    if not user_data:
        user_data = user_models.UserData.current()

    user_badges = []
    grouped_badges_dict = {}

    if user_data:
        user_badges = models_badges.UserBadge.get_for(user_data)
        badges_dict = all_badges_dict()
        grouped_user_badge = None
        for user_badge in user_badges:
            if (grouped_user_badge and
                    grouped_user_badge.badge.name == user_badge.badge_name):
                grouped_user_badge.target_context_names.append(
                    user_badge.target_context_name)
            else:
                badge = badges_dict.get(user_badge.badge_name)
                if badge is None:
                    logging.warning("Can't find reference badge named %s" %
                                    user_badge.badge_name)
                    continue
                badge.is_owned = True
                grouped_user_badge = badges.GroupedUserBadge.build(user_data,
                                                                   badge,
                                                                   user_badge)
                grouped_badges_dict[user_badge.badge_name] = grouped_user_badge

    possible_badges = sorted(all_badges(),
                             key=lambda badge: badge.badge_category)
    for badge in possible_badges:
        badge.is_owned = badge.name in grouped_badges_dict
        badge.can_become_goal = (user_data and not user_data.is_phantom
                                    and not badge.is_owned and badge.is_goal)
        if badge.can_become_goal:
            badge.objectives = json.dumps(badge.exercise_names_required)

    possible_badges = filter(lambda badge: not badge.is_hidden(),
                            possible_badges)

    grouped_user_badges = sorted(
            filter(lambda group: (hasattr(group, "badge") and
                                  group.badge is not None),
                   grouped_badges_dict.values()),
            reverse=True,
            key=lambda group: group.last_earned_date)

    def filter_by_category(category):
        return filter(lambda group: group.badge.badge_category == category,
                      grouped_user_badges)

    user_badges_normal = filter(lambda group: group.badge.badge_category
                                    != badges.BadgeCategory.MASTER,
                                grouped_user_badges)
    user_badges_master = filter_by_category(badges.BadgeCategory.MASTER)
    user_badges_diamond = filter_by_category(badges.BadgeCategory.DIAMOND)
    user_badges_platinum = filter_by_category(badges.BadgeCategory.PLATINUM)
    user_badges_gold = filter_by_category(badges.BadgeCategory.GOLD)
    user_badges_silver = filter_by_category(badges.BadgeCategory.SILVER)
    user_badges_bronze = filter_by_category(badges.BadgeCategory.BRONZE)

    def filter_and_sort(category):
        return sorted(filter(lambda badge: badge.badge_category == category,
                             possible_badges),
                      key=lambda badge: badge.points or sys.maxint)

    bronze_badges = filter_and_sort(badges.BadgeCategory.BRONZE)
    silver_badges = filter_and_sort(badges.BadgeCategory.SILVER)
    gold_badges = filter_and_sort(badges.BadgeCategory.GOLD)
    platinum_badges = filter_and_sort(badges.BadgeCategory.PLATINUM)
    diamond_badges = filter_and_sort(badges.BadgeCategory.DIAMOND)
    master_badges = filter_and_sort(badges.BadgeCategory.MASTER)

    return {'possible_badges': possible_badges,
            'user_badges_normal': user_badges_normal,
            'user_badges_master': user_badges_master,
            "badge_collections": [bronze_badges, silver_badges,
                                     gold_badges, platinum_badges,
                                     diamond_badges, master_badges],
            'bronze_badges': user_badges_bronze,
            'silver_badges': user_badges_silver,
            'gold_badges': user_badges_gold,
            'platinum_badges': user_badges_platinum,
            'diamond_badges': user_badges_diamond}

EMPTY_BADGE_NAME = "__empty__"
NUM_PUBLIC_BADGE_SLOTS = 5


def get_public_user_badges(user_data=None):
    """ Retrieves the list of user-earned badges that the user has selected
    to publicly display on his/her profile display-case.
    This is returned as a list of Badge objects, and not UserBadge objects
    and therefore does not contain further information about the user's
    activities.

    """
    if not user_data:
        user_data = user_models.UserData.current()
        if not user_data:
            return []

    public_badges = user_data.public_badges or []
    full_dict = all_badges_dict()
    results = []
    for name in public_badges:
        if name in full_dict:
            results.append(full_dict[name])
        else:
            # assert - name is "__empty__"
            results.append(None)  # empty slot
    return results


def get_user_discussion_badges(user_data):
    """Returns the discussion badges earned by the user,
    sorted from more prestigious to less prestigious.
    """
    # TODO(ankit): Find a less static way to fetch
    # the discussion badges.
    discussion_badges_list = [
        feedback_badges.LevelOneAnswerVoteCountBadge(),
        feedback_badges.LevelTwoAnswerVoteCountBadge(),
        feedback_badges.LevelThreeAnswerVoteCountBadge(),

        feedback_badges.LevelOneQuestionVoteCountBadge(),
        feedback_badges.LevelTwoQuestionVoteCountBadge(),
        feedback_badges.LevelThreeQuestionVoteCountBadge(),

        discussion_badges.FirstFlagBadge(),
        discussion_badges.FirstUpVoteBadge(),
        discussion_badges.FirstDownVoteBadge(),
        discussion_badges.ModeratorBadge(),

        discussion_quality_count_badges.LevelOneAnswerQualityCountBadge(),
        discussion_quality_count_badges.LevelTwoAnswerQualityCountBadge(),
        discussion_quality_count_badges.LevelOneQuestionQualityCountBadge(),
        discussion_quality_count_badges.LevelTwoQuestionQualityCountBadge(),
    ]

    discussion_badges_map = {}

    for badge in discussion_badges_list:
        discussion_badges_map[badge.name] = badge

    badges = models_badges.UserBadge.get_for(user_data)

    # Only discussion badges.
    user_badges_dict = {}

    for badge in badges:
        badge_name = badge.badge_name

        if badge_name in discussion_badges_map:
            discussion_badge = discussion_badges_map[badge_name]

            if badge_name in user_badges_dict:
                user_badges_dict[badge_name]['count'] += 1
                user_badges_dict[badge_name]['multiple'] = True

                try:
                    if badge.target_context:
                        user_badges_dict[badge_name][
                            'feedback_keys'].append(badge.target_context.key())
                except db.ReferencePropertyResolveError:
                    pass
            else:
                user_badge = {}
                user_badge['icon_src'] = discussion_badge.icon_src
                user_badge['absolute_url'] = discussion_badge.absolute_url
                user_badge['description'] = (
                    discussion_badge.safe_extended_description)
                user_badge['name'] = discussion_badge.description
                user_badge['category'] = discussion_badge.badge_category
                user_badge['count'] = 1
                user_badge['multiple'] = False

                # Do a silent fail in case of a
                # db.ReferencePropertyResolveError error.
                # Occurs when the badge has a dangling reference to a
                # feedback item that was deleted.
                try:
                    if badge.target_context:
                        user_badge['feedback_keys'] = [
                            badge.target_context.key()]
                except db.ReferencePropertyResolveError:
                    # TODO(ankit): Maybe set target_context to None here?
                    pass

                user_badges_dict[badge_name] = user_badge

    user_discussion_badges = user_badges_dict.values()

    # Sort the badges from more prestigious -> less prestigious.
    key_fxn = lambda entity: entity['category']
    user_discussion_badges = sorted(
        user_discussion_badges, key=key_fxn, reverse=True)

    return user_discussion_badges


def start_new_badge_mapreduce():
    """Start a new Mapper task for calling badge_update_map."""
    return control.start_map(
        name="UpdateUserBadges",
        handler_spec="badges.util_badges.badge_update_map",
        reader_spec=(
            "third_party.mapreduce.input_readers.DatastoreInputReader"),
        mapper_parameters={
            "input_reader": {"entity_kind": "user_models.UserData"},
            },
        mapreduce_parameters={"processing_rate": 250},
        shard_count=64,
        queue_name="user-badge-queue"
        )


def is_badge_review_waiting(user_data):
    if not user_data:
        return False

    if not user_data.user:
        return False

    if not user_data.user_id:
        logging.error("UserData with user and no current_user: %s"
                        % user_data.email)
        return False

    if user_data.is_phantom:
        # Don't bother doing overnight badge reviews for phantom users --
        # we're not that worried about it, and it reduces task queue stress.
        return False

    if (not user_data.last_activity
        or (user_data.last_badge_review
            and user_data.last_activity <= user_data.last_badge_review)):
        # No activity since last badge review, skip
        return False

    return True


def badge_update_map(user_data):
    if not is_badge_review_waiting(user_data):
        return

    action_cache = (last_action_cache.LastActionCache
                    .get_for_user_data(user_data))

    # Update all no-context badges
    update_with_no_context(user_data, action_cache=action_cache)

    # Update all exercise-context badges
    for user_exercise in (exercise_models.UserExercise
                            .get_for_user_data(user_data)):
        update_with_user_exercise(user_data, user_exercise,
                                    action_cache=action_cache)

    # Update all topic-context badges
    for user_topic in topic_models.UserTopic.get_for_user_data(user_data):
        update_with_user_topic(user_data, user_topic,
                                action_cache=action_cache)

    user_data.last_badge_review = datetime.datetime.now()
    user_data.put()


# Award this user any earned no-context badges.
def update_with_no_context(user_data, action_cache=None):
    possible_badges = badges_with_context_type(badges.BadgeContextType.NONE)
    action_cache = action_cache or (last_action_cache.LastActionCache
                                    .get_for_user_data(user_data))

    awarded = False
    for badge in possible_badges:
        if badge.is_manually_awarded():
            continue
        if not badge.is_already_owned_by(user_data=user_data):
            if badge.is_satisfied_by(user_data=user_data,
                                    action_cache=action_cache):
                badge.award_to(user_data=user_data)
                awarded = True

    return awarded


# Award user any earned Exercise-context badges for provided UserExercise.
def update_with_user_exercise(user_data, user_exercise,
                              include_other_badges=False,
                              action_cache=None):
    possible_badges = badges_with_context_type(badges
                                               .BadgeContextType.EXERCISE)
    action_cache = action_cache or (last_action_cache.LastActionCache
                                    .get_for_user_data(user_data))

    awarded = False
    for badge in possible_badges:
        if badge.is_manually_awarded():
            continue
        # Pass in pre-retrieved user_exercise data so each badge check
        # doesn't have to talk to the datastore
        if not badge.is_already_owned_by(user_data=user_data,
                                         user_exercise=user_exercise):
            if badge.is_satisfied_by(user_data=user_data,
                                     user_exercise=user_exercise,
                                     action_cache=action_cache):
                badge.award_to(user_data=user_data,
                               user_exercise=user_exercise)
                awarded = True

    if include_other_badges:
        awarded = update_with_no_context(user_data,
                                         action_cache=action_cache) or awarded

    return awarded


# Award this user any earned Topic-context badges for the provided UserTopic.
def update_with_user_topic(user_data, user_topic, include_other_badges=False,
                            action_cache=None):
    possible_badges = badges_with_context_type(badges.BadgeContextType.TOPIC)
    action_cache = action_cache or (last_action_cache.LastActionCache
                                    .get_for_user_data(user_data))

    awarded = False
    for badge in possible_badges:
        if badge.is_manually_awarded():
            continue
        # Pass in pre-retrieved user_topic data so each badge check doesn't
        # have to talk to the datastore
        if not badge.is_already_owned_by(user_data=user_data,
                                            user_topic=user_topic):
            if badge.is_satisfied_by(user_data=user_data,
                                    user_topic=user_topic,
                                    action_cache=action_cache):
                badge.award_to(user_data=user_data, user_topic=user_topic)
                awarded = True

    if include_other_badges:
        awarded = (update_with_no_context(user_data, action_cache=action_cache)
                    or awarded)

    return awarded


def update_with_triggers(triggers, **kwargs):
    """Award any badges with the given trigger type, passing the kwargs (which
    should include user_data and may include other things depending on the
    trigger) to is_already_owned_by, is_satisfied_by, and award_to.
    """
    awarded = False

    for badge in badges_with_triggers(triggers):
        if not badge.is_already_owned_by(**kwargs):
            if badge.is_satisfied_by(**kwargs):
                badge.award_to(**kwargs)
                awarded = True

    return awarded
