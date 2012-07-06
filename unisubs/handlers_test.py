from __future__ import with_statement

import datetime
import urllib

from third_party.agar.test import BaseTest
from third_party.agar.test import MockUrlfetchTest
from google.appengine.api.urlfetch import DownloadError
from mock import patch
from mock import Mock

from video_models import Video, VideoSubtitles, VideoSubtitlesFetchReport
from testutil import gaetasktime
import unisubs.handlers
from unisubs.handlers import BATCH_SIZE
from unisubs.handlers import DEFER_SECONDS
from unisubs.handlers import ImportHandler
from unisubs.handlers import _task_handler
from unisubs.handlers import _task_report_handler

UNISUBS_API_URL = 'http://www.universalsubtitles.org/api/1.0/subtitles/' \
                      '?language=en&video_url=%s'

# Hack for speed: force default queue name.  Using the correct non-default
# queue throws an UnknownQueueError unless the testbed's root_path is set.
# However, that config reading makes the tests 4x slower.

unisubs.handlers.TASK_QUEUE = UNISUBS_FETCH_Q = 'default'


class ImportHandlerTest(BaseTest):
    def test_cron_handler_enqueues_task_and_does_not_redirect(self):
        handler = ImportHandler(None, Mock())
        handler.request_string = Mock(return_value='')
        handler.redirect = Mock(
            side_effect=RuntimeError('should not redirect'))

        handler.get()
        self.assertTasksInQueue(n=1, queue_names=UNISUBS_FETCH_Q)
        handler.request_string.assert_called_once_with('interactive')

    @patch('unisubs.handlers.uuid')
    def test_interactive_handler_enqueues_task_and_redirects(self, uuid):
        uuid.uuid4.return_value = 'UUID'
        handler = ImportHandler(None, Mock())
        handler.request_string = Mock(return_value='1')
        handler.redirect = Mock()

        handler.post()
        self.assertTasksInQueue(n=1, queue_names=UNISUBS_FETCH_Q)
        handler.request_string.assert_called_once_with('interactive')
        handler.redirect.assert_called_once_with(
            '/admin/unisubs?_started=UUID')


class TaskReportHandlerTest(BaseTest):
    def test_put_report_updates_status(self):
        report = {'status': 'started'}
        _task_report_handler('UUID', report)
        self.assertEqual(VideoSubtitlesFetchReport().all().count(), 1)
        report = VideoSubtitlesFetchReport().all().get()
        self.assertEqual(report.status, 'finished')


