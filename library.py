import layer_cache
import topic_models
from setting_model import Setting
import shared_jinja
import math


# helpful function to see topic structure from the console.  In the console:
# import library
# library.library_content_html(bust_cache=True)
#
# Within library_content_html: print_topics(topics)
def print_topics(topics):
    for topic in topics:
        print topic.homepage_title
        print topic.depth
        if topic.subtopics:
            print "subtopics:"
            for subtopic in topic.subtopics:
                print subtopic.homepage_title
                if subtopic.subtopics:
                    print "subsubtopics:"
                    for subsubtopic in subtopic.subtopics:
                        print subsubtopic.homepage_title
                    print " "
            print " "
        print " "


def flatten_tree(tree, parent_topics=[]):
    homepage_topics = []
    tree.content = []
    tree.subtopics = []

    tree.depth = len(parent_topics)

    if parent_topics:
        if tree.depth == 1 and len(parent_topics[0].subtopics) > 1:
            tree.homepage_title = '%s: %s' % (
                parent_topics[0].standalone_title, tree.title)
        else:
            tree.homepage_title = tree.title
    else:
        tree.homepage_title = tree.standalone_title

    child_parent_topics = parent_topics[:]

    if tree.id in topic_models.Topic._super_topic_ids:
        tree.is_super = True
        child_parent_topics.append(tree)
    elif parent_topics:
        child_parent_topics.append(tree)

    for child in tree.children:
        if child.key().kind() == "Topic":
            if child.has_children_of_type(["Topic", "Video", "Url"]):
                tree.subtopics.append(child)
        else:
            tree.content.append(child)

    del tree.children

    if tree.content:
        tree.height = math.ceil(len(tree.content) / 3.0) * 18

    if hasattr(tree, "is_super") or (not parent_topics and tree.content):
        homepage_topics.append(tree)

    for subtopic in tree.subtopics:
        homepage_topics += flatten_tree(subtopic, child_parent_topics)

    return homepage_topics


def add_next_topic(topics, prev_topic=None, depth=0):
    """ Does a depth first search through the topic tree and keeps the last
    topic it has seen in prev_topic variable so as to populates its .next
    attribute to point to the current topic and populate .next_is_subtopic to
    say if the current topic is a subtopic or not.
    """
    for topic in topics:
        # if we are not the very first topic
        if prev_topic:
            # set the previous topic's next and next_is_subtopic attributes
            prev_topic.next = topic
            if depth > 0:
                prev_topic.next_is_subtopic = True

        if topic.subtopics:
            # set prev_topic to the last item in the subtopic list
            prev_topic = add_next_topic(topic.subtopics,
                                        prev_topic=topic,
                                        depth=depth + 1)
        else:
            # set prev_topic to the current topic
            prev_topic = topic

    # return last item in the list
    return prev_topic


# A number to increment if the layout of the page, as expected by the client
# side JS changes, and the JS is changed to update it. This version is
# independent of topic content version, and is to do with code versions
_layout_version = 2


@layer_cache.cache_with_key_fxn(
        lambda ajax=False, version_number=None:
        "library_content_by_topic_%s_v%s.%s" % (
        "ajax" if ajax else "inline",
        version_number if version_number else Setting.topic_tree_version(),
        _layout_version))
def library_content_html(ajax=False, version_number=None):
    """" Returns the HTML for the structure of the topics as they will be
    populated on the homepage. Does not actually contain the list of video
    names as those are filled in later asynchronously via the cache.
    """
    if version_number:
        version = topic_models.TopicVersion.get_by_number(version_number)
    else:
        version = topic_models.TopicVersion.get_default_version()
    return None
    tree = topic_models.Topic.get_root(version).make_tree(
        types=["Topics", "Video", "Url"])
    topics = flatten_tree(tree)

    topics.sort(key=lambda topic: topic.standalone_title)

    # special case the duplicate topics for now, eventually we need to
    # either make use of multiple parent functionality (with a hack
    # for a different title), or just wait until we rework homepage
    topics = [topic for topic in topics
              if not topic.id == "new-and-noteworthy" and not
              (topic.standalone_title == "California Standards Test: Geometry"
              and not topic.id == "geometry-2")]

    # print_topics(topics)

    add_next_topic(topics)

    template_values = {
        'topics': topics,
        'ajax': ajax,
        'version_date': str(version.made_default_on),
        'version_id': version.number
    }

    html = shared_jinja.get().render_template("library_content_template.html",
                                              **template_values)

    return html
