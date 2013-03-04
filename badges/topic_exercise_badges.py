from google.appengine.ext import db

import object_property
import topic_models
import url_util
from badges import Badge, BadgeCategory
import logging

def sync_with_topic_version(version):
    """ Syncs state of all TopicExerciseBadges with the specified
    TopicVersion's topic tree. This'll add new badges for any new topics
    that have exercises, retire badges associated with topics that no longer
    contain exercises, and keep all constituent exercise names up-to-date.
    """

    # Get all topics with live exercises as direct children
    topics = topic_models.Topic.get_exercise_topics(version)

    entities_to_put = []

    # Make sure there is a TopicExerciseBadgeType for every topic
    # that contains exercises
    for topic in topics:
        logging.info("sync topic %s" % topic.title)

        badge_type = TopicExerciseBadgeType.get_or_insert_for_topic(topic)

        # If we didn't succeed in creation, bail hard so we can
        # figure out what's going on
        if not badge_type:
            raise Exception("Failed to create TopicExerciseBadgeType: %s" %
                    topic.standalone_title)

        # Get all required exercise names for this topic
        exercise_names_required = [ex.name for ex in topic.children]

        # If the badge needs its required exercises updated or
        # was previously retired, update it.
        if (badge_type.retired or
                set(exercise_names_required) != set(badge_type.exercise_names_required) or
                badge_type.topic_standalone_title != topic.standalone_title or
                badge_type.icon_name != topic.icon_name):

            badge_type.exercise_names_required = exercise_names_required
            badge_type.topic_standalone_title = topic.standalone_title
            badge_type.icon_name = topic.icon_name
            badge_type.retired = False
            entities_to_put.append(badge_type)

    for badge_type in TopicExerciseBadgeType.all():

        # Make sure each TopicExerciseBadgeType has a corresponding topic...
        exists = any(
                t for t in topics
                if t.key().name() == badge_type.topic_key_name)

        # ...if it doesn't, it may've been created by an old topic
        # that has since been removed. In this case, retire the badge.
        if not exists:
            badge_type.retired = True
            entities_to_put.append(badge_type)

    if entities_to_put:
        db.put(entities_to_put)


class TopicExerciseBadge(Badge):
    """ TopicExerciseBadge represents a single challenge patch for
    achieving proficiency in all constituent exercises of a Topic.

    TopicExerciseBadges are constructed by the data stored in
    TopicExerciseBadgeType datastore entities.
    """

    @staticmethod
    def all():
        badges = [TopicExerciseBadge(t) for t in TopicExerciseBadgeType.all()]
        return sorted(badges, key=lambda b: b.topic_standalone_title.lower())

    @staticmethod
    def name_for_topic_key_name(topic_key_name):
        return "topic_exercise_%s" % topic_key_name

    @staticmethod
    def get_by_exercise(exercise_name):
        """return the TopicExerciseBadge for a given exercise"""
        icon = [b for b in TopicExerciseBadge.all()
                if exercise_name in b.exercise_names_required]
        if icon:
            return icon[0]
        return None

    def __init__(self, badge_type):
        Badge.__init__(self)

        # Set topic-specific properties
        self.topic_standalone_title = badge_type.topic_standalone_title
        self.exercise_names_required = badge_type.exercise_names_required

        # Icon file name prefix from Topic
        self.icon_name = badge_type.icon_name

        # Set typical badge properties
        self.name = TopicExerciseBadge.name_for_topic_key_name(
                badge_type.topic_key_name)
        self.description = self.topic_standalone_title
        self.points = 0
        self.badge_category = BadgeCategory.MASTER
        self.is_retired = badge_type.retired
        self.is_hidden_if_unknown = self.is_retired

    def is_satisfied_by(self, *args, **kwargs):

        # This badge can't inherit from RetiredBadge because its Retired status
        # is set dynamically by topics, so it must handle self.is_retired
        # manually.
        if self.is_retired:
            return False

        user_data = kwargs.get("user_data", None)
        if user_data is None:
            return False

        if len(self.exercise_names_required) <= 0:
            return False

        # Make sure user is proficient in all topic exercises
        for exercise_name in self.exercise_names_required:
            if not user_data.is_proficient_at(exercise_name):
                return False

        return True

    def extended_description(self):
        return ("Bereik bekwaamheid in alle vaardigheden van %s" %
                self.topic_standalone_title)

    @property
    def icon_filename(self):
        """ Some topics will have custom icons pre-prepared, and some won't.
        To add a custom icon to a topic, add the topic's name to
        TOPICS_WITH_CUSTOM_ICONS below. Those without will use a default icon.

        Custom icon location and format:
        40x40px: /images/power-mode/badges/
                    [lowercase-alphanumeric-dashes-only topic title]-40x40.png
        60x60px: /images/power-mode/badges/
                    [lowercase-alphanumeric-dashes-only topic title]-60x60.png

        See /images/power-mode/badges/readme
        """

        if self.icon_name:
            return self.icon_name
        else:
            return "default"

    @property
    def completed_icon_src(self):
        """ Returns the icon src for a special, "completed!" version of this
        topic badge to be used on the knowledge map only, for now.
        """
        path = ("/images/power-mode/badges/%s-completed-40x40.png?6" %
                self.icon_filename)
        return url_util.absolute_url(path)

    @property
    def compact_icon_src(self):
        path = "/images/power-mode/badges/%s-60x60.png?6" % self.icon_filename
        return url_util.absolute_url(path)

    @property
    def icon_src(self):
        path = "/images/power-mode/badges/%s-40x40.png?6" % self.icon_filename
        return url_util.absolute_url(path)

    @property
    def large_icon_src(self):
        path = ("/images/power-mode/badges/%s-250x250.png?7" %
                self.icon_filename)
        return url_util.absolute_url(path)


