from google.appengine.api import memcache
from google.appengine.ext import deferred
from agar.test import BaseTest

import main

def do_something():
    return True

class TestBaseTest(BaseTest):

    def test_assert_tasks_in_queue(self):
        self.assertTasksInQueue(0)
        
        deferred.defer(do_something, _name="hello_world")

        self.assertTasksInQueue(1)
        self.assertTasksInQueue(1, name='hello_world')
        self.assertTasksInQueue(0, name='something else')
        self.assertTasksInQueue(0, url='/foobar')
        self.assertTasksInQueue(1, url='/_ah/queue/deferred')
        self.assertTasksInQueue(1, queue_names='default')
        self.assertTasksInQueue(0, queue_names='other')

    def test_assert_memcache_items(self):
        self.assertMemcacheItems(0)

        memcache.set("foo", "bar")

        self.assertMemcacheItems(1)

        memcache.set("abc", "xyz")

        self.assertMemcacheItems(2)

    def test_assert_memcache_hits(self):
        self.assertMemcacheHits(0)

        memcache.get("foo")

        self.assertMemcacheHits(0)

        memcache.set("foo", "bar")
        memcache.get("foo")

        self.assertMemcacheHits(1)

        memcache.get("foo")

        self.assertMemcacheHits(2)

