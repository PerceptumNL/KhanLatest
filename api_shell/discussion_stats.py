"""Hacky tool for compiling discussion statistics via remote api shell.

When connected to a datastore via the remote api shell, you can run
this script via:

    >>> import discussion_stats

    >>> # ...this will take a while to run, possibly a couple hours
    >>> discussion_stats.analyze()
    "Done!"

    >>> # ...this doesn't deal w/ hacking around App Engine's file
    >>> # saving restrictions right now, so it just dumps data to be pasted
    >>> # elsewhere. TODO: save data somewhere instead of dumping as output.
    >>> discussion_stats.dump()
    {{ big messy dump of data that can be pasted right into a CSV file}}

This output contains the following comma-separated values, with one row
for each topic that contains videos and one row for the site as a whole:

    count_videos: number of videos

    count_questions: number of questions

    count_answers: number of answers

    count_deleted: number of questions/answers deleted by flags or mods

    count_quality_askers: number of unique authors of medium quality (or
        higher) questions

    count_quality_answerers: number of unique authors of medium quality (or
        higher) answers 

    count_vhq_questions: number of very high quality questions
    count_vhq_answers: number of very high quality answers
    count_vhq_questions_with_vhq_answer: number of very high quality questions
        with at least one very high quality answer

    count_hq_questions: number of high quality questions (not very high)
    count_hq_answers: number of high quality answers (not very high)

    count_mq_questions: number of medium quality questions (not high/very high)
    count_mq_answers: number of medium quality answers (not high/very high)

TODO: when discussion data is moved to ec2 land, this code could be
transitioned into a mongodb-friendly version and, perhaps, automatically
compiled over time.
"""

import datetime

import discussion.discussion_models
import discussion.util_discussion
import topic_models

# dict_totals collects statistics for entire site
dict_totals = {}

# dict_topic_totals collects statistics for each individual topic
dict_topic_totals = {}


def incr_stat(key, step, topic):
    """ Increment a specific stat by step for both site and a specific topic.

    Modifies global dict_totals and dict_topic_totals values.

    Arguments:
        key: name of statistic being incremented, such as "count_hq_answers"
        step: integer amount to increment statistic by
        topic: topic model from which this stat was compiled
    """
    if key not in dict_totals:
        dict_totals[key] = 0

    if key not in dict_topic_totals[topic.id]:
        dict_topic_totals[topic.id][key] = 0

    dict_totals[key] += step
    dict_topic_totals[topic.id][key] += step


def is_medium_quality(feedback):
    """ Return true if feedback qualifies as a medium quality post. """
    return (not is_high_quality(feedback) and
            not is_very_high_quality(feedback) and
            not feedback.is_flagged and 
            feedback.sum_votes >= 1 and 
            len(feedback.content) > 20)


def is_high_quality(feedback):
    """ Return true if feedback qualifies as a high quality post. """
    return (not is_very_high_quality(feedback) and
            not feedback.is_flagged and 
            feedback.sum_votes >= 3 and 
            len(feedback.content) > 30)


def is_very_high_quality(feedback):
    """ Return true if feedback qualifies as a very high quality post. """
    return (not feedback.is_flagged and 
            feedback.sum_votes >= 7 and 
            len(feedback.content) > 30)


def analyze(topics_to_analyze=-1):
    """ Analyze discussion content within all topics and compile stats. 
    
    This will individually walk through every video in every topic, compiling
    statistics about every question and answer.
    
    *This can take hours, so be prepared to let it run.*

    Analyze prints out a CSV-ified dump of compiled data.

    Arguments:
        topics_to_analyze: number of topics to analyze, or -1 for all topics
    """

    topics_analyzed = 0
    topic_dict = dict((t.id, t)
                      for t in topic_models.Topic.get_content_topics())

    for topic_id in topic_dict:

        topic = topic_dict[topic_id]

        if topic.id not in dict_topic_totals:
            dict_topic_totals[topic.id] = {}

        videos = topic.get_videos()
        incr_stat("count_videos", len(videos), topic)

        for video in videos:
            analyze_feedback(video, topic)
            print("Video done at: %s" % datetime.datetime.now())

        print("Finished topic: %s" % topic.standalone_title)

        topics_analyzed += 1
        if topics_to_analyze > -1 and topics_analyzed >= topics_to_analyze:
            break

    print("Done! Run discussion_stats.dump() to print CSV data.")


def dump():
    """ Print CSV file (as string) of most recently compiled stats. """
    # TODO: deal w/ App Engine's inability to write to a file or store this
    # elsewhere instead of just dumping to stdout.
    print(to_csv())