class TaskHandlerTest(MockUrlfetchTest):
    def _set_responses_xrange(self, *args, **kwargs):
        """Populate db with Video and mock URL responses for their subtitles"""
        for i in xrange(*args):
            youtube_id = str(i)
            Video(youtube_id=youtube_id).put()
            video_url = urllib.quote('http://www.youtube.com/watch?v=%s' %
                                     youtube_id)
            url = UNISUBS_API_URL % video_url
            self.set_response(url, content=kwargs.get('content', youtube_id),
                              status_code=kwargs.get('status_code', 200))

    def test_report_started_immediately(self):
        _task_handler('UUID')
        self.assertEqual(VideoSubtitlesFetchReport.all().count(), 1)

    def test_process_first_batch_on_empty_cursor(self):
        self._set_responses_xrange(BATCH_SIZE)
        _task_handler('UUID')
        self.assertEqual(VideoSubtitles.all().count(), BATCH_SIZE)

    def test_process_next_batch_on_nonempty_cursor(self):
        offset = 3

        # these should be skipped, they'll DownloadError
        for i in xrange(0, offset):
            Video(youtube_id=str(i)).put()

        # these should be downloaded
        self._set_responses_xrange(offset, BATCH_SIZE + offset)

        query = Video.all()
        query.fetch(offset)
        cursor = query.cursor()

        _task_handler('UUID', cursor=cursor)
        self.assertEqual(VideoSubtitles.all().count(), BATCH_SIZE)

    def test_schedule_task_after_processing_full_batch(self):
        self._set_responses_xrange(BATCH_SIZE)
        _task_handler('UUID')
        self.assertTasksInQueue(n=1, name='UUID_1',
                                queue_names=UNISUBS_FETCH_Q)

    def test_schedule_report_after_processing_partial_batch(self):
        self._set_responses_xrange(1)
        _task_handler('UUID')
        self.assertTasksInQueue(n=1, name='UUID_report',
                                queue_names=UNISUBS_FETCH_Q)

    def test_schedule_report_after_processing_empty_batch(self):
        _task_handler('UUID')
        self.assertTasksInQueue(n=1, name='UUID_report',
                                queue_names=UNISUBS_FETCH_Q)

    def test_delay_between_batches(self):
        self._set_responses_xrange(BATCH_SIZE)

        expected_eta = (gaetasktime.eta_utcnow() +
                        datetime.timedelta(seconds=DEFER_SECONDS))

        _task_handler('UUID')
        self.assertTasksInQueue(n=1)
        task, = self.get_tasks()
        self.assertTrue(task.eta >= expected_eta)

    def test_assume_utf8_encoded_content(self):
        # Universal Subtitles API returns utf-8
        # u'\xc4\xd0' is unicode for the utf-8 byte string '\xc3\x84\xc3\x90'
        utf8_str = '\xc3\x84\xc3\x90'
        unicode_str = u'\xc4\xd0'

        self._set_responses_xrange(1, content=utf8_str)

        _task_handler('UUID')
        self.assertEqual(VideoSubtitles.all().count(), 1)
        subs = VideoSubtitles.all().get()
        self.assertEqual(subs.json, unicode_str)

    @patch('unisubs.handlers.deferred.defer')
    def test_report_number_of_fetches(self, defer):
        self._set_responses_xrange(BATCH_SIZE)

        def _defer(func, uid, id, cursor, report, **kwargs):
            self.assertEqual(report['fetches'], BATCH_SIZE)
            self.assertEqual(report['writes'], BATCH_SIZE)
        defer.side_effect = _defer

        _task_handler('UUID')
        self.assertEqual(defer.call_count, 1, 'task should be enqueued')

    @patch('unisubs.handlers.deferred.defer')
    @patch('logging.error')
    def test_log_and_report_download_error(self, error, defer):
        self._set_responses_xrange(1, content=DownloadError())

        def _defer(func, uid, report, **kwargs):
            self.assertEqual(report['errors'], 1)
        defer.side_effect = _defer

        _task_handler('UUID')
        self.assertEqual(error.call_count, 1,
                         'download error should be logged')
        self.assertEqual(defer.call_count, 1, 'task should be enqueued')

    @patch('unisubs.handlers.VideoSubtitles')
    @patch('unisubs.handlers.deferred.defer')
    @patch('logging.error')
    def test_log_and_report_subtitles_put_error(self, error, defer,
            VideoSubtitles):

        self._set_responses_xrange(1)

        VideoSubtitles.return_value.put.side_effect = \
            RuntimeError('failed mock put()')

        def _defer(func, uid, report, **kwargs):
            self.assertEqual(report['errors'], 1)
            self.assertEqual(report['writes'], 0)
        defer.side_effect = _defer

        _task_handler('UUID')
        self.assertEqual(error.call_count, 1, 'put error should be logged')
        self.assertEqual(defer.call_count, 1, 'task should be enqueued')
        self.assertEqual(VideoSubtitles.return_value.put.call_count, 1,
                         'put() should have been called')

    @patch('logging.info')
    def test_should_not_put_duplicate_subtitles(self, info):
        self._set_responses_xrange(BATCH_SIZE, content="some json")

        # first fetch
        _task_handler('UUID', 0)
        self.assertEqual(VideoSubtitles.all().count(), BATCH_SIZE)
        self.assertEqual(info.call_count, 0)

        with patch('unisubs.handlers.VideoSubtitles') as MockVideoSubtitles:
            MockVideoSubtitles.get_key_name = VideoSubtitles.get_key_name
            MockVideoSubtitles.get_by_key_name = VideoSubtitles.get_by_key_name
            # second fetch, same content
            _task_handler('UUID', 1)
            self.assertEqual(MockVideoSubtitles.return_value.put.call_count, 0,
                             'duplicate subtitles should not be put()')
            self.assertEqual(info.call_count, BATCH_SIZE,
                             'skipped put should be logged')

    @patch('logging.error')
    def test_log_error_for_non_200_status(self, error):
        self._set_responses_xrange(1, status_code=404)
        _task_handler('UUID')
        self.assertEqual(error.call_count, 1, 'status error should be logged')
        logged_message = error.call_args[0][0]
        self.assertEqual(logged_message.count('404'), 1)

    def test_derive_key_name_from_video(self):
        self._set_responses_xrange(BATCH_SIZE)
        _task_handler('UUID')
        videos = Video.all().fetch(BATCH_SIZE)
        for v in videos:
            key = VideoSubtitles.get_key_name('en', v.youtube_id)
            subs = VideoSubtitles.get_by_key_name(key)
            self.assertIsNotNone(subs)
