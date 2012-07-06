"""Tests of all the handlers in v1.py.

This includes end-to-end tests of all the handlers in v1.  (It's a
rather slow test because of that.)  Basically, it sends off a url
request and makes sure the response is sane.  end-to-end tests require a
running appengine instance: it will start an instance on an unused port.

To run an individual test from this file, run something like:
   $ tools/runtests.py --max-size=large \
     api.v1_endtoend_test.V1EndToEndGetTest.test_user
"""

import urllib2

from testutil import handler_test_utils
from testutil import oauth_test_client
from testutil import testsize
try:
    import unittest2 as unittest     # python 2.5
except ImportError:
    import unittest                  # python 2.6+


# Set to False to get error reports for all tests we haven't done yet.
SKIP_TODO = True


@testsize.large()
def setUpModule():
    handler_test_utils.start_dev_appserver(db='testutil/test_db.sqlite')
    oauth_test_client.stub_for_oauth()


def tearDownModule():
    # Let's emit the dev_appserver's logs in case those are helpful.
    # TODO(csilvers): only emit if there are >0 failures?
    print
    print '---------------- START DEV_APPSERVER LOGS ---------------------'
    print open(handler_test_utils.dev_appserver_logfile_name()).read()
    print '----------------- END DEV_APPSERVER LOGS ----------------------'

    oauth_test_client.unstub_for_oauth()
    oauth_test_client.clear_oauth_tokens_cache()
    handler_test_utils.stop_dev_appserver()


def todo():
    """Decorator: Skip a test iff SKIP_TODO is set."""
    if SKIP_TODO:
        return unittest.skip("still marked TODO")
    return lambda func: func


def _server_hostname():
    """The hostname (http://foo:port) of the dev-appserver instance."""
    return handler_test_utils.appserver_url


class V1EndToEndTestBase(unittest.TestCase):
    def setUp(self):
        """Reset to the default user, with no special privileges."""
        self.fetcher = oauth_test_client.OAuthRequestFetcher()
        self.fetcher.set_user()

    def assertIn(self, needle, haystack):
        self.assertTrue(needle in haystack,
                        'Did not find "%s" in "%s"' % (needle, haystack))

    def assertNotIn(self, needle, haystack):
        self.assertFalse(needle in haystack,
                        'Unexpectedly found "%s" in "%s"' % (needle, haystack))

    def assertHTTPError(self, fetch_url, error_code):
        """Assert that fetching the given url raises the given HTTP error."""
        # We can't use assertRaises because we want to examine the assertion.
        try:
            self.fetcher.fetch(fetch_url, method='GET')
            self.fail("Fetching %s did not raise an expected HTTP code %d"
                      % (fetch_url, error_code))
        except urllib2.HTTPError, why:
            self.assertEqual(error_code, why.code)

    def assert400Error(self, fetch_url):
        """Assert that fetching the given url raises HTTP 400/BAD REQUEST."""
        self.assertHTTPError(fetch_url, 400)

    def assert401Error(self, fetch_url):
        """Assert that fetching the given url raises HTTP 401/UNAUTHORIZED."""
        self.assertHTTPError(fetch_url, 401)


class V1EndToEndAuthTest(V1EndToEndTestBase):
    def fetch(self, path):
        return self.fetcher.fetch(path, method='GET')

    @testsize.large()
    def test_invalid_password(self):
        self.fetcher.password = 'invalid'
        # This should fail when trying to get the access token.
        # oauth_test_client raises a RuntimeError in that case.
        self.assertRaises(RuntimeError, self.fetch, '/api/v1/user')

    @testsize.large()
    def test_user_cannot_access_developer_url(self):
        """Normal-user privileges are lower than developer."""
        self.assert401Error('/api/v1/dev/topictree')

    @testsize.large()
    def test_moderator_cannot_access_developer_url(self):
        """Moderator privileges are lower than developer."""
        self.fetcher.set_user(moderator=True)
        self.assert401Error('/api/v1/dev/topictree')

    @testsize.large()
    def test_child_access_with_anointed_client(self):
        """Under-13 child account access is allowed with anointed client."""
        self.fetcher.set_user(anointed_consumer=True, child=True)
        r = self.fetch('/api/v1/user')
        # Child account's email address should be accessible for the anointed
        # consumer.
        self.assertIn("child@example.com", r)

    @testsize.large()
    def test_child_access_without_anointed_client(self):
        """Under-13 child account access is denied without anointed client."""
        self.fetcher.set_user(anointed_consumer=False, child=True)
        self.assert401Error('/api/v1/user')

    @testsize.large()
    def test_child_access_without_anointed_client_with_open_access(self):
        """Under-13 child account access is allowed for open access content."""
        self.fetcher.set_user(anointed_consumer=False, child=True)
        r = self.fetch('/api/v1/exercises')
        self.assertIn('"exponents_2"', r)

    @testsize.large()
    def test_anointed_client_access(self):
        """Only an anointed consumer can access this url."""
        self.assert401Error('/api/v1/user/videos/SvFtmPhbNRw'
                            '/log_compatability')
        self.fetcher.set_user(anointed_consumer=True)
        # I don't bother to set all the url-parameters needed, so this
        # request will fail.  The important point is it gets far
        # enough into the handling to be looking at the url query fields.
        self.assert400Error('/api/v1/user/videos/SvFtmPhbNRw'
                            '/log_compatability')


