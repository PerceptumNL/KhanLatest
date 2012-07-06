try:
    import unittest2 as unittest
except ImportError:
    import unittest

import video_models
from mock import patch


class VideoSubtitlesTest(unittest.TestCase):
    def test_get_key_name(self):
        kn = video_models.VideoSubtitles.get_key_name('en', 'YOUTUBEID')
        self.assertEqual(kn, 'en:YOUTUBEID')

    def test_load_valid_json(self):
        subs = video_models.VideoSubtitles(json='[{"text":"subtitle"}]')
        json = subs.load_json()
        self.assertIsNotNone(json)
        self.assertEqual([{u'text': u'subtitle'}], json)

    @patch('models.logging.warn')
    def test_log_warning_on_invalid_json(self, warn):
        subs = video_models.VideoSubtitles(json='invalid json')
        json = subs.load_json()
        self.assertIsNone(json)
        self.assertEqual(warn.call_count, 1, 'logging.warn() not called')
