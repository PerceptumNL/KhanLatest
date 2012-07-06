"""Test that we can communicate with youtube via the youtube API.

This test actually talks to youtube, so it's particularly flaky: it
can fail if youtube is down, or if a video gets renamed.  The 'right'
solution is to mock out the actual youtube communication.  But since
one reason for this test that we're using the gdata library correctly,
that's difficult to do.  TODO(csilvers): figure out a better way.
"""

from testutil.gae_model import GAEModelTestCase
from testutil import testsize
import youtube_sync


# This has to mock out the appengine db in order to do youtube fetching.
class GdataTest(GAEModelTestCase):
    """Test that we use the gdata API properly."""
    @testsize.large()
    def test_get_video_data_dict(self):
        # If this test starts failing, make sure this video still
        # exists on youtube, and nobody has changed any info about it.
        data = youtube_sync.youtube_get_video_data_dict('NvGTCzAfvr0')
        self.assertEqual('Absolute Value 1', data['title'])
        self.assertTrue('NvGTCzAfvr0' in data['url'], data['url'])
        self.assertEqual(202, data['duration'])
        # As of 11 April 2012, this video has had 99221 views, so it's
        # safe to have that be a lower bound here.
        self.assertTrue(data['views'] >= 99221, data['views'])
