#!/usr/bin/python
# -*- coding: utf-8 -*-
import urllib
import logging
import re
import time
# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import urlfetch

import webapp2
from webapp2_extras.routes import DomainRoute
from webapp2_extras.routes import RedirectRoute

#from google.appengine.ext.webapp import template
#template.register_template_library('templatetags')

# It's important to have this prior to the imports below that require imports
# to request_handler.py. The structure of the imports are such that this
# module causes a lot of circular imports to happen, so including it once out
# the way at first seems to fix some of those issues.
import templatetags  # @UnusedImport

import devpanel.handlers
import bulk_update.handler
import request_cache
from gae_mini_profiler import profiler
from gae_bingo.middleware import GAEBingoWSGIMiddleware
import autocomplete
import coaches
import knowledgemap.handlers
#import youtube_sync
import warmup
import login
import homepage
import helpus
import rssblog

from third_party import search

import request_handler
from app import App
import util
import user_util
import exercise_statistics
import activity_summary
import dashboard.handlers
import exercises.handlers
import exercises.handler_raw
import exercisestats.report
import exercisestats.report_json
import exercisestats.exercisestats_util
from gandalf.bridge import gandalf
import github
import paypal.handlers
import smarthistory
import scratchpads.handlers
import topics
import goals.handlers
import appengine_stats
import stories.handlers
import summer.handlers
import common_core.handlers
import unisubs.handlers
import api.jsonify
import socrates.handlers
import labs.labs_request_handler
import labs.explorations
import layer_cache
from knowledgemap import kmap_editor

import topic_models
import video_models
from user_models import UserData
from video_models import Video
from url_model import Url
from exercise_video_model import ExerciseVideo
from topic_models import Topic
from discussion import comments, qa, voting
import discussion.handlers
from about import blog, util_about
from coach_resources import util_coach, schools_blog
import phantom_users.handlers
import badges.custom_badge_handlers
import badges.handlers
from mailing_lists import util_mailing_lists
import profiles.handlers
from custom_exceptions import MissingVideoException, PageNotFoundException
from oauth_provider import apps as oauth_apps
from phantom_users.cloner import Clone
from image_cache import ImageCache
from api.auth.xsrf import ensure_xsrf_cookie
import redirects.handlers
import robots
from importer.handlers import ImportHandler
import wsgi_compat
import os
import library


class VideoDataTest(request_handler.RequestHandler):
    @user_util.developer_required
    def get(self):
        self.response.out.write('<html>')
        videos = Video.all()
        for video in videos:
            self.response.out.write('<P>Title: ' + video.title)

class GenerateLibraryContent(request_handler.RequestHandler):

    @user_util.open_access
    def post(self):
        # We support posts so we can fire task queues at this handler
        self.get(from_task_queue = True)

    @user_util.open_access
    def get(self, from_task_queue = False):
        library.library_content_html(bust_cache=True)

        if not from_task_queue:
            self.redirect("/")

class TopicPage(request_handler.RequestHandler):
    @staticmethod
    def show_topic(handler, topic):
        selected_topic = topic
        parent_topic = db.get(topic.parent_keys[0])

        # If the parent is a supertopic, use that instead
        if parent_topic.id in Topic._super_topic_ids:
            topic = parent_topic
        elif not (topic.id in Topic._super_topic_ids or
                  topic.has_children_of_type(["Video"])):
            handler.redirect("/", True)
            return

        template_values = {
            "main_topic": topic,
            "selected_topic": selected_topic,
        }
        handler.render_jinja2_template('viewtopic.html', template_values)

    @user_util.open_access
    @ensure_xsrf_cookie
    def get(self, path):
        """ Display a topic page if the URL matches a pre-existing topic,
        such as /math/algebra or /algebra

        NOTE: Since there is no specific route we are matching,
        this handler is registered as the default handler,
        so unrecognized paths will return a 404.
        """
        if path.endswith('/'):
            # Canonical paths do not have trailing slashes
            path = path[:-1]

        path_list = path.split('/')
        if len(path_list) > 0:
            # Only look at the actual topic ID
            topic = topic_models.Topic.get_by_id(path_list[-1])

            if topic and topic.parent_keys:
                if path != topic.get_extended_slug():
                    # If the topic ID is found but the path is incorrect,
                    # redirect the user to the canonical path
                    self.redirect("/%s" % topic.get_extended_slug(), True)
                    return

                TopicPage.show_topic(self, topic)
                return

        # error(404) sets the status code to 404. Be aware that execution
        # continues after the .error call.
        self.error(404)
        raise PageNotFoundException("Page not found")