class V1EndToEndGetTest(V1EndToEndTestBase):
    """Test all the GET methods in v1.py, except obsolete /playlist urls."""

    def fetch(self, path):
        return self.fetcher.fetch(path, method='GET')

    @testsize.large()
    def test_topics__with_content(self):
        r = self.fetch('/api/v1/topics/with_content')
        # Topic-version 11 (the default) appends '[late]' to all titles.
        self.assertIn('"title": "Art History [late]"', r)

    @testsize.large()
    def test_topicversion__version_id__topics__with_content(self):
        """2 is the non-default version in our test db."""
        r = self.fetch('/api/v1/topicversion/2/topics/with_content')
        # Topic-version 2 appends '[early]' to all titles.
        self.assertIn('"title": "Art History [early]"', r)

    @testsize.large()
    def test_topics__library__compact(self):
        r = self.fetch('/api/v1/topics/library/compact')
        self.assertIn('"title": "One Step Equations"', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__changelist(self):
        # Test that this requires developer access
        self.assert401Error('/api/v1/topicversion/2/changelist')
        # ...even if it's a non-existent url.
        self.assert401Error('/api/v1/topicversion/10000/changelist')

        self.fetcher.set_user(developer=True)

        # early version
        r = self.fetch('/api/v1/topicversion/2/changelist')
        self.assertIn('TODO(csilvers)', r)

        # later (default) version
        r = self.fetch('/api/v1/topicversion/11/changelist')
        self.assertIn('TODO(csilvers)', r)

        # non-existent version
        r = self.fetch('/api/v1/topicversion/1000/changelist')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    def test_topicversion__version_id__topic__topic_id__videos(self):
        # Test an early version and a later version.
        r = self.fetch('/api/v1/topicversion/2/topic/basic-equations/videos')
        self.assertIn('"title": "One Step Equations"', r)
        self.assertNotIn('"title": "Exponent Rules Part 1"', r)

        r = self.fetch('/api/v1/topicversion/11/topic/basic-equations/videos')
        self.assertIn('"title": "One Step Equations"', r)
        self.assertNotIn('"title": "Exponent Rules Part 1"', r)

        # Test a topic that doesn't exist in one version.
        self.assert400Error('/api/v1/topicversion/2/topic/art_of_math/videos')
        r = self.fetch('/api/v1/topicversion/11/topic/art_of_math/videos')
        self.assertEqual('[]', r)   # has a Url child, but not a Video

        # Test a super-topic.
        r = self.fetch('/api/v1/topicversion/11/topic/math/videos')
        self.assertEqual('[]', r)   # has Topic children, but no Video

        # Test a topic-version and topic-id that don't exist at all.
        self.assert400Error('/api/v1/topicversion/2/topic/no_existe/videos')
        self.assert400Error('/api/v1/topicversion/1000/topic/art_of_math'
                            '/videos')

    @testsize.large()
    def test_topic__topic_id__videos(self):
        r = self.fetch('/api/v1/topic/basic-equations/videos')
        self.assertIn('"date_added": "2012-03-28T20:37:54Z"', r)
        self.assertIn('"description": "One Step Equations"', r)
        self.assertIn('"m3u8": "http://s3.amazonaws.com/KA-youtube-converted/'
                      '9DxrF6Ttws4.m3u8/9DxrF6Ttws4.m3u8"', r)
        self.assertNotIn('"mp4": ', r)   # This video is m3u8-only
        self.assertIn('"keywords": "One, Step, Equations, CC_39336_A-REI_3"',
                      r)
        self.assertIn('"views": 43923', r)
        self.assertIn('"youtube_id": "9DxrF6Ttws4"', r)

        # Test a url with no videos.
        r = self.fetch('/api/v1/topic/art_of_math/videos')
        self.assertEqual('[]', r)

    @testsize.large()
    def test_topicversion__version_id__topic__topic_id__exercises(self):
        # Test an early version and a later version.
        r = self.fetch('/api/v1/topicversion/2/topic/basic-equations'
                       '/exercises')
        self.assertIn('"display_name": "One step equations"', r)
        self.assertNotIn('"display_name": "Exponent rules"', r)

        r = self.fetch('/api/v1/topicversion/11/topic/basic-equations'
                       '/exercises')
        self.assertIn('"display_name": "One step equations"', r)
        self.assertNotIn('"display_name": "Exponent rules"', r)

        # And a super-topic with exercises in various sub-topics
        r = self.fetch('/api/v1/topicversion/11/topic/math/exercises')
        self.assertEqual('[]', r)   # has Topic children, but no exercise

        # And one with no exercises.
        r = self.fetch('/api/v1/topicversion/11/topic/art/exercises')
        self.assertEqual('[]', r)

        # And one in a non-existent topic-version and topic-id.
        self.assert400Error('/api/v1/topicversion/2/topic/no_existe/exercises')
        self.assert400Error('/api/v1/topicversion/1000/topic/art_of_math'
                            '/exercises')

    @testsize.large()
    def test_topic__topic_id__exercises(self):
        r = self.fetch('/api/v1/topic/basic-equations/exercises')
        self.assertIn('"one_step_equations_0.5"', r)
        self.assertIn('"creation_date": "2012-03-28T20:38:50Z"', r)
        self.assertIn('"relative_url": "/exercise/one_step_equations"', r)
        self.assertIn('"short_display_name": "1step eq"', r)
        self.assertIn('"tags": []', r)

    @testsize.large()
    @todo()
    def test_topic__topic_id__progress(self):
        r = self.fetch('/api/v1/topic/basic-equations/progress')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    def test_topicversion__version_id__topictree(self):
        r = self.fetch('/api/v1/topicversion/2/topictree')
        # Here we keep track of leading spaces to make sure of indentation.
        self.assertIn('                            '
                      '"short_display_name": "Exp. Rules"', r)
        self.assertIn('                    '
                      '"title": "Exponents (Basic) [early]"', r)
        self.assertIn('                            '
                      '"relative_url": "/video/domain-and-range-1"', r)
        self.assertIn('            '
                      '"title": "Mathematics [early]"', r)
        self.assertNotIn('[late]', r)
        self.assertNotIn('The History of Art in 3 Minutes', r)  # only in v11

        r = self.fetch('/api/v1/topicversion/11/topictree')
        self.assertIn('                            '
                      '"short_display_name": "Exp. Rules"', r)
        self.assertIn('                    '
                      '"title": "Exponents (Basic) [late]"', r)
        self.assertIn('                            '
                      '"relative_url": "/video/domain-and-range-1"', r)
        self.assertIn('            '
                      '"title": "Mathematics [late]"', r)
        self.assertIn('The History of Art in 3 Minutes', r)
        self.assertNotIn('Mathematics of Art', r)  # no hidden topics
        self.assertNotIn('[early]', r)

        self.assert400Error('/api/v1/topicversion/1000/topictree')

    @testsize.large()
    def test_topictree(self):
        r = self.fetch('/api/v1/topictree')
        # Here we keep track of leading spaces to make sure of indentation.
        self.assertIn('                            '
                      '"display_name": "Exponent rules"', r)
        self.assertIn('                            '
                      '"display_name": "One step equations"', r)
        self.assertIn('                            '
                      '"title": "Absolute Value 1"', r)
        self.assertIn('            "id": "math"', r)
        self.assertIn('                    "readable_id": '
                      '"courbet--the-artist-s-studio--1854-55"', r)
        self.assertIn('                    '
                      '"title": "The History of Art in 3 Minutes"', r)
        self.assertIn('            "standalone_title": "All About Art"', r)
        self.assertIn('            "title": "Art History [late]"', r)
        self.assertIn('    "title": "The Root of All Knowledge [late]"', r)
        self.assertNotIn('"title": "The Root of All Knowledge [early]"', r)
        self.assertNotIn('Mathematics of Art', r)  # no hidden topics

    @testsize.large()
    @todo()
    def test_dev__topictree__problems(self):
        # TODO(james): uncomment once this becomes developer_required in v1.py
        #self.assert401Error('/api/v1/dev/topictree/problems')
        self.fetcher.set_user(developer=True)

        r = self.fetch('/api/v1/dev/topictree/problems')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    def test_dev__topicversion__version_id__topic__topic_id__topictree(self):
        self.assert401Error('/api/v1/dev/topicversion/2/topic/math/topictree')

        # Here we keep track of leading spaces to make sure of indentation.
        self.fetcher.set_user(developer=True)
        r = self.fetch('/api/v1/dev/topicversion/2/topic/math/topictree')
        self.assertIn('                    '
                      '"title": "Exponent Rules Part 1"', r)
        self.assertIn('            "id": "basic-equations"', r)
        self.assertIn('    "standalone_title": "All About Math"', r)
        self.assertIn('    "title": "Mathematics [early]"', r)

        r = self.fetch('/api/v1/dev/topicversion/11/topic/math/topictree')
        self.assertIn('                    '
                      '"title": "Exponent Rules Part 1"', r)
        self.assertIn('            "id": "basic-equations"', r)
        self.assertIn('    "standalone_title": "All About Math"', r)
        self.assertIn('    "title": "Mathematics [late]"', r)

        # In dev mode, we should get hidden topics
        r = self.fetch('/api/v1/dev/topicversion/11/topic/root/topictree')
        self.assertIn('Mathematics of Art', r)  # no hidden topics

        self.assert400Error('/api/v1/dev/topicversion/1000/topic/math'
                            '/topictree')
        self.assert400Error('/api/v1/dev/topicversion/2/topic/does_not_exist'
                            '/topictree')

    @testsize.large()
    def test_dev__topicversion__version_id__topictree(self):
        self.assert401Error('/api/v1/dev/topicversion/2/topictree')
        self.fetcher.set_user(developer=True)

        r = self.fetch('/api/v1/dev/topicversion/2/topictree')
        self.assertIn('    "title": "The Root of All Knowledge [early]"', r)
        self.assertNotIn('[late]', r)

        r = self.fetch('/api/v1/dev/topicversion/11/topictree')
        self.assertIn('    "title": "The Root of All Knowledge [late]"', r)
        self.assertNotIn('[early]', r)

        r = self.assert400Error('/api/v1/dev/topicversion/1000/topictree')

    @testsize.large()
    def test_dev__topictree(self):
        self.assert401Error('/api/v1/dev/topictree')
        self.fetcher.set_user(developer=True)
        r = self.fetch('/api/v1/dev/topictree')
        self.assertIn('    "title": "The Root of All Knowledge [late]"', r)
        self.assertNotIn('[early]', r)

    @testsize.large()
    def test_topicversion__version_id__search__query(self):
        r = self.fetch('/api/v1/topicversion/2/search/basic')
        self.assertIn('"title": "Exponents (Basic) [early]"', r)
        self.assertIn('"id": "exponent_rules', r)         # exercise
        self.assertIn('"id": "exponent-rules-part-1', r)  # video
        self.assertIn('"title": "Equations (one-step) [early]"', r)
        self.assertNotIn('"title": "Domain and Range 1"', r)
        self.assertNotIn('courbet--the-artist-s-studio--1854-55', r)

        r = self.fetch('/api/v1/topicversion/11/search/basic')
        self.assertIn('"title": "Exponents (Basic) [late]"', r)
        self.assertIn('"id": "exponent_rules', r)         # exercise
        self.assertIn('"id": "exponent-rules-part-1', r)  # video
        self.assertIn('"title": "Equations (one-step) [late]"', r)
        self.assertNotIn('"title": "Domain and Range 1"', r)
        self.assertNotIn('courbet--the-artist-s-studio--1854-55', r)

        r = self.fetch('/api/v1/topicversion/11/search/Studio')
        self.assertNotIn('"title": "Exponents (Basic) [late]"', r)
        self.assertIn('courbet--the-artist-s-studio--1854-55', r)

        # This should only match for topicversion 11, not 2.
        r = self.fetch('/api/v1/topicversion/11/search/Minutes')
        self.assertIn('"title": "The History of Art in 3 Minutes"', r)
        r = self.fetch('/api/v1/topicversion/2/search/Minutes')
        self.assertNotIn('Minutes', r)

        # Gives no results
        r = self.fetch('/api/v1/topicversion/11/search/NadaNothingZilch')
        self.assertIn('"nodes": []', r)
        # Try an invalid topic-version
        self.assert400Error('/api/v1/topicversion/1000/search/Minutes')

    @testsize.large()
    def test_topicversion__version_id__topic__topic_id(self):
        r = self.fetch('/api/v1/topicversion/2/topic/math')
        self.assertIn('"title": "Exponents (Basic) [early]"', r)
        self.assertIn('"title": "Equations (one-step) [early]"', r)
        self.assertIn('"title": "Other [early]"', r)
        self.assertIn('"standalone_title": "All About Math"', r)
        self.assertNotIn('[late]', r)

        r = self.fetch('/api/v1/topicversion/11/topic/math')
        self.assertIn('"title": "Exponents (Basic) [late]"', r)
        self.assertIn('"title": "Equations (one-step) [late]"', r)
        self.assertIn('"title": "Other [late]"', r)
        self.assertIn('"standalone_title": "All About Math"', r)
        self.assertNotIn('[early]', r)

        self.assert400Error('/api/v1/topicversion/1000/topic/math')
        self.assert400Error('/api/v1/topicversion/2/topic/does_not_exist')

    @testsize.large()
    def test_topic__topic_id(self):
        r = self.fetch('/api/v1/topic/math')
        self.assertIn('"children":', r)
        self.assertIn('"id": "basic-exponents"', r)
        self.assertIn('"title": "Exponents (Basic) [late]"', r)
        self.assertNotIn('"title": "Exponents (Basic) [early]"', r)
        self.assertIn('"description": "A super-topic I made up for this test"',
                      r)
        self.assertIn('"topic_page_url": "/math"', r)

        self.assert400Error('/api/v1/topic/does_not_exist')

    @testsize.large()
    def test_topicversion__version_id__topic__topic_id__topic_page(self):
        # Test an early version and a later version.
        r = self.fetch('/api/v1/topicversion/2/topic/basic-equations'
                       '/topic-page')
        self.assertIn('"title": "One Step Equations"', r)
        self.assertIn('"title": "Absolute Value 1"', r)
        self.assertIn('"topic_page_url": "/math/basic-equations"', r)

        r = self.fetch('/api/v1/topicversion/11/topic/basic-equations'
                       '/topic-page')
        self.assertIn('"title": "One Step Equations"', r)
        self.assertNotIn('"title": "Absolute Value 1"', r)
        self.assertIn('"topic_page_url": "/math/basic-equations"', r)

        # Test a topic that doesn't exist in one version.
        r = self.fetch('/api/v1/topicversion/2/topic/art_of_math/topic-page')
        self.assertEqual('{}', r)
        r = self.fetch('/api/v1/topicversion/11/topic/art_of_math/topic-page')
        self.assertIn('"title": "Mathematics of Art"', r)

        # Test a super-topic.
        r = self.fetch('/api/v1/topicversion/11/topic/math/topic-page')
        self.assertIn('"child_count": 2', r)
        self.assertIn('"standalone_title": "Mathematics (other)"', r)
        self.assertIn('"title": "Mathematics [late]"', r)
        self.assertNotIn('[early]', r)

        # Test a topic-version and topic-id that don't exist at all.
        self.assert400Error('/api/v1/topicversion/1000/topic/art_of_math'
                            '/topic-page')
        r = self.fetch('/api/v1/topicversion/2/topic/noexist/topic-page')
        self.assertEqual('{}', r)

    @testsize.large()
    def test_topic__topic_id__topic_page(self):
        r = self.fetch('/api/v1/topic/math/topic-page')
        self.assertIn('"teaser_html": "Introduction to exponent rules"', r)
        self.assertIn('"child_count": 2', r)
        self.assertIn('"standalone_title": "Mathematics (other)"', r)
        self.assertIn('"title": "Mathematics [late]"', r)
        self.assertNotIn('[early]', r)

        # Shows hidden topics too.
        r = self.fetch('/api/v1/topic/art_of_math/topic-page')
        self.assertIn('"title": "Mathematics of Art"', r)

        r = self.fetch('/api/v1/topic/no-existe/topic-page')
        self.assertEqual('{}', r)

    @testsize.large()
    def test_topicversion__version_id__maplayout(self):
        r = self.fetch('/api/v1/topicversion/2/maplayout')
        self.assertIn('"icon_url": '
                      '"/images/power-mode/badges/default-40x40.png"', r)
        self.assertIn('"id": "basic-equations"', r),
        self.assertIn('"standalone_title": "One-Step Equations"', r)
        self.assertIn('"x": 0', r)
        self.assertNotIn('"x": 1', r)
        self.assertIn('"y": 6', r)
        self.assertIn('"id": "basic-exponents"', r),

        r = self.fetch('/api/v1/topicversion/11/maplayout')
        self.assertIn('"icon_url": '
                      '"/images/power-mode/badges/default-40x40.png"', r)
        self.assertIn('"id": "basic-equations"', r),
        self.assertIn('"standalone_title": "One-Step Equations"', r)
        self.assertIn('"x": 1', r)
        self.assertNotIn('"x": 0', r)
        self.assertIn('"y": 6', r)
        self.assertIn('"id": "basic-exponents"', r),

    @testsize.large()
    def test_maplayout(self):
        r = self.fetch('/api/v1/maplayout')
        self.assertIn('"icon_url": '
                      '"/images/power-mode/badges/default-40x40.png"', r)
        self.assertIn('"id": "basic-equations"', r),
        self.assertIn('"standalone_title": "One-Step Equations"', r)
        self.assertIn('"x": 1', r)
        self.assertIn('"y": 6', r)
        self.assertIn('"id": "basic-exponents"', r),

    @testsize.large()
    def test_topicversion__default__id(self):
        r = self.fetch('/api/v1/topicversion/default/id')
        self.assertEqual('11', r)

    @testsize.large()
    @todo()
    def test_dev__task_message(self):
        self.assert401Error('/api/v1/dev/task_message')
        self.fetcher.set_user(developer=True)

        r = self.fetch('/api/v1/dev/task_message')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    def test_topicversion__version_id__topic__topic_id__children(self):
        r = self.fetch('/api/v1/topicversion/2/topic/math/children')
        self.assertIn('"title": "Exponents (Basic) [early]"', r)
        self.assertIn('"title": "Equations (one-step) [early]"', r)
        self.assertIn('"title": "Other [early]"', r)
        self.assertNotIn('[late]', r)

        r = self.fetch('/api/v1/topicversion/11/topic/math/children')
        self.assertIn('"title": "Exponents (Basic) [late]"', r)
        self.assertIn('"title": "Equations (one-step) [late]"', r)
        self.assertIn('"title": "Other [late]"', r)
        self.assertNotIn('[early]', r)

        r = self.fetch('/api/v1/topicversion/11/topic/art/children')
        self.assertIn('"readable_id": "courbet--the-artist-s-studio--1854-55"',
                      r)
        self.assertIn('"title": "The History of Art in 3 Minutes"', r)

    @testsize.large()
    def test_topic__topic_id__children(self):
        r = self.fetch('/api/v1/topic/math/children')
        self.assertIn('"title": "Exponents (Basic) [late]"', r)
        self.assertIn('"title": "Equations (one-step) [late]"', r)
        self.assertIn('"title": "Other [late]"', r)

        r = self.fetch('/api/v1/topic/art/children')
        self.assertIn('"readable_id": "courbet--the-artist-s-studio--1854-55"',
                      r)

    @testsize.large()
    def test_topicversion__version_id(self):
        self.assert401Error('/api/v1/topicversion/2')

        self.fetcher.set_user(developer=True)
        r = self.fetch('/api/v1/topicversion/2')
        self.assertIn('"number": 2', r)
        self.assertIn('"created_on": "2012-03-28T20:43:04Z"', r)

        r = self.fetch('/api/v1/topicversion/11')
        self.assertIn('"number": 11', r)
        self.assertIn('"created_on": "2012-03-30T21:34:28Z"', r)

        r = self.fetch('/api/v1/topicversion/1000')
        self.assertEqual('null', r)    # TODO(csilvers): should this be {} ?

    @testsize.large()
    def test_topicversions__(self):
        r = self.fetch('/api/v1/topicversions/')
        self.assertIn('"copied_from_number": 11', r)
        self.assertIn('"number": 11', r)
        self.assertIn('"created_on": "2012-03-30T21:34:28Z"', r)
        self.assertIn('"copied_from_number": null', r)
        self.assertIn('"number": 2', r)
        self.assertIn('"made_default_on": "2012-03-29T02:02:54Z"', r)

    @testsize.large()
    def test_topicversion__version_id__unused_content(self):
        r = self.fetch('/api/v1/topicversion/2/unused_content')
        self.assertIn('"title": "Mathematics & art"', r)
        self.assertIn('"title": "The History of Art in 3 Minutes"', r)

        r = self.fetch('/api/v1/topicversion/11/unused_content')
        self.assertEqual('[]', r)

        self.assert400Error('/api/v1/topicversion/1000/unused_content')

    @testsize.large()
    @todo()
    def test_topicversion__version_id__url__url_id(self):
        r = self.fetch('/api/v1/topicversion/<version_id>/url/<url_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_url__url_id(self):
        r = self.fetch('/api/v1/url/<url_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    def test_videos__video_id__explore_url(self):
        # A video with an explore-id
        r = self.fetch('/api/v1/videos/SvFtmPhbNRw/explore_url')
        self.assertEqual('"http://en.wikipedia.org/wiki/Gustave_Courbet"', r)

        # A video with no explore-id
        r = self.fetch('/api/v1/videos/NvGTCzAfvr0/explore_url')
        self.assertEqual('null', r)

        # An invalid video-id
        r = self.fetch('/api/v1/videos/no_existe/explore_url')
        self.assertEqual('null', r)

    @testsize.large()
    def test_exercises(self):
        r = self.fetch('/api/v1/exercises')
        self.assertIn('"exponents_2"', r)
        self.assertIn('"creation_date": "2012-03-28T20:38:49Z"', r)
        self.assertIn('"one_step_equations_0.5"', r)
        self.assertIn('"display_name": "One step equations"', r)
        self.assertIn('"short_display_name": "1step eq"', r)
        self.assertIn('"tags": []', r)

    @testsize.large()
    def test_topicversion__version_id__exercises__exercise_name(self):
        r = self.fetch('/api/v1/topicversion/2/exercises/exponent_rules')
        self.assertIn('"display_name": "Exponent rules"', r)
        self.assertIn('"exponent-rules-part-1"', r)

        r = self.fetch('/api/v1/topicversion/11/exercises/exponent_rules')
        self.assertIn('"display_name": "Exponent rules"', r)
        self.assertIn('"exponent-rules-part-1"', r)

        r = self.fetch('/api/v1/topicversion/2/exercises/no_existe')
        self.assertEqual('null', r)

        self.assert400Error('/api/v1/topicversion/1000/exercises'
                            '/exponent-rules')

    @testsize.large()
    def test_exercises__exercise_name(self):
        r = self.fetch('/api/v1/exercises/exponent_rules')
        self.assertIn('"display_name": "Exponent rules"', r)
        self.assertIn('"exponent-rules-part-1"', r)

    @testsize.large()
    @todo()
    def test_exercises__recent(self):
        r = self.fetch('/api/v1/exercises/recent')
        # TODO(csilvers): mock out the clock for this, so one of the
        # exercises is recent but the other isn't.
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_exercises__exercise_name__followup_exercises(self):
        r = self.fetch('/api/v1/exercises/<exercise_name>/followup_exercises')
        self.assertIn('TODO(csilvers): add this to the db', r)

    @testsize.large()
    def test_exercises__exercise_name__videos(self):
        r = self.fetch('/api/v1/exercises/exponent_rules/videos')
        self.assertIn('"relative_url": "/video/exponent-rules-part-1"', r)

        r = self.fetch('/api/v1/exercises/no_existe/videos')
        self.assertEqual('[]', r)

    @testsize.large()
    def test_topicversion__version_id__videos__video_id(self):
        r = self.fetch('/api/v1/topicversion/2/videos/NvGTCzAfvr0')
        self.assertIn('"relative_url": "/video/absolute-value-1"', r)
        self.assertIn('"date_added": "2012-03-28T20:37:56Z"', r)
        self.assertIn('"png": "http://s3.amazonaws.com/KA-youtube-converted'
                      '/NvGTCzAfvr0.mp4/NvGTCzAfvr0.pn', r)
        self.assertNotIn('"mp4"', r)   # this video is png-only
        self.assertIn('"views": 99221', r)

        r = self.fetch('/api/v1/topicversion/11/videos/NvGTCzAfvr0')
        self.assertIn('"relative_url": "/video/absolute-value-1"', r)
        self.assertIn('"date_added": "2012-03-28T20:37:56Z"', r)
        self.assertIn('"png": "http://s3.amazonaws.com/KA-youtube-converted'
                      '/NvGTCzAfvr0.mp4/NvGTCzAfvr0.pn', r)
        self.assertNotIn('"mp4"', r)   # this video is png-only
        self.assertIn('"views": 99221', r)

        r = self.fetch('/api/v1/topicversion/2/videos/no_existe')
        self.assertEqual('null', r)
        self.assert400Error('/api/v1/topicversion/1000/videos/NvGTCzAfvr0')

    @testsize.large()
    def test_videos__video_id(self):
        r = self.fetch('/api/v1/videos/NvGTCzAfvr0')
        self.assertIn('"relative_url": "/video/absolute-value-1"', r)
        self.assertIn('"date_added": "2012-03-28T20:37:56Z"', r)
        self.assertIn('"png": "http://s3.amazonaws.com/KA-youtube-converted'
                      '/NvGTCzAfvr0.mp4/NvGTCzAfvr0.pn', r)
        self.assertNotIn('"mp4"', r)   # this video is png-only
        self.assertIn('"views": 99221', r)

        r = self.fetch('/api/v1/videos/no_existe')
        self.assertEqual('null', r)

    @testsize.large()
    @todo()
    def test_videos__recent(self):
        # TODO(csilvers): mock out time so we can test this
        r = self.fetch('/api/v1/videos/recent')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    def test_videos__video_id__exercises(self):
        r = self.fetch('/api/v1/videos/kITJ6qH7jS0/exercises')
        self.assertIn('"relative_url": "/exercise/exponent_rules"', r)
        self.assertIn('"name": "exponent_rules"', r)

        r = self.fetch('/api/v1/videos/SvFtmPhbNRw/exercises')
        self.assertEqual('[]', r)

        r = self.fetch('/api/v1/videos/no_existe/exercises')
        self.assertEqual('[]', r)

    @testsize.large()
    @todo()
    def test_videos__topic_id__video_id__play(self):
        r = self.fetch('/api/v1/videos/<topic_id>/<video_id>/play')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_commoncore(self):
        r = self.fetch('/api/v1/commoncore')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    def test_videos__youtube_id__youtubeinfo(self):
        self.assert401Error('/api/v1/videos/kITJ6qH7jS0/youtubeinfo')

        self.fetcher.set_user(developer=True)
        r = self.fetch('/api/v1/videos/kITJ6qH7jS0/youtubeinfo')
        self.assertIn('"relative_url": "/video/exponent-rules-part-1"', r)
        self.assertIn('"views": 175660', r)
        self.assertIn('"youtube_id": "kITJ6qH7jS', r)

    @testsize.large()
    @todo()
    def test_user(self):
        r = self.fetch('/api/v1/user')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__username_available(self):
        r = self.fetch('/api/v1/user/username_available')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__promo__promo_name(self):
        r = self.fetch('/api/v1/user/promo/<promo_name>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__profile(self):
        r = self.fetch('/api/v1/user/profile')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__coaches(self):
        r = self.fetch('/api/v1/user/coaches')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__students(self):
        r = self.fetch('/api/v1/user/students')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__studentlists(self):
        r = self.fetch('/api/v1/user/studentlists')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__videos(self):
        r = self.fetch('/api/v1/user/videos')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__videos__youtube_id(self):
        r = self.fetch('/api/v1/user/videos/<youtube_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__videos__youtube_id__log_compatability(self):
        r = self.fetch('/api/v1/user/videos/<youtube_id>/log_compatability')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__topic__topic_id__exercises__next(self):
        r = self.fetch('/api/v1/user/topic/<topic_id>/exercises/next')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__exercises(self):
        r = self.fetch('/api/v1/user/exercises')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__topic__topic_id__exercises(self):
        r = self.fetch('/api/v1/user/topic/<topic_id>/exercises')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__students__progress__summary(self):
        r = self.fetch('/api/v1/user/students/progress/summary')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__exercises__exercise_name(self):
        r = self.fetch('/api/v1/user/exercises/<exercise_name>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__exercises__exercise_name__followup_exercises(self):
        r = self.fetch('/api/v1/user/exercises/<exercise_name>'
                       '/followup_exercises')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__topics(self):
        r = self.fetch('/api/v1/user/topics')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__topic__topic_id(self):
        r = self.fetch('/api/v1/user/topic/<topic_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__exercises__reviews__count(self):
        r = self.fetch('/api/v1/user/exercises/reviews/count')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__exercises__exercise_name__log(self):
        r = self.fetch('/api/v1/user/exercises/<exercise_name>/log')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__videos__youtube_id__log(self):
        r = self.fetch('/api/v1/user/videos/<youtube_id>/log')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    def test_badges(self):
        r = self.fetch('/api/v1/badges')
        self.assertIn('"icon_src": "%s/images/badges/sun-small.png"'
                      % _server_hostname(),
                      r)
        self.assertIn('"badge_category": 3', r)

    @testsize.large()
    def test_badges__categories(self):
        r = self.fetch('/api/v1/badges/categories')
        self.assertIn('"icon_src": "%s/images/badges/sun-small.png"'
                      % _server_hostname(),
                      r)
        self.assertIn('"category": 3', r)

    @testsize.large()
    def test_badges__categories__category(self):
        r = self.fetch('/api/v1/badges/categories/3')
        self.assertIn('"icon_src": "%s/images/badges/sun-small.png"'
                      % _server_hostname(),
                      r)
        self.assertIn('"category": 3', r)

    @testsize.large()
    @todo()
    def test_user__badges(self):
        r = self.fetch('/api/v1/user/badges')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__activity(self):
        r = self.fetch('/api/v1/user/activity')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_autocomplete(self):
        r = self.fetch('/api/v1/autocomplete')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_dev__backupmodels(self):
        self.assert401Error('/api/v1/dev/backupmodels')
        self.fetcher.set_user(developer=True)

        r = self.fetch('/api/v1/dev/backupmodels')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_dev__protobufquery(self):
        self.assert401Error('/api/v1/dev/protobufquery')
        self.fetcher.set_user(developer=True)

        r = self.fetch('/api/v1/dev/protobufquery')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_dev__protobuf__entity(self):
        self.assert401Error('/api/v1/dev/protobuf/<entity>')
        self.fetcher.set_user(developer=True)

        r = self.fetch('/api/v1/dev/protobuf/<entity>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_dev__problems(self):
        self.assert401Error('/api/v1/dev/problems')
        self.fetcher.set_user(developer=True)

        r = self.fetch('/api/v1/dev/problems')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_dev__videos(self):
        self.assert401Error('/api/v1/dev/videos')
        self.fetcher.set_user(developer=True)

        r = self.fetch('/api/v1/dev/videos')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_dev__users(self):
        self.assert401Error('/api/v1/dev/users')
        self.fetcher.set_user(developer=True)

        r = self.fetch('/api/v1/dev/users')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__students__progressreport(self):
        r = self.fetch('/api/v1/user/students/progressreport')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__goals(self):
        r = self.fetch('/api/v1/user/goals')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__goals__current(self):
        r = self.fetch('/api/v1/user/goals/current')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__students__goals(self):
        r = self.fetch('/api/v1/user/students/goals')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__goals__id(self):
        r = self.fetch('/api/v1/user/goals/<id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    def test_avatars(self):
        r = self.fetch('/api/v1/avatars')
        self.assertIn('"image_src": "/images/avatars/leaf-green.png"', r)

    @testsize.large()
    def test_dev__version(self):
        r = self.fetch('/api/v1/dev/version')
        self.assertIn('"version_id": "', r)


class V1EndToEndDeleteTest(V1EndToEndTestBase):
    '''Test all the DELETE methods in v1.py.'''

    # TODO(csilvers): reset the database before each of these.

    def fetch(self, path):
        self.fetcher.fetch(path, method='DELETE')

    @testsize.large()
    @todo()
    def test_user__studentlists__list_key(self):
        r = self.fetch('/api/v1/user/studentlists/list_key>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__goals__id(self):
        r = self.fetch('/api/v1/user/goals/id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__goals(self):
        r = self.fetch('/api/v1/user/goals')
        self.assertIn('TODO(csilvers)', r)


class V1EndToEndPostTest(V1EndToEndTestBase):
    '''Test all the POST methods in v1.py.'''
    # TODO(csilvers): reset the database before each of these.

    def fetch(self, path):
        self.fetcher.fetch(path, method='POST')

    # This is a GET request, but changes state so should be POST or PUT.

    @testsize.large()
    @todo()
    def test_topicversion__version_id__setdefault(self):
        self.methd = 'GET'
        r = self.fetch('/api/v1/topicversion/<version_id>/setdefault')
        self.assertIn('TODO(csilvers)', r)

    # Note some of these also accept PUT, but we don't seem to distinguish.

    @testsize.large()
    @todo()
    def test_topicversion__version_id__exercises__exercise_name(self):
        r = self.fetch('/api/v1/topicversion/version_id'
                       '/exercises/exercise_name')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__videos__(self):
        r = self.fetch('/api/v1/topicversion/version_id/videos/')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__videos__video_id(self):
        r = self.fetch('/api/v1/topicversion/version_id/videos/video_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__profile(self):
        r = self.fetch('/api/v1/user/profile')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__badges__public(self):
        r = self.fetch('/api/v1/user/badges/public')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_parentsignup(self):
        r = self.fetch('/api/v1/parentsignup')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_videos__(self):
        r = self.fetch('/api/v1/videos/')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_videos__video_id(self):
        r = self.fetch('/api/v1/videos/video_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__deletechange(self):
        r = self.fetch('/api/v1/topicversion/version_id/deletechange')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__topic__parent_id__addchild(self):
        r = self.fetch('/api/v1/topicversion/version_id/topic/parent_id'
                       '/addchild')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topic__parent_id__addchild(self):
        r = self.fetch('/api/v1/topic/parent_id/addchild')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__topic__parent_id__deletechild(self):
        r = self.fetch('/api/v1/topicversion/version_id/topic/parent_id'
                       '/deletechild')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topic__parent_id__deletechild(self):
        r = self.fetch('/api/v1/topic/parent_id/deletechild')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__topic__old_parent_id__movechild(self):
        r = self.fetch('/api/v1/topicversion/version_id/topic/old_parent_id'
                       '/movechild')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topic__old_parent_id__movechild(self):
        r = self.fetch('/api/v1/topic/old_parent_id/movechild')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__topic__topic_id__ungroup(self):
        r = self.fetch('/api/v1/topicversion/version_id/topic/topic_id'
                       '/ungroup')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topic__topic_id__ungroup(self):
        r = self.fetch('/api/v1/topic/topic_id/ungroup')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_videos__video_id__download_available(self):
        r = self.fetch('/api/v1/videos/video_id/download_available')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__promo__promo_name(self):
        r = self.fetch('/api/v1/user/promo/promo_name>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__studentlists(self):
        r = self.fetch('/api/v1/user/studentlists')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__videos__youtube_id__log(self):
        r = self.fetch('/api/v1/user/videos/youtube_id/log')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__exercises__exercise_name__problems__problem_number__attempt(
        self):
        r = self.fetch('/api/v1/user/exercises/exercise_name'
                       '/problems/problem_number/attempt')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__exercises__exercise_name__problems__problem_number__hint(
        self):
        r = self.fetch('/api/v1/user/exercises/<exercise_name>'
                       '/problems/<problem_number>/hint')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__exercises__exercise_name__reset_streak(self):
        r = self.fetch('/api/v1/user/exercises/exercise_name/reset_streak')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__exercises__exercise_name__wrong_attempt(self):
        r = self.fetch('/api/v1/user/exercises/exercise_name/wrong_attempt')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_developers__add(self):
        r = self.fetch('/api/v1/developers/add')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_developers__remove(self):
        r = self.fetch('/api/v1/developers/remove')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_coworkers__add(self):
        r = self.fetch('/api/v1/coworkers/add')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_coworkers__remove(self):
        r = self.fetch('/api/v1/coworkers/remove')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__goals(self):
        r = self.fetch('/api/v1/user/goals')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_exercises__exercise_name(self):
        r = self.fetch('/api/v1/exercises/exercise_name>')
        self.assertIn('TODO(csilvers)', r)


class V1EndToEndPutTest(V1EndToEndTestBase):
    '''Test all the PUT methods in v1.py.'''
    # TODO(csilvers): reset the database before each of these.

    def fetch(self, path):
        self.fetcher.fetch(path, method='PUT')

    @testsize.large()
    @todo()
    def test_dev__topicversion__version_id__topic__topic_id__topictree(self):
        r = self.fetch('/api/v1/dev/topicversion/<version_id>/topic/<topic_id>'
                       '/topictree')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_dev__topicversion__version_id__topictree(self):
        r = self.fetch('/api/v1/dev/topicversion/version_id/topictree')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_dev__topictree__init__publish(self):
        r = self.fetch('/api/v1/dev/topictree/init/publish>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_dev__topictree(self):
        r = self.fetch('/api/v1/dev/topictree')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__topic__topic_id(self):
        r = self.fetch('/api/v1/topicversion/version_id/topic/topic_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topic__topic_id(self):
        r = self.fetch('/api/v1/topic/topic_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__maplayout(self):
        r = self.fetch('/api/v1/topicversion/version_id/maplayout')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_maplayout(self):
        r = self.fetch('/api/v1/maplayout')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id(self):
        r = self.fetch('/api/v1/topicversion/version_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__url__(self):
        r = self.fetch('/api/v1/topicversion/version_id/url/')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_topicversion__version_id__url__url_id(self):
        r = self.fetch('/api/v1/topicversion/version_id/url/url_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_url__(self):
        r = self.fetch('/api/v1/url/')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_url__url_id(self):
        r = self.fetch('/api/v1/url/url_id>')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_videos__video_id__explore_url(self):
        r = self.fetch('/api/v1/videos/video_id/explore_url')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__coaches(self):
        r = self.fetch('/api/v1/user/coaches')
        self.assertIn('TODO(csilvers)', r)

    @testsize.large()
    @todo()
    def test_user__goals__id(self):
        r = self.fetch('/api/v1/user/goals/id>')
        self.assertIn('TODO(csilvers)', r)
