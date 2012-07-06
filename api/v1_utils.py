"""Helper routines called by handlers in api/v1.py.

TODO(csilvers): this is a terrible grab-bag of functionality.  Refactor.
"""

import cStringIO as StringIO
import datetime
import logging
import traceback
import zlib

from google.appengine.ext import db
from google.appengine.ext import deferred

import app
import exercise_models
import exercise_video_model
import pickle_util
import setting_model
import topic_models
import url_model
import video_models


def exercise_save_data(version, data, exercise=None, put_change=True):
    if "name" not in data:
        raise Exception("exercise 'name' missing")
    data["live"] = data["live"] == "true" or data["live"] == True
    data["v_position"] = int(data["v_position"])
    data["h_position"] = int(data["h_position"])
    data["seconds_per_fast_problem"] = (
        float(data["seconds_per_fast_problem"]))

    changeable_props = ["name", "covers", "h_position", "v_position", "live",
                        "prerequisites", "covers", "seconds_per_fast_problem",
                        "related_video_readable_ids", "description", 
                        "short_display_name", "pretty_display_name", "file_name"]
    if exercise:
        exercise_models.Exercise.add_related_video_readable_ids_prop(
                {exercise.key(): exercise})
        return topic_models.VersionContentChange.add_content_change(
                exercise,
                version,
                data,
                changeable_props)
    else:
        return topic_models.VersionContentChange.add_new_content(
                exercise_models.Exercise,
                version,
                data,
                changeable_props,
                put_change)


