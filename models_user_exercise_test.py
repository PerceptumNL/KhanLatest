#!/usr/bin/env python

import os

import models
import exercises.exercise_util
from testutil import testsize, gae_model


class UserDataCoachTest(gae_model.GAEModelTestCase):
    def setUp(self):
        super(UserDataCoachTest, self).setUp(db_consistency_probability=1)

        self.student = make_user('student@example.com')

        # Task queues want HTTP_HOST to be set.
        os.environ.setdefault('HTTP_HOST', 'localhost')

        # create a topic with some exercises
        edit_version = models.TopicVersion.create_new_version()
        self.topic = models.Topic.insert(title='title', parent=None,
            version=edit_version)

        # build a knowledge map that looks like this:
        #    c1
        #    |
        #  /---------\
        #  |    |    |
        #  l1  r1    d1
        #  |    |   /  \
        #  l2  r2  da  db
        #   \  /
        #    c2
        self.c1 = make_exercise("c1")

        self.l1 = make_exercise("l1", self.c1)
        self.l2 = make_exercise("l2", self.l1)
        self.r1 = make_exercise("r1", self.c1)
        self.r2 = make_exercise("r2", self.r1)
        self.c2 = make_exercise("c2", self.l2, self.r2)

        self.d1 = make_exercise("d1", self.c1)
        self.da = make_exercise("da", self.d1)
        self.db = make_exercise("db", self.d1)

        self.exercises = [
            self.c1,
            self.c2,
            self.l1,
            self.l2,
            self.r1,
            self.r2,
            self.d1,
            self.da,
            self.db
        ]

        for ex in self.exercises:
            self.topic.add_child(ex)

    def test_new_user_should_begin_at_c1(self):
        uexs = models.UserExercise.next_in_topic(self.student, self.topic)
        self.assertEqual(1, len(uexs))
        self.assertEqual(uexs[0].exercise_model.key(), self.c1.key())

    @testsize.medium()
    def test_when_proficient_in_c1_should_get_children(self):
        c1_uex = self.student.get_or_insert_exercise(self.c1)
        for i in xrange(10):
            do_problem(self.student, c1_uex)

        uexs = set(uex.exercise for uex in
            models.UserExercise.next_in_topic(self.student, self.topic))
        children = set(
                [e.name for e in self.exercises if 'c1' in e.prerequisites])
        self.assertTrue(len(children.intersection(uexs)) > 0)

    @testsize.medium()
    def test_returns_max_exercises(self):
        c1_uex = self.student.get_or_insert_exercise(self.c1)
        d1_uex = self.student.get_or_insert_exercise(self.d1)
        for i in xrange(10):
            do_problem(self.student, c1_uex)
            do_problem(self.student, d1_uex)

        # 4 exercises are now on the frontier
        uexs = [uex.exercise for uex in
            models.UserExercise.next_in_topic(self.student, self.topic, n=4)]
        self.assertEqual(4, len(uexs))

        # if we ask for 3 we should only get 3
        uexs = [uex.exercise for uex in
            models.UserExercise.next_in_topic(self.student, self.topic, n=3)]
        self.assertEqual(3, len(uexs))

    @testsize.medium()
    def test_when_exercise_is_worked_on_should_be_presented_last(self):
        c1_uex = self.student.get_or_insert_exercise(self.c1)
        for i in xrange(10):
            do_problem(self.student, c1_uex)

        r1_uex = self.student.get_or_insert_exercise(self.r1)
        do_problem(self.student, r1_uex)

        uexs = [uex.exercise for uex in
            models.UserExercise.next_in_topic(self.student, self.topic)]

        # now make sure r1 is c2
        self.assertEqual(uexs[-1], 'r1')

        # try again with l1
        l1_uex = self.student.get_or_insert_exercise(self.l1)
        do_problem(self.student, l1_uex)

        uexs = [uex.exercise for uex in
            models.UserExercise.next_in_topic(self.student, self.topic)]

        self.assertEqual(uexs[-1], 'l1')

    @testsize.medium()
    def test_proficient_exercises_are_not_returned(self):
        c1_uex = self.student.get_or_insert_exercise(self.c1)
        l1_uex = self.student.get_or_insert_exercise(self.l1)
        r1_uex = self.student.get_or_insert_exercise(self.r1)

        # get some proficiencies
        for i in xrange(10):
            do_problem(self.student, c1_uex)
            do_problem(self.student, r1_uex)
            do_problem(self.student, l1_uex)

        uexs = [uex.exercise for uex in
            models.UserExercise.next_in_topic(self.student, self.topic)]

        # make sure no proficient exercises are returned
        self.assertNotIn('c1', uexs)
        self.assertNotIn('l1', uexs)
        self.assertNotIn('r1', uexs)

    @testsize.medium()
    def test_exercise_in_review_mode_is_included(self):
        c1_uex = self.student.get_or_insert_exercise(self.c1)
        l1_uex = self.student.get_or_insert_exercise(self.l1)
        r1_uex = self.student.get_or_insert_exercise(self.r1)

        # get some proficiencies
        for i in xrange(10):
            do_problem(self.student, c1_uex)
            do_problem(self.student, r1_uex)
            _, graph, _ = do_problem(self.student, l1_uex)

        # meta-assert: validate there are currently no review exercises
        reviewing = set(ex['name'] for ex in graph.review_graph_dicts())
        self.assertEqual(0, len(reviewing))

        # now put some into review mode by getting an answer wrong
        _, graph, _ = do_problem(self.student, c1_uex, correct=False)
        _, graph, _ = do_problem(self.student, l1_uex, correct=False)

        # meta-assert: validate this actually worked
        reviewing = set(ex['name'] for ex in graph.review_graph_dicts())
        self.assertIn('c1', reviewing)
        self.assertIn('l1', reviewing)

        uexs = [uex.exercise for uex in
            models.UserExercise.next_in_topic(self.student, self.topic)]

        # now make sure the reviewable exercises are included
        self.assertIn('c1', uexs)
        self.assertIn('l1', uexs)


def do_problem(user_data, user_exercise, correct=True):
    options = {
        "user_data": user_data,
        "user_exercise": user_exercise,
        "problem_number": user_exercise.total_done + 1,
        "attempt_number": 1,
        "attempt_content": "TEST",
        "sha1": "TEST",
        "seed": "TEST",
        "completed": True,
        "count_hints": 0,
        "time_taken": 1,
        "review_mode": False,
        "topic_mode": False,
        "problem_type": "TEST",
        "ip_address": "0.0.0.0",
        "card": {},
        "stack_uid": "TEST",
        "topic_id": "TEST",
        "cards_done": 1,
        "cards_left": 7,
        "async_problem_log_put": False,
    }

    if correct:
        return exercises.exercise_util.attempt_problem(**options)
    else:
        exercises.exercise_util.attempt_problem(**dict(options.items() +
            {"completed": False}.items()))
        return exercises.exercise_util.attempt_problem(**dict(options.items() +
            {"attempt_number": 2}.items()))


def make_user(email):
    u = models.UserData.insert_for(email, email)
    u.put()
    return u


def make_exercise(exercise_name, *prereqs):
    query = models.Exercise.all().filter('name =', exercise_name)
    if query.get():
        raise "Already exists!"

    prereqs = [p for p in prereqs]
    if prereqs and hasattr(prereqs[0], "name"):
        prereqs = [e.name for e in prereqs]

    exercise = models.Exercise(
        name=exercise_name,
        prerequisites=list(prereqs),
        covers=[],
        author=None,
        live=True)
    exercise.put()
    return exercise
