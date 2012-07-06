import threading
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import request_cache


class RequestCacheThreadSafetyTest(unittest.TestCase):
    """Test that request_cache storage is per-thread.

    On App Engine with multithreading enabled each request is assigned
    a thread. request_cache relies on thread-local storage to
    implement its cache.

    This test exists to verify that things work as expected because
    the dev appserver doesn't handle requests in parallel. Also, if
    there is an implementation change maybe this will be an early alert.
    """

    def tearDown(self):
        super(RequestCacheThreadSafetyTest, self).tearDown()
        request_cache.flush()

    def test_read_thread_storage_in_has(self):
        self.assertFalse(request_cache.has('key'))
        request_cache.set('key', 'main')
        self.assertTrue(request_cache.has('key'))

        thread_output = {}

        def thread_func(thread_output):
            thread_output['value_of_has'] = request_cache.has('key')

        thread = threading.Thread(target=thread_func, args=[thread_output])
        thread.start()
        thread.join()

        # The second thread should see different values than the main thread.
        self.assertFalse(thread_output['value_of_has'])

    def test_read_thread_storage_in_get(self):
        self.assertIsNone(request_cache.get('key'))
        request_cache.set('key', 'main')
        self.assertEqual('main', request_cache.get('key'))

        thread_output = {}

        def thread_func(thread_output):
            thread_output['value_of_get'] = request_cache.get('key')

        thread = threading.Thread(target=thread_func, args=[thread_output])
        thread.start()
        thread.join()

        # The second thread should see different values than the main thread.
        self.assertIsNone(thread_output['value_of_get'])

    def test_write_thread_storage_in_set(self):
        self.assertFalse(request_cache.has('key'))
        self.assertIsNone(request_cache.get('key'))

        thread_output = {}

        def thread_func(thread_output):
            request_cache.set('key', 'thread')
            thread_output['value_of_get_after_set'] = request_cache.get('key')

        thread = threading.Thread(target=thread_func, args=[thread_output])
        thread.start()
        thread.join()

        # The main thread should not see changes made by the second
        # thread.
        self.assertFalse(request_cache.has('key'))
        self.assertIsNone(request_cache.get('key'))
        self.assertEqual('thread', thread_output['value_of_get_after_set'])

    def test_write_thread_storage_in_flush(self):
        request_cache.set('key', 'main')
        self.assertTrue(request_cache.has('key'))
        self.assertEqual('main', request_cache.get('key'))

        thread_output = {}

        def thread_func(thread_output):
            request_cache.set('key', 'thread')
            thread_output['value_of_get_before_flush'] = (
                request_cache.get('key'))
            request_cache.flush()
            thread_output['value_of_get_after_flush'] = (
                request_cache.get('key'))

        thread = threading.Thread(target=thread_func, args=[thread_output])
        thread.start()
        thread.join()

        # The main thread should not see changes made by the second
        # thread.
        self.assertTrue(request_cache.has('key'))
        self.assertEqual('main', request_cache.get('key'))
        self.assertEqual('thread', thread_output['value_of_get_before_flush'])
        self.assertIsNone(thread_output['value_of_get_after_flush'])