def topictree_import_task(version_id, topic_id, publish, tree_json_compressed):
    try:
        tree_json = pickle_util.load(zlib.decompress(tree_json_compressed))

        logging.info("starting import")
        version = topic_models.TopicVersion.get_by_id(version_id)
        parent = topic_models.Topic.get_by_id(topic_id, version)

        topics = topic_models.Topic.get_all_topics(version, True)
        logging.info("got all topics")
        topic_dict = dict((topic.id, topic) for topic in topics)
        topic_keys_dict = dict((topic.key(), topic) for topic in topics)

        videos = video_models.Video.get_all()
        logging.info("got all videos")
        video_dict = dict((video.readable_id, video) for video in videos)

        exercises = exercise_models.Exercise.get_all_use_cache()
        logging.info("got all exercises")
        exercise_dict = dict((exercise.name, exercise)
                             for exercise in exercises)

        all_entities_dict = {}
        new_content_keys = []

        # on dev server dont record new items in ContentVersionChanges
        if app.App.is_dev_server:
            put_change = False
        else:
            put_change = True

        # delete all subtopics of node we are copying over the same topic
        if tree_json["id"] == parent.id:
            parent.delete_descendants()

        # adds key to each entity in json tree, if the node is not in
        # the tree then add it
        def add_keys_json_tree(tree, parent, do_exercises, i=0, prefix=None):
            pos = ((prefix + ".") if prefix else "") + str(i)

            if not do_exercises and tree["kind"] == "Topic":
                if tree["id"] in topic_dict:
                    topic = topic_dict[tree["id"]]
                    tree["key"] = topic.key()
                else:
                    kwargs = dict((str(key), value)
                                  for key, value in tree.iteritems()
                                  if key in ['standalone_title', 'description',
                                             'tags'])
                    kwargs["version"] = version
                    topic = topic_models.Topic.insert(title=tree['title'],
                                                      parent=parent, **kwargs)
                    logging.info("%s: added topic %s" % (pos, topic.title))
                    tree["key"] = topic.key()
                    topic_dict[tree["id"]] = topic

                # if this topic is not the parent topic (ie. its not
                # root, nor the topic_id you are updating)
                if (parent.key() != topic.key() and
                    # and this topic is not in the new parent
                    topic.key() not in parent.child_keys and
                    # if it already exists in a topic
                    len(topic.parent_keys) and
                    # and that topic is not the parent topic
                    topic.parent_keys[0] != parent.key()):

                    # move it from that old parent topic, its position
                    # in the new parent does not matter as child_keys
                    # will get written over later.  move_child is
                    # needed only to make sure that the parent_keys
                    # and ancestor_keys will all match up correctly
                    old_parent = topic_keys_dict[topic.parent_keys[0]]
                    logging.info("moving topic %s from %s to %s" % (topic.id,
                        old_parent.id, parent.id))
                    old_parent.move_child(topic, parent, 0)

                all_entities_dict[tree["key"]] = topic

            elif not do_exercises and tree["kind"] == "Video":
                if tree["readable_id"] in video_dict:
                    video = video_dict[tree["readable_id"]]
                    tree["key"] = video.key()
                else:
                    changeable_props = ["youtube_id", "url", "title", 
                                        "description", "keywords", "duration", 
                                        "readable_id", "views"]
                    video = topic_models.VersionContentChange.add_new_content(
                                                            video_models.Video,
                                                            version,
                                                            tree,
                                                            changeable_props,
                                                            put_change)
                    logging.info("%s: added video %s" % (pos, video.title))
                    new_content_keys.append(video.key())
                    tree["key"] = video.key()
                    video_dict[tree["readable_id"]] = video

                all_entities_dict[tree["key"]] = video

            elif do_exercises and tree["kind"] == "Exercise":
                if tree["name"] in exercise_dict:
                    tree["key"] = (exercise_dict[tree["name"]].key() 
                                   if tree["name"] in exercise_dict else None)
                else:
                    if "related_video_readable_ids" in tree:
                        # adding keys to entity tree so we don't need to look
                        # it up again when creating the video in 
                        # add_new_content
                        tree["related_video_keys"] = []
                        for readable_id in tree["related_video_readable_ids"]:
                            video = video_dict[readable_id]
                            tree["related_video_keys"].append(video.key())

                    exercise = exercise_save_data(version, 
                                                  tree, 
                                                  None, 
                                                  put_change)
                    logging.info("%s: added Exercise %s" %
                                 (pos, exercise.name))
                    new_content_keys.append(exercise.key())
                    tree["key"] = exercise.key()
                    exercise_dict[tree["name"]] = exercise

                all_entities_dict[tree["key"]] = exercise_dict[tree["name"]]

            elif not do_exercises and tree["kind"] == "Url":
                if tree["id"] in url_dict:
                    url = url_dict[tree["id"]]
                    tree["key"] = url.key()
                else:
                    changeable_props = ["tags", "title", "url"]
                    url = topic_models.VersionContentChange.add_new_content(
                                                            url_model.Url,
                                                            version,
                                                            tree,
                                                            changeable_props,
                                                            put_change)
                    logging.info("%s: added Url %s" % (pos, url.title))
                    new_content_keys.append(url.key())
                    tree["key"] = url.key()
                    url_dict[tree["id"]] = url

                all_entities_dict[tree["key"]] = url

            i = 0
            # recurse through the tree's children
            if "children" in tree:
                for child in tree["children"]:
                    add_keys_json_tree(child, 
                                       topic_dict[tree["id"]], 
                                       do_exercises, i, pos)
                    i += 1

        add_keys_json_tree(tree_json, parent, do_exercises=False)

        # add related_video_readable_ids prop to exercises
        evs = exercise_video_model.ExerciseVideo.all().fetch(10000)
        exercise_key_dict = dict((e.key(), e) for e in exercises)
        video_key_dict = dict((v.key(), v) for v in video_dict.values())
        exercise_models.Exercise.add_related_video_readable_ids_prop(
                exercise_key_dict, 
                evs, 
                video_key_dict)

        # exercises need to be done after, because if they reference
        # ExerciseVideos those Videos have to already exist
        add_keys_json_tree(tree_json, parent, do_exercises=True)

        logging.info("added keys to nodes")

        def add_child_keys_json_tree(tree):
            if tree["kind"] == "Topic":
                tree["child_keys"] = []
                if "children" in tree:
                    for child in tree["children"]:
                        tree["child_keys"].append(child["key"])
                        add_child_keys_json_tree(child)

        add_child_keys_json_tree(tree_json)
        logging.info("added children keys")

        def extract_nodes(tree, nodes):
            if "children" in tree:
                for child in tree["children"]:
                    nodes.update(extract_nodes(child, nodes))
                del(tree["children"])
            nodes[tree["key"]] = tree
            return nodes

        nodes = extract_nodes(tree_json, {})
        logging.info("extracted %i nodes" % len(nodes))
        changed_nodes = []

        i = 0
        # now loop through all the nodes
        for key, node in nodes.iteritems():
            if node["kind"] == "Topic":
                topic = all_entities_dict[node["key"]]
                logging.info("%i/%i Updating any change to Topic %s" %
                             (i, len(nodes), topic.title))

                kwargs = (dict((str(key), value)
                               for key, value in node.iteritems()
                               if key in ['id', 'title', 'standalone_title',
                                          'description', 'tags', 'hide',
                                          'child_keys']))
                kwargs["version"] = version
                kwargs["put"] = False
                if topic.update(**kwargs):
                    changed_nodes.append(topic)

            elif (node["kind"] == "Video" and
                  node["key"] not in new_content_keys):
                video = all_entities_dict[node["key"]]
                logging.info("%i/%i Updating any change to Video %s" %
                             (i, len(nodes), video.title))

                change = topic_models.VersionContentChange.add_content_change(
                    video,
                    version,
                    node,
                    ["readable_id", "title", "youtube_id", "description", 
                    "keywords"])
                if change:
                    logging.info("changed")

            elif (node["kind"] == "Exercise" and
                  node["key"] not in new_content_keys):
                exercise = all_entities_dict[node["key"]]
                logging.info("%i/%i Updating any changes to Exercise %s" %
                             (i, len(nodes), exercise.name))

                change = exercise_save_data(version, node, exercise)
                if change:
                    logging.info("changed")

            elif node["kind"] == "Url" and node["key"] not in new_content_keys:
                url = all_entities_dict[node["key"]]
                logging.info("%i/%i Updating any changes to Url %s" %
                             (i, len(nodes), url.title))

                changeable_props = ["tags", "title", "url"]

                change = topic_models.VersionContentChange.add_content_change(
                    url,
                    version,
                    node,
                    changeable_props)

                if change:
                    logging.info("changed")

            i += 1

        logging.info("about to put %i topic nodes" % len(changed_nodes))
        setting_model.Setting.cached_content_add_date(datetime.datetime.now())
        db.put(changed_nodes)
        logging.info("done with import")

        if publish:
            version.set_default_version()

    except Exception, e:
        fp = StringIO.StringIO()
        traceback.print_exc(file=fp)
        logging.error(fp.getvalue())
        logging.error("Topic import failed with %s", e)
        raise deferred.PermanentTaskFailure

    return True
