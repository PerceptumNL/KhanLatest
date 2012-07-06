import cgi
import datetime
import logging
import re
from urlparse import urlparse

import third_party.gdata.youtube.service

from google.appengine.api import taskqueue
from google.appengine.api import users
from google.appengine.ext import db

from setting_model import Setting
from video_models import Video
from topic_models import Topic
import request_handler
import user_util

def youtube_get_video_data_dict(youtube_id):
    yt_service = third_party.gdata.youtube.service.YouTubeService()

    # Now that we run these queries from the App Engine servers, we need to 
    # explicitly specify our developer_key to avoid being lumped together w/ rest of GAE and
    # throttled by YouTube's "Too many request" quota
    yt_service.developer_key = "AI39si6ctKTnSR_Vx7o7GpkpeSZAKa6xjbZz6WySzTvKVYRDAO7NHBVwofphk82oP-OSUwIZd0pOJyNuWK8bbOlqzJc9OFozrQ"
    yt_service.client_id = "n/a"

    logging.info("trying to get info for youtube_id: %s" % youtube_id)
    try:
        video = yt_service.GetYouTubeVideoEntry(video_id=youtube_id)
    except:
        video = None
    if video:
        video_data = {"youtube_id" : youtube_id,
                      "title" : video.media.title.text.decode('utf-8'),
                      "url" : video.media.player.url.decode('utf-8'),
                      "duration" : int(video.media.duration.seconds)}

        if video.statistics:
            video_data["views"] = int(video.statistics.view_count)

        video_data["description"] = (video.media.description.text or '').decode('utf-8')
        video_data["keywords"] = (video.media.keywords.text or '').decode('utf-8')

        potential_id = re.sub('[^a-z0-9]', '-', video_data["title"].lower());
        potential_id = re.sub('-+$', '', potential_id)  # remove any trailing dashes (see issue 1140)
        potential_id = re.sub('^-+', '', potential_id)  # remove any leading dashes (see issue 1526)                        

        number_to_add = 0
        current_id = potential_id
        while True:
            query = Video.all()
            query.filter('readable_id=', current_id)
            if (query.get() is None): #id is unique so use it and break out
                video_data["readable_id"] = current_id
                break
            else: # id is not unique so will have to go through loop again
                number_to_add+=1
                current_id = potential_id+'-'+number_to_add                       

        return video_data

    return None


def youtube_get_video_data(video):
    data_dict = youtube_get_video_data_dict(video.youtube_id)

    if data_dict is None:
        return None

    for prop, value in data_dict.iteritems():
        setattr(video, prop, value)

    return video

class YouTubeSyncStep:
    START = 0
    UPDATE_VIDEO_STATS = 1

class YouTubeSyncStepLog(db.Model):
    step = db.IntegerProperty()
    generation = db.IntegerProperty()
    dt = db.DateTimeProperty(auto_now_add = True)

class YouTubeSync(request_handler.RequestHandler):

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def get(self):

        if self.request_bool("start", default = False):
            self.task_step(0)
            self.response.out.write("Sync started")
        else:
            latest_logs_query = YouTubeSyncStepLog.all()
            latest_logs_query.order("-dt")
            latest_logs = latest_logs_query.fetch(10)

            self.response.out.write("Latest sync logs:<br/><br/>")
            for sync_log in latest_logs:
                self.response.out.write("Step: %s, Generation: %s, Date: %s<br/>" % (sync_log.step, sync_log.generation, sync_log.dt))
            self.response.out.write("<br/><a href='/admin/youtubesync?start=1'>Start New Sync</a>")

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def post(self):
        # Protected for admins only by app.yaml so taskqueue can hit this URL
        step = self.request_int("step", default = 0)

        if step == YouTubeSyncStep.START:
            self.startYouTubeSync()
        elif step == YouTubeSyncStep.UPDATE_VIDEO_STATS:
            self.updateVideoStats()

        log = YouTubeSyncStepLog()
        log.step = step
        log.generation = int(Setting.last_youtube_sync_generation_start())
        log.put()

        # check to see if we have more steps to go
        if step < YouTubeSyncStep.UPDATE_VIDEO_STATS:
            self.task_step(step + 1)

    def task_step(self, step):
        taskqueue.add(url='/admin/youtubesync/%s' % step, queue_name='youtube-sync-queue', params={'step': step})

    def startYouTubeSync(self):
        Setting.last_youtube_sync_generation_start(int(Setting.last_youtube_sync_generation_start()) + 1)

    def updateVideoStats(self):
        yt_service = third_party.gdata.youtube.service.YouTubeService()
        # Now that we run these queries from the App Engine servers, we need to 
        # explicitly specify our developer_key to avoid being lumped together w/ rest of GAE and
        # throttled by YouTube's "Too many request" quota
        yt_service.developer_key = "AI39si6ctKTnSR_Vx7o7GpkpeSZAKa6xjbZz6WySzTvKVYRDAO7NHBVwofphk82oP-OSUwIZd0pOJyNuWK8bbOlqzJc9OFozrQ"
        yt_service.client_id = "n/a"

        videos_to_put = set()

        # doing fetch now otherwise query timesout later while doing youtube requests
        # theoretically we can also change this code to use Mapper class:
        # http://code.google.com/appengine/articles/deferred.html
        for i, video in enumerate(Video.all().fetch(100000)):
            entry = None
            youtube_id = video.youtube_id

            # truncating youtubeid at 11 to handle _DUP_X's
            # handling the _DUPs to make it easier to detect content problems when duration = 0
            if re.search("_DUP_\d*$", youtube_id):
                youtube_id = youtube_id[0:11]

            try:
                entry = yt_service.GetYouTubeVideoEntry(video_id=youtube_id)

            except Exception, e:
                logging.info("Error trying to get %s: %s" % 
                            (youtube_id, e))
            
            if entry:
                count = int(entry.statistics.view_count)
                if count != video.views:
                    logging.info("%i: Updating %s from %i to %i views" % 
                                (i, video.title, video.views, count)) 
                    video.views = count
                    videos_to_put.add(video)
                
                duration = int(entry.media.duration.seconds)
                if duration != video.duration:
                    video.duration = duration
                    videos_to_put.add(video)

        db.put(list(videos_to_put))