def analyze_feedback(video, topic):
    """ Analyze all feedback associated with a specific video and topic. """

    feedback = discussion.util_discussion.get_feedback_for_video(video)
    count_including_deleted = len(feedback)

    # Remove hidden posts
    feedback = [f for f in feedback if f.is_visible_to_public()]

    # Track deleted
    incr_stat("count_deleted", count_including_deleted - len(feedback), topic)

    questions = [f for f in feedback if f.is_type(discussion.discussion_models
                                                  .FeedbackType.Question)]
    dict_questions = dict((q.key(), q) for q in questions)

    answers = [f for f in feedback if f.is_type(discussion.discussion_models
                                                .FeedbackType.Answer)]
    # Just grab all answers for this video and cache in page's questions
    for answer in answers:
        # Grab the key only for each answer, don't run a full gql
        # query on the ReferenceProperty
        question_key = answer.question_key()
        if question_key in dict_questions:
            question = dict_questions[question_key]
            question.children_cache.append(answer)

    incr_stat("count_questions", len(questions), topic)
    incr_stat("count_answers",
              sum(len(q.children_cache) for q in questions),
              topic)

    # Assess very_high quality
    vhq_questions = [q for q in questions if is_very_high_quality(q)]

    for q in questions:
        q.vhq_children_cache = [a for a in q.children_cache
                                if is_very_high_quality(a)]

    incr_stat("count_vhq_questions", len(vhq_questions), topic)
    incr_stat("count_vhq_answers",
              sum(len(q.vhq_children_cache) for q in questions),
              topic)
    incr_stat("count_vhq_questions_with_vhq_answer", 
              len([vhq_q for vhq_q in vhq_questions
                   if len(vhq_q.vhq_children_cache) > 0]),
              topic)

    # Assess high quality
    hq_questions = [q for q in questions if is_high_quality(q)]

    for q in questions:
        q.hq_children_cache = [a for a in q.children_cache
                               if is_high_quality(a)]

    incr_stat("count_hq_questions", len(hq_questions), topic)
    incr_stat("count_hq_answers",
              sum(len(q.hq_children_cache) for q in questions),
              topic)

    # Assess medium quality
    mq_questions = [q for q in questions if is_medium_quality(q)]

    for q in questions:
        q.mq_children_cache = [a for a in q.children_cache
                               if is_medium_quality(a)]

    incr_stat("count_mq_questions", len(mq_questions), topic)
    incr_stat("count_mq_answers",
              sum(len(q.mq_children_cache) for q in questions),
              topic)

    # Count unique authors contributing >= mq posts
    quality_askers = set()
    quality_answerers = set()
    for q in questions:
        if is_medium_quality(q):
            # or is_high_quality(q) or is_very_high_quality(q):
            quality_askers.add(q.author_user_id)

        for a in q.children_cache:
            if is_medium_quality(a):
                # or is_high_quality(a) or is_very_high_quality(a):
                quality_answerers.add(a.author_user_id)

    incr_stat("count_quality_askers", len(quality_askers), topic)
    incr_stat("count_quality_answerers", len(quality_answerers), topic)


def to_csv():
    """ Convert compiled statistics into CSV string. """

    # Start w/ column headers
    lines = [",".join(csv_prop_order())]

    # Add cross-topic total stats as CSV row labeled "*All*"
    add_calculated_props("*All*", dict_totals)
    lines.append(dict_to_csv(dict_totals))

    # Skip any topics that don't have videos
    for topic_id in dict_topic_totals.keys():
        if dict_topic_totals[topic_id]["count_videos"] == 0:
            del dict_topic_totals[topic_id]

    # Add one CSV row per topic stats
    for topic_id in dict_topic_totals:
        add_calculated_props(topic_id, dict_topic_totals[topic_id])

    topic_dicts = sorted(dict_topic_totals.values(), 
            key=lambda d: d["ratio_mq_or_above_q_or_a"], 
            reverse=True)

    for topic_dict in topic_dicts:
        lines.append(dict_to_csv(topic_dict))

    return "\n".join(lines)


def csv_prop_order():
    """ Return ordered list of property names to be used as CSV columns. """

    return [
            "topic_id",
            "ratio_mq_or_above_q_or_a",
            "count_videos",
            "count_questions",
            "count_answers",
            "avg_questions_per_vid",
            "avg_answers_per_question",
            "count_quality_askers",
            "count_quality_answerers",
            "count_mq_questions",
            "count_mq_answers",
            "count_hq_questions",
            "count_hq_answers",
            "count_vhq_questions",
            "count_vhq_answers",
            "count_vhq_questions_with_vhq_answer",
            "count_deleted"
            ]


def add_calculated_props(topic_id, json_dict):
    """ Add additional calculated stat properties to json_dict.
    
    Some of the statistics we're interested in tracking require calculation
    on other stats post-compilation. Example: avg_questions_per_vid

    Arguments:
        topic_id: unique identifier for Topic model associated with this set
        of accumulated data
        json_dict: dict of statistics accumulated so far
    """

    json_dict["topic_id"] = topic_id

    json_dict["avg_questions_per_vid"] = (json_dict["count_questions"] / 
            float(json_dict["count_videos"]))
    json_dict["avg_answers_per_question"] = (json_dict["count_answers"] / 
            float(json_dict["count_questions"]))

    # Calculate total percentage of feedback that was >= medium quality
    json_dict["ratio_mq_or_above_q_or_a"] = ((
        json_dict["count_mq_questions"] + json_dict["count_mq_answers"] + 
        json_dict["count_hq_questions"] + json_dict["count_hq_answers"] + 
        json_dict["count_vhq_questions"] + json_dict["count_vhq_answers"]) / 
            float(json_dict["count_questions"] + json_dict["count_answers"]))


def dict_to_csv(json_dict):
    """ Turn a dictionary of stats into a single line of CSV data. """
    line = ",".join([str(json_dict[prop]) for prop in csv_prop_order()])
    return line