# New video view handler. The URI format is a topic path followed by /v/ and
# then the video identifier, i.e.:
#   /math/algebra/introduction-to-algebra/v/origins-of-algebra
class ViewVideo(request_handler.RequestHandler):

    @staticmethod
    def show_video(handler, readable_id, topic_id,
                   redirect_to_canonical_url=False):
        topic = None
        query_string = ''

        if topic_id is not None and len(topic_id) > 0:
            topic = Topic.get_by_id(topic_id)

        # If a topic_id wasn't specified or the specified topic wasn't found
        # use the first topic for the requested video.
        if topic is None:
            # Get video by readable_id to get the first topic for the video
            video = Video.get_for_readable_id(readable_id)
            if video is None:
                raise MissingVideoException("Missing video '%s'" %
                                            readable_id)

            topic = video.first_topic()
            if not topic:
                raise MissingVideoException("No topic has video '%s'" %
                                            readable_id)

            if handler.request.query_string:
                query_string = '?' + handler.request.query_string

            redirect_to_canonical_url = True

        if redirect_to_canonical_url:
            url = Video.get_canonical_url(readable_id, topic, query_string)

            logging.info("Redirecting to %s" % url)
            handler.redirect(url, True)
            return None

        # Note: Bingo conversions are tracked on the client now,
        # so they have been removed here. (tomyedwab)

        topic_data = topic.get_play_data()

        discussion_options = qa.add_template_values({}, handler.request)
        video_data = Video.get_play_data(readable_id, topic,
                                         discussion_options)
        if video_data is None:
            raise MissingVideoException("Missing video '%s'" % readable_id)

        template_values = {
            "topic_data": topic_data,
            "topic_data_json": api.jsonify.jsonify(topic_data),
            "video": video_data,
            "video_data_json": api.jsonify.jsonify(video_data),
            "selected_nav_link": 'watch',
        }

        return template_values

    @user_util.open_access
    @ensure_xsrf_cookie
    def get(self, path, video_id):
        if path:
            path_list = path.split('/')

            if len(path_list) > 0:
                topic_id = path_list[-1]
                template_values = ViewVideo.show_video(
                    self, video_id, topic_id)
                if template_values:
                    self.render_jinja2_template(
                        'viewvideo.html', template_values)


class ViewVideoDeprecated(request_handler.RequestHandler):
    # The handler itself is deprecated. The ViewVideo handler is the canonical
    # handler now.
    @user_util.open_access
    @ensure_xsrf_cookie
    def get(self, readable_id=""):
        # This method displays a video in the context of a particular topic.
        # To do that we first need to find the appropriate topic.  If we aren't
        # given the topic title in a query param, we need to find a topic that
        # the video is a part of.  That requires finding the video, given it
        # readable_id or, to support old URLs, it's youtube_id.
        video = None
        video_id = self.request.get('v')
        topic_id = self.request_string('topic', default="")
        readable_id = urllib.unquote(readable_id)

        # remove any trailing dashes (see issue 1140)
        readable_id = re.sub('-+$', '', readable_id)

        # If either the readable_id or topic title is missing,
        # redirect to the canonical URL that contains them
        if video_id:  # Support for old links
            query = Video.all()
            query.filter('youtube_id =', video_id)
            video = query.get()

            if not video:
                raise MissingVideoException(
                    "Missing video w/ youtube id '%s'" % video_id)

            readable_id = video.readable_id
            topic = video.first_topic()

            if not topic:
                raise MissingVideoException(
                    "No topic has video w/ youtube id '%s'" % video_id)

        ViewVideo.show_video(self, readable_id, topic_id, True)

from datetime import *
class GMT1(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=1) + self.dst(dt)
    def dst(self, dt):
        # DST starts last Sunday in March
        d = datetime(dt.year, 4, 1)   # ends last Sunday in October
        self.dston = d - timedelta(days=d.weekday() + 1)
        d = datetime(dt.year, 11, 1)
        self.dstoff = d - timedelta(days=d.weekday() + 1)
        if self.dston <=  dt.replace(tzinfo=None) < self.dstoff:
            return timedelta(hours=1)
        else:
            return timedelta(0)
    def tzname(self,dt):
         return "GMT +1"