class TopicExerciseBadgeType(db.Model):
    """ Every time we publish a new topic tree,
    we make sure there is one TopicExerciseBadgeType for
    each topic that contains exercises.
    """

    topic_key_name = db.StringProperty()
    topic_standalone_title = db.StringProperty(indexed=False)
    exercise_names_required = object_property.TsvProperty(indexed=False)
    retired = db.BooleanProperty(default=False, indexed=False)
    icon_name = db.StringProperty(default="")

    @staticmethod
    def get_key_name(topic):
        return "topic:%s" % topic.key().name()

    @staticmethod
    def get_or_insert_for_topic(topic):

        if not topic:
            return None

        key_name = TopicExerciseBadgeType.get_key_name(topic)
        topic_badge_type = TopicExerciseBadgeType.get_by_key_name(key_name)

        if not topic_badge_type:
            topic_badge_type = TopicExerciseBadgeType.get_or_insert(
                    key_name=key_name,
                    topic_key_name=topic.key().name(),
                    topic_standalone_title=topic.standalone_title,
                    icon_name=topic.icon_name
                    )

        return topic_badge_type

# TODO: when we find a nicer way of detecting existence of icons,
# use that. Couple ideas so far felt even grosser than this quick
# and easy hack.
TOPICS_WITH_CUSTOM_ICONS = frozenset([
    "Addition and subtraction",
    "Multiplication and division",
    "Negative numbers",
    "Properties of numbers",
    "Order of operations",
    "Factors and multiples",
    "Fractions",
    "Decimals",
    "Percents",
    "Ratios and proportions (basic)",
    "Exponents (basic)",
    "intro to algebra",
    "solving linear equations",
    "Solving linear equations",
    "Solving linear inequalities",
    "Graphing linear equations and inequalities",
    "Solving linear equations and inequalities",
    "Systems of equations and inequalities",
    "Ratios and proportions",
    "Absolute value",
    "Exponents and Radicals",
    "Logarithms",
    "Polynomials and quadratics",
    "polynomials",
    "Quadratics",
    "Functions",
    "Conic sections",
    "Complex numbers",
    "ck12",
    "Linear equations and inequalities",
    "Angles",
    "Statistics",
    "Trigonometry",
    "Calculus",
    "Triangles",
    "Linear Algebra",
    "California Standards Test",
    "Circles",
    "Telling Time",
    "Basic Geometry",
    "Vectors",
    "Pythagorean theorem",
    "Probability",
    "Basic geometry",
    "Telling time",
    "Equation of a line",
    "Rates and ratios"
])