class ReportIssue(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        issue_type = self.request.get('type')
        self.write_response(issue_type, {
            'issue_labels': self.request.get('issue_labels'),
        })
    @user_util.open_access
    def post(self):
        issue_type = self.request.get('type')

        title = self.request_string("title", default="")
        page = self.request_string("page", default="")
        ureport = self.request_string("ureport", default="")
        ucontact = self.request_string("ucontact", default="")
        utype = self.request_string("utype", default="")

        from third_party import gspread
        from secrets import *
        gc = gspread.login(google_docs_user, google_docs_pw)
        sh = gc.open_by_key(google_docs_spreadsheet_problems)
        wks = sh.get_worksheet(0)
        cell_list = wks.col_values(1)
        row = len(cell_list) + 1
        currdate = datetime.now(GMT1()).strftime("%d %b %Y %I:%M:%S %p")
        wks.update_acell('A'+str(row), currdate)
        wks.update_acell('B'+str(row), page)
        wks.update_acell('C'+str(row), utype)
        wks.update_acell('D'+str(row), title)
        wks.update_acell('E'+str(row), ureport)
        wks.update_acell('F'+str(row), ucontact)
        template_values = {
            'currdate': currdate,
            'title': title,
            'description': ureport,
            'email': ucontact,
            }
        self.render_jinja2_template('reportissue_resume.html', template_values)


    def write_response(self, issue_type, extra_template_values):
        user_agent = self.request.headers.get('User-Agent')
        if user_agent is None:
            user_agent = ''

        # Commas delimit labels, so we don't want them
        user_agent = user_agent.replace(',', ';')

        template_values = {
            'referer': self.request.headers.get('Referer'),
            'user_agent': user_agent,
            }
        template_values.update(extra_template_values)
        page = 'reportissue_template.html'
        if issue_type == 'Defect':
            page = 'reportproblem.html'
        elif issue_type == 'Enhancement':
            page = 'makesuggestion.html'
        elif issue_type == 'New-Video':
            page = 'requestvideo.html'
        elif issue_type == 'Comment':
            page = 'makecomment.html'
        elif issue_type == 'Question':
            page = 'askquestion.html'

        self.render_jinja2_template(page, template_values)


class Crash(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        if self.request_bool("capability_disabled", default=False):
            raise CapabilityDisabledError("Simulate scheduled GAE downtime")
        else:
            # Even Watson isn't perfect
            raise Exception("What is Toronto?")


class SendToLog(request_handler.RequestHandler):
    @user_util.open_access
    def post(self):
        message = self.request_string("message", default="")
        if message:
            logging.critical("Manually sent to log: %s" % message)


class Sleep(request_handler.RequestHandler):
    """Sleeps for a while.  Used to busy an instance when deploying."""
    @user_util.open_access
    def get(self):
        # A simple check to prevent DoS attacks from the outside world.
        if self.request.get('key') != App.sleep_secret:
            self.redirect("/")
            return
        time.sleep(28)    # just short of the request-timeout limit of 30
        self.response.out.write('What a nice nap!  Now I feel all refreshed.')


class ViewContribute(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('contribute.html', {
            "selected_nav_link": "contribute"
        })


class ViewCredits(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('viewcredits.html', {
            "selected_nav_link": "contribute"
        })


class Donate(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('donate.html', {
            "selected_nav_link": "donate"
        })


class ViewTOS(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('tos.html', {
            "selected_nav_link": "tos"
        })


class ViewAPITOS(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('api-tos.html', {
            "selected_nav_link": "api-tos"
        })


class ViewPrivacyPolicy(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('privacy-policy.html', {
            "selected_nav_link": "privacy-policy"
        })


class ViewDMCA(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('dmca.html', {
            "selected_nav_link": "dmca"
        })


class ViewStyleGuide(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        self.render_jinja2_template('styleguide.html', {
            "selected_nav_link": "styleguide"
        })


class RetargetFeedback(bulk_update.handler.UpdateKind):
    def get_keys_query(self, kind):
        """Returns a keys-only query to get the keys of the entities to
        update.
        """
        return db.GqlQuery('select __key__ from Feedback')

    def use_transaction(self):
        return False

    def update(self, feedback):
        orig_video = feedback.video()

        if orig_video == None or type(orig_video).__name__ != "Video":
            return False
        readable_id = orig_video.readable_id
        query = Video.all()
        query.filter('readable_id =', readable_id)
        # The database currently contains multiple Video objects for a
        # particular video.  Some are old.  Some are due to a YouTube sync
        # where the youtube urls changed and our code was producing youtube_ids
        # that ended with '_player'.  This hack gets the most recent valid
        # Video object.
        key_id = 0
        for v in query:
            if v.key().id() > key_id and not v.youtube_id.endswith('_player'):
                video = v
                key_id = v.key().id()
        # End of hack
        if video is not None and video.key() != orig_video.key():
            logging.info("Retargeting Feedback %s from Video %s to Video %s",
                         feedback.key().id(),
                         orig_video.key().id(),
                         video.key().id())
            feedback.targets[0] = video.key()
            return True
        else:
            return False


class Search(request_handler.RequestHandler):
    # Reject any search queries shorter than this
    MIN_QUERY_LENGTH = 4

    # Characters that Solr doesn't like: " \ ! ^ [ ] { } ( ) :
    SEARCH_FILTER_RE = re.compile("[%s]" % re.escape(r'"\!^[]{}():'))

    @user_util.open_access
    def get(self):
        if not gandalf("new_faster_search"):
            self.get_old()
            return

        query = self.request.get('page_search_query')
        # Remove any characters that Solr doesn't understand or interfere with
        # the query language syntax, so we don't get errors returned.
        query = self.SEARCH_FILTER_RE.sub(" ", query).strip().lower()
        template_values = {'page_search_query': query}
        if len(query) < self.MIN_QUERY_LENGTH:
            if len(query) > 0:
                template_values.update({
                    'query_too_short': self.MIN_QUERY_LENGTH
                })
            self.render_jinja2_template(
                "searchresults_new.html", template_values)
            return

        url = ("http://search-rpc.khanacademy.org/solr/select/?q=%s&start=0&"
               "rows=1000&indent=on&wt=json&fl=*%%20score&defType=edismax&"
               "qf=title^10.0+keywords^2.0+description^6.0+subtitles" %
               urllib.quote(query.encode('utf-8')))
        try:
            logging.info("Fetching: %s" % url)
            # Allow responses to be cached for an hour
            response = urlfetch.fetch(url=url, deadline=25, headers={
                'Cache-Control': 'max-age=3600'
            })
            response_object = json.loads(response.content)
        except Exception, e:
            logging.error("Failed to fetch search results from search-rpc! "
                          "Error: %s" % str(e))
            template_values.update({
                'server_timout': True
            })
            self.render_jinja2_template(
                "searchresults_new.html", template_values)
            return

        logging.info("Received response: %d" %
                     response_object["response"]["numFound"])

        matching_topics = [t for t in response_object["response"]["docs"]
                           if t["kind"] == "Topic"]
        if matching_topics:
            matching_topic_count = 1
            matching_topic = matching_topics[0] if matching_topics else None
            matching_topic["children"] = (
                json.loads(matching_topic["child_topics"])
                if "child_topics" in matching_topic
                else None)
        else:
            matching_topic_count = 0
            matching_topic = None

        videos = [v for v in response_object["response"]["docs"]
                  if v["kind"] == "Video" and v["score"] >= 1.0]
        topics = {}

        for video in videos:
            video["related_exercises"] = json.loads(video["related_exercises"])

            parent_topic = json.loads(video["parent_topic"])
            topic_id = parent_topic["id"]
            if topic_id not in topics:
                topics[topic_id] = parent_topic
                topics[topic_id]["videos"] = []
                topics[topic_id]["match_count"] = 0
                topics[topic_id]["max_score"] = 0

            topics[topic_id]["videos"].append(video)
            topics[topic_id]["match_count"] += 1
            topics[topic_id]["max_score"] = max(
                topics[topic_id]["max_score"], float(video["score"]))

        topics_list = sorted(
            topics.values(), key=lambda topic: -topic["max_score"])

        template_values.update({
                           'topics': topics_list,
                           'matching_topic': matching_topic,
                           'videos': videos,
                           'search_string': query,
                           'video_count': len(videos),
                           'topic_count': len(topics_list),
                           'matching_topic_count': matching_topic_count
                           })

        self.render_jinja2_template("searchresults_new.html", template_values)

    @user_util.admin_required
    def update(self):
        if App.is_dev_server:
            new_version = topic_models.TopicVersion.get_default_version()
            old_version_number = layer_cache.KeyValueCache.get(
                "last_dev_topic_vesion_indexed")

            # no need to update if current version matches old version
            if new_version.number == old_version_number:
                return False

            if old_version_number:
                old_version = topic_models.TopicVersion.get_by_id(
                                                            old_version_number)
            else:
                old_version = None

            topic_models.rebuild_search_index(new_version, old_version)

            layer_cache.KeyValueCache.set("last_dev_topic_vesion_indexed",
                                          new_version.number)

    def get_old(self):
        """ Deprecated old version of search, so we can Gandalf in the new one.

        If new search is working, this should be taken out by May 31, 2012.
        """

        show_update = False
        if App.is_dev_server and user_util.is_current_user_admin():
            update = self.request_bool("update", False)
            if update:
                self.update()

            version_number = layer_cache.KeyValueCache.get(
                "last_dev_topic_vesion_indexed")
            default_version = topic_models.TopicVersion.get_default_version()
            if version_number != default_version.number:
                show_update = True

        query = self.request.get('page_search_query')
        template_values = {'page_search_query': query}
        query = query.strip()
        if len(query) < search.SEARCH_PHRASE_MIN_LENGTH:
            if len(query) > 0:
                template_values.update({
                    'query_too_short': search.SEARCH_PHRASE_MIN_LENGTH
                })
            self.render_jinja2_template("searchresults.html", template_values)
            return
        searched_phrases = []

        # Do an async query for all ExerciseVideos, since this may be slow
        exvids_query = ExerciseVideo.all()
        exvids_future = util.async_queries([exvids_query])

        # One full (non-partial) search, then sort by kind
        all_text_keys = Topic.full_text_search(
                query, limit=50, kind=None,
                stemming=Topic.INDEX_STEMMING,
                multi_word_literal=Topic.INDEX_MULTI_WORD,
                searched_phrases_out=searched_phrases)

        # Quick title-only partial search
        topic_partial_results = filter(
                lambda topic_dict: query in topic_dict["title"].lower(),
                autocomplete.topic_title_dicts())
        video_partial_results = filter(
                lambda video_dict: query in video_dict["title"].lower(),
                autocomplete.video_title_dicts())
        url_partial_results = filter(
                lambda url_dict: query in url_dict["title"].lower(),
                autocomplete.url_title_dicts())

        # Combine results & do one big get!
        all_keys = [str(key_and_title[0]) for key_and_title in all_text_keys]
        all_keys.extend([result["key"] for result in topic_partial_results])
        all_keys.extend([result["key"] for result in video_partial_results])
        all_keys.extend([result["key"] for result in url_partial_results])
        all_keys = list(set(all_keys))

        # Filter out anything that isn't a Topic, Url or Video
        all_keys = [key for key in all_keys
                    if db.Key(key).kind() in ["Topic", "Url", "Video"]]

        # Get all the entities
        all_entities = db.get(all_keys)

        # Group results by type
        topics = []
        videos = []
        for entity in all_entities:
            if isinstance(entity, Topic):
                topics.append(entity)
            elif isinstance(entity, Video):
                videos.append(entity)
            elif isinstance(entity, Url):
                videos.append(entity)
            elif entity:
                logging.info("Found unknown object " + repr(entity))

        # Get topics for videos not in matching topics
        filtered_videos = []
        filtered_videos_by_key = {}
        for video in videos:
            if [(str(topic.key()) in video.topic_string_keys)
                for topic in topics].count(True) == 0:
                video_topic = video.first_topic()
                if video_topic != None:
                    topics.append(video_topic)
                    filtered_videos.append(video)
                    filtered_videos_by_key[str(video.key())] = []
            else:
                filtered_videos.append(video)
                filtered_videos_by_key[str(video.key())] = []
        video_count = len(filtered_videos)

        # Get the related exercises
        all_exercise_videos = exvids_future[0].get_result()
        exercise_keys = []
        for exvid in all_exercise_videos:
            video_key = str(ExerciseVideo.video.get_value_for_datastore(exvid))
            if video_key in filtered_videos_by_key:
                exercise_key = ExerciseVideo.exercise.get_value_for_datastore(
                    exvid)
                video_exercise_keys = filtered_videos_by_key[video_key]
                video_exercise_keys.append(exercise_key)
                exercise_keys.append(exercise_key)
        exercises = db.get(exercise_keys)

        # Sort exercises with videos
        video_exercises = {}
        for video_key, exercise_keys in filtered_videos_by_key.iteritems():
            video_exercises[video_key] = map(
                lambda exkey: [exercise for exercise in exercises
                               if exercise.key() == exkey][0], exercise_keys)

        # Count number of videos in each topic and sort descending
        topic_count = 0
        matching_topic_count = 0
        if topics:
            if len(filtered_videos) > 0:
                for topic in topics:
                    topic.match_count = [
                        (str(topic.key()) in video.topic_string_keys)
                        for video in filtered_videos].count(True)
                    if topic.match_count > 0:
                        topic_count += 1

                topics = sorted(topics,
                                key=lambda topic: topic.match_count,
                                reverse=True)
            else:
                for topic in topics:
                    topic.match_count = 0

            for topic in topics:
                if topic.title.lower() == query:
                    topic.matches = True
                    matching_topic_count += 1

                    child_topics = topic.get_child_topics(
                        include_descendants=True)
                    topic.child_topics = [t for t in child_topics
                                          if t.has_content()]

        template_values.update({
                           'show_update': show_update,
                           'topics': topics,
                           'videos': filtered_videos,
                           'video_exercises': video_exercises,
                           'search_string': query,
                           'video_count': video_count,
                           'topic_count': topic_count,
                           'matching_topic_count': matching_topic_count
                           })

        self.render_jinja2_template("searchresults.html", template_values)


class PermanentRedirectToHome(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):

        redirect_target = "/"
        relative_path = self.request.path.rpartition('/')[2].lower()

        # Permanently redirect old JSP version of the site to home
        # or, in the case of some special targets, to their appropriate new URL
        dict_redirects = {
            "sat.jsp": "/sat",
            "gmat.jsp": "/gmat",
        }

        if relative_path in dict_redirects:
            redirect_target = dict_redirects[relative_path]

        self.redirect(redirect_target, True)


class ServeUserVideoCss(request_handler.RequestHandler):
    @user_util.login_required
    def get(self):
        user_data = UserData.current()
        user_video_css = video_models.UserVideoCss.get_for_user_data(user_data)
        self.response.headers['Content-Type'] = 'text/css'

        if user_video_css.version == user_data.uservideocss_version:
            # Don't cache if there's a version mismatch and the update isn't
            # finished
            self.response.headers['Cache-Control'] = 'public,max-age=1000000'

        self.response.out.write(user_video_css.video_css)

#KhanNL
class Nuke(request_handler.RequestHandler):
    @user_util.developer_required
    def get(self):
        return
        db.delete(Video.all(keys_only=True))

#KhanNL
@layer_cache.cache_with_key_fxn(lambda exercise_file: "exercise_raw_html_%s" % exercise_file, layer=layer_cache.Layers.InAppMemory)
def raw_exercise_contents(exercise_file):
    path = os.path.join(os.path.dirname(__file__), "khan-exercises/exercises/%s" % exercise_file)

    f = None
    contents = ""

    try:
        f = open(path)
        contents = f.read()
    except:
        raise MissingExerciseException(
                "Missing exercise file for exid '%s'" % exercise_file)
    finally:
        if f:
            f.close()

    if not len(contents):
        raise MissingExerciseException(
                "Missing exercise content for exid '%s'" % exercise_file)

    return contents

#KhanNL
class TranslateFile(request_handler.RequestHandler):
    @user_util.open_access
    def get(self, path):
        path = self.request.path
        exercise_file = urllib.unquote(path.rpartition('/')[2])
        self.response.headers["Content-Type"] = "text/html"
        self.response.out.write(raw_exercise_contents(exercise_file))

class MemcacheViewer(request_handler.RequestHandler):
    @user_util.developer_required
    def get(self):
        key = self.request_string(
            "key", "__layer_cache_models._get_settings_dict__")
        namespace = self.request_string("namespace", App.version)
        values = memcache.get(key, namespace=namespace)
        self.response.out.write("Memcache key %s = %s.<br>\n" % (key, values))
        if type(values) is dict:
            for k, value in values.iteritems():
                self.response.out.write(
                    "<p><b>%s</b>%s</p>" % (k, dict((key, getattr(value, key))
                                                    for key in dir(value))))
        if self.request_bool("clear", False):
            memcache.delete(key, namespace=namespace)


application = webapp2.WSGIApplication([
    DomainRoute('smarthistory.khanacademy.org', [
        webapp2.SimpleRoute('/.*', smarthistory.SmartHistoryProxy)
    ]),
    ('/', homepage.ViewHomePage),
    ('/missingvideos', helpus.ViewMissingVideos),
    ('/about', util_about.ViewAbout),
    ('/about/blog', blog.ViewBlog),
    RedirectRoute('/about/blog/schools',
        redirect_to='http://ka-implementations.tumblr.com/',
        defaults={'_permanent': False}),
    ('/about/blog/.*', blog.ViewBlogPost),
    ('/about/start', util_about.ViewStart),
    RedirectRoute('/about/getting-started',
                  redirect_to='http://khanacademy.desk.com/customer/portal/articles/329323-where-do-i-begin-how-should-i-get-started-'),
    ('/about/contact', util_about.ViewContact),
    ('/about/tos', ViewTOS),
    ('/about/api-tos', ViewAPITOS),
    ('/about/privacy-policy', ViewPrivacyPolicy),
    ('/about/dmca', ViewDMCA),
    ('/contribute', ViewContribute),
    RedirectRoute('/getinvolved', redirect_to='/contribute'),
    ('/contribute/credits', ViewCredits),
    ('/about/faq', util_about.ViewFAQ),
    RedirectRoute('/frequently-asked-questions', redirect_to='/about/faq'),
    ('/exercisedashboard', knowledgemap.handlers.ViewKnowledgeMap),
    ('/style', ViewStyleGuide),

    ('/stories/submit', stories.handlers.SubmitStory),
    ('/stories/?.*', stories.handlers.ViewStories),

    # Labs
    ('/labs', labs.labs_request_handler.LabsRequestHandler),

    ('/labs/explorations', labs.explorations.RequestHandler),
    ('/labs/explorations/([^/]+)', labs.explorations.RequestHandler),
    ('/labs/socrates', socrates.handlers.SocratesIndexHandler),
    ('/labs/socrates/(.*)/v/([^/]*)', socrates.handlers.SocratesHandler),

    ('/(.*)/e', exercises.handlers.ViewExercise),
    ('/(.*)/e/([^/]*)', exercises.handlers.ViewExercise),

    # /exercise/addition_1
    ('/exercise/(.+)', exercises.handlers.ViewExerciseDeprecated),
    # /topicexercise/addition_and_subtraction
    ('/topicexercise/(.+)', exercises.handlers.ViewTopicExerciseDeprecated),
    # /exercises?exid=addition_1
    ('/exercises', exercises.handlers.ViewExerciseDeprecated),

    ('/(review)', exercises.handlers.ViewExercise),
    #KhanNL
    ('/khan-exercises/exercises/(.*).js', TranslateFile),
    ('/khan-exercises/exercises/.*', exercises.handler_raw.RawExercise),
    ('/viewexercisesonmap', knowledgemap.handlers.ViewKnowledgeMap),
    ('/video/(.*)', ViewVideoDeprecated),  # Backwards URL compatibility
    ('/v/(.*)', ViewVideoDeprecated),  # Backwards URL compatibility
    ('/video', ViewVideoDeprecated),  # Backwards URL compatibility
    ('/(.*)/v/([^/]*)', ViewVideo),
    ('/reportissue', ReportIssue),
    ('/search', Search),
    ('/savemapcoords', knowledgemap.handlers.SaveMapCoords),
    ('/crash', Crash),

    ('/image_cache/(.+)', ImageCache),

    ('/library_content', GenerateLibraryContent),
    ('/admin/import_smarthistory', topics.ImportSmartHistory),
    ('/admin/reput', bulk_update.handler.UpdateKind),
    ('/admin/retargetfeedback', RetargetFeedback),
    ('/admin/updateblogentries', rssblog.UpdateBlogEntries),
    ('/admin/startnewbadgemapreduce', badges.handlers.StartNewBadgeMapReduce),
    ('/admin/badgestatistics', badges.handlers.BadgeStatistics),
    ('/admin/startnewexercisestatisticsmapreduce',
     exercise_statistics.StartNewExerciseStatisticsMapReduce),
    ('/admin/startnewvotemapreduce', voting.StartNewVoteMapReduce),
    ('/admin/dailyactivitylog',
     activity_summary.StartNewDailyActivityLogMapReduce),
 #   ('/admin/youtubesync.*', youtube_sync.YouTubeSync),
    ('/admin/unisubs', unisubs.handlers.ReportHandler),
    ('/admin/unisubs/import', unisubs.handlers.ImportHandler),

    ('/devadmin', devpanel.handlers.Panel),
    ('/devadmin/maplayout', kmap_editor.MapLayoutEditor),
    ('/devadmin/coaches_list', devpanel.handlers.CoachesList),
    ('/devadmin/emailchange', devpanel.handlers.MergeUsers),
    ('/devadmin/deleteaccount', devpanel.handlers.DeleteAccount),
    ('/devadmin/managedevs', devpanel.handlers.Manage),
    ('/devadmin/managecoworkers', devpanel.handlers.ManageCoworkers),
    ('/devadmin/managecommoncore', devpanel.handlers.ManageCommonCore),
    ('/commoncore', common_core.handlers.CommonCore),
    ('/staging/commoncore', common_core.handlers.CommonCore),
    ('/devadmin/content', topics.EditContent),
    ('/devadmin/memcacheviewer', MemcacheViewer),
    ('/devadmin/nukevideo', Nuke),

    # Manually refresh the content caches
    ('/devadmin/refresh', topics.RefreshCaches),

    ('/coach/resources', util_coach.ViewCoachResources),
    ('/coach/demo', util_coach.ViewDemo),
    ('/coach/accessdemo', util_coach.AccessDemo),
    ('/coach/schools-blog', schools_blog.ViewBlog),
    ('/toolkit', util_coach.ViewToolkit),
    ('/toolkit/(.*)', util_coach.ViewToolkit),
    ('/coaches', coaches.ViewCoaches),
    ('/students', coaches.ViewStudents),
    ('/unregisterstudent', coaches.UnregisterStudent),
    ('/requeststudent', coaches.RequestStudent),
    ('/acceptcoach', coaches.AcceptCoach),

    ('/removestudentfromlist', coaches.RemoveStudentFromList),
    ('/addstudenttolist', coaches.AddStudentToList),

    ('/mailing-lists/subscribe', util_mailing_lists.Subscribe),

    ('/profile/graph/activity', profiles.handlers.ActivityGraph),
    ('/profile/graph/focus', profiles.handlers.FocusGraph),
    ('/profile/graph/exercisesovertime',
     profiles.handlers.ExercisesOverTimeGraph),
    ('/profile/graph/exerciseproblems',
     profiles.handlers.ExerciseProblemsGraph),

    ('/profile/graph/classexercisesovertime',
     profiles.handlers.ClassExercisesOverTimeGraph),
    ('/profile/graph/classenergypointsperminute',
     profiles.handlers.ClassEnergyPointsPerMinuteGraph),
    ('/profile/graph/classtime', profiles.handlers.ClassTimeGraph),
    ('/profile/(.+?)/(.*)', profiles.handlers.ViewProfile),
    ('/profile/(.*)', profiles.handlers.ViewProfile),
    ('/profile', profiles.handlers.ViewProfile),
    ('/class_profile', profiles.handlers.ViewClassProfile),
    ('/class_profile/(.*)', profiles.handlers.ViewClassProfile),

    ('/login', login.Login),
    ('/login/mobileoauth', login.MobileOAuthLogin),
    ('/postlogin', login.PostLogin),
    ('/logout', login.Logout),
    ('/signup', login.Signup),
    ('/completesignup', login.CompleteSignup),
    ('/parentsignup', login.ParentSignup),

    ('/createchild', login.CreateChild),
    ('/pwchange', login.PasswordChange),
    ('/forgotpw', login.ForgotPassword),  # Start of pw-recovery flow
    ('/pwreset', login.PasswordReset),  # For after user clicks on email link

    ('/api-apps/register', oauth_apps.Register),

    # Below are all discussion related pages
    ('/discussion/addcomment', comments.AddComment),
    ('/discussion/pagecomments', comments.PageComments),

    ('/discussion/expandquestion', discussion.handlers.ExpandQuestion),
    ('/discussion/flagentity', discussion.handlers.FlagEntity),
    ('/discussion/voteentity', voting.VoteEntity),
    ('/discussion/updateqasort', voting.UpdateQASort),
    ('/admin/discussion/finishvoteentity', voting.FinishVoteEntity),

    ('/discussion/mod', discussion.handlers.ModPanel),
    ('/discussion/mod/flaggedfeedback', discussion.handlers.FlaggedFeedback),
    ('/discussion/mod/moderatorlist', discussion.handlers.ModeratorList),
    ('/discussion/mod/bannedlist', discussion.handlers.BannedList),
    RedirectRoute('/discussion/moderatorlist', redirect_to='/discussion/mod'),
    RedirectRoute('/discussion/flaggedfeedback',
                  redirect_to='/discussion/mod'),

    ('/githubpost', github.NewPost),

    ('/paypal/autoreturn', paypal.handlers.AutoReturn),
    ('/paypal/ipn', paypal.handlers.IPN),

    ('/badges/custom/create', badges.custom_badge_handlers.CreateCustomBadge),
    ('/badges/custom/award', badges.custom_badge_handlers.AwardCustomBadge),
    ('/badges/(.*)', badges.handlers.ViewBadge),
    ('/badges', badges.handlers.ViewBadge),

    ('/notifierclose', phantom_users.handlers.ToggleNotify),
    ('/newaccount', Clone),

    ('/dashboard', dashboard.handlers.Dashboard),
    ('/admin/dashboard/record_statistics',
     dashboard.handlers.RecordStatistics),
    ('/admin/entitycounts', dashboard.handlers.EntityCounts),
    ('/devadmin/contentcounts', dashboard.handlers.ContentCountsCSV),

    ('/sendtolog', SendToLog),
    ('/sleep', Sleep),

    ('/user_video_css', ServeUserVideoCss),

    ('/admin/exercisestats/collectfancyexercisestatistics',
     exercisestats.exercisestats_util.CollectFancyExerciseStatistics),
    ('/exercisestats/report', exercisestats.report.Test),
    ('/exercisestats/exerciseovertime',
     exercisestats.report_json.ExerciseOverTimeGraph),
    ('/exercisestats/geckoboardexerciseredirect',
     exercisestats.report_json.GeckoboardExerciseRedirect),
    ('/exercisestats/exercisestatsmap',
     exercisestats.report_json.ExerciseStatsMapGraph),
    ('/exercisestats/exerciseslastauthorcounter',
     exercisestats.report_json.ExercisesLastAuthorCounter),
    ('/exercisestats/exercisenumbertrivia',
     exercisestats.report_json.ExerciseNumberTrivia),
    ('/exercisestats/userlocationsmap',
     exercisestats.report_json.UserLocationsMap),
    ('/exercisestats/exercisescreatedhistogram',
     exercisestats.report_json.ExercisesCreatedHistogram),

    ('/goals/new', goals.handlers.CreateNewGoal),
    ('/goals/admincreaterandom', goals.handlers.CreateRandomGoalData),

    # Summer Discovery Camp application/registration
    ('/summer/application', summer.handlers.Application),
    ('/summer/tuition', summer.handlers.Tuition),
    ('/summer/application-status', summer.handlers.Status),
    ('/summer/getstudent', summer.handlers.GetStudent),
    ('/summer/paypal-autoreturn', summer.handlers.PaypalAutoReturn),
    ('/summer/paypal-ipn', summer.handlers.PaypalIPN),
    ('/summer/admin/download', summer.handlers.Download),
    ('/summer/admin/updatestudentstatus', summer.handlers.UpdateStudentStatus),

    # Computer Science Curriculum
    webapp2.Route('/explore', scratchpads.handlers.ScratchpadHandler,
        handler_method='index_official'),
    webapp2.Route('/explore/new', scratchpads.handlers.ScratchpadHandler,
        handler_method='new'),
    webapp2.Route('/explore/tutorials', scratchpads.handlers.ScratchpadHandler,
        handler_method='index_tutorials'),
    webapp2.Route('/explore/<slug>/<scratchpad_id:\d+>',
        scratchpads.handlers.ScratchpadHandler, handler_method='show'),
    webapp2.Route('/explore/<slug>/<scratchpad_id:\d+>/image.png',
        scratchpads.handlers.ScratchpadHandler, handler_method='image'),
    ('/explore/soundcloud-callback',
        scratchpads.handlers.SoundcloudCallbackRequestHandler),

    # Stats about appengine
    ('/stats/dashboard', dashboard.handlers.Dashboard),
    ('/stats/memcache', appengine_stats.MemcacheStatus),

    ('/robots.txt', robots.RobotsTxt),

    # Hard-coded redirects
    RedirectRoute('/shop',
            redirect_to='http://khanacademy.myshopify.com',
            defaults={'_permanent': False}),
    RedirectRoute('/jobs<:/?.*>',
            redirect_to='http://hire.jobvite.com/CompanyJobs/Careers.aspx?k=JobListing&c=qd69Vfw7',
            defaults={'_permanent': False}),
    RedirectRoute('/jobs/<:.*>',
            redirect_to='http://hire.jobvite.com/CompanyJobs/Careers.aspx?k=JobListing&c=qd69Vfw7',
            defaults={'_permanent': False}),

    # Dynamic redirects are prefixed w/ "/r/" and managed by "/redirects"
    ('/r/.*', redirects.handlers.Redirect),
    ('/redirects', redirects.handlers.List),
    ('/redirects/add', redirects.handlers.Add),
    ('/redirects/remove', redirects.handlers.Remove),

    ('/importer', ImportHandler),

    # Redirect any links to old JSP version
    ('/.*\.jsp', PermanentRedirectToHome),
    ('/index\.html', PermanentRedirectToHome),

    ('/_ah/warmup.*', warmup.Warmup),

    # Topic paths can be anything, so we match everything.
    # The TopicPage handler will throw a 404 if no page is found.
    # (For more information see TopicPage handler above)
    ('/(.*)', TopicPage),

    ], debug=True)

application = profiler.ProfilerWSGIMiddleware(application)
application = GAEBingoWSGIMiddleware(application)
application = request_cache.RequestCacheMiddleware(application)
application = wsgi_compat.WSGICompatHeaderMiddleware(application)


def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
