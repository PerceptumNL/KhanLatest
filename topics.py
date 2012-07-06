import api.v1_utils    # TODO(csilvers): move this to another file
import request_handler
import user_util
import logging
import layer_cache
from google.appengine.api import urlfetch
from knowledgemap import layout
from youtube_sync import youtube_get_video_data_dict


# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

import zlib

from google.appengine.ext import db
from google.appengine.ext import deferred

from api.jsonify import jsonify

import pickle_util
from topic_models import Topic, TopicVersion
from url_model import Url
import topic_models
import video_models

class EditContent(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):

        version_name = self.request.get('version', 'edit')

        edit_version = TopicVersion.get_by_id(version_name)
        if edit_version is None:
            default_version = TopicVersion.get_default_version()
            if default_version is None:
                # Assuming this is dev, there is an empty datastore and we need an import
                edit_version = TopicVersion.create_new_version()
                edit_version.edit = True
                edit_version.put()
                create_root(edit_version)
            else:
                raise Exception("Wait for setting default version to finish making an edit version.")

        if self.request.get('autoupdate', False):
            self.render_jinja2_template('autoupdate_in_progress.html', {"edit_version": edit_version})
            return
        if self.request.get('autoupdate_begin', False):
            return self.topic_update_from_live(edit_version)
        if self.request.get('migrate', False):
            return self.topic_migration()
        if self.request.get('fixdupes', False):
            return self.fix_duplicates()

        root = Topic.get_root(edit_version)
        data = root.get_visible_data()
        tree_nodes = [data]
        
        template_values = {
            'edit_version': jsonify(edit_version),
            'tree_nodes': jsonify(tree_nodes)
            }
 
        self.render_jinja2_template('topics-admin.html', template_values)
        return

    def topic_update_from_live(self, edit_version):
        layout.update_from_live(edit_version)
        try:
            response = urlfetch.fetch(
                url="http://www.khanacademy.org/api/v1/topictree",
                deadline=25)
            topictree = json.loads(response.content)

            logging.info("calling /_ah/queue/deferred_import")

            # importing the full topic tree can be too large so pickling and compressing
            deferred.defer(api.v1_utils.topictree_import_task, "edit", "root", True,
                        zlib.compress(pickle_util.dump(topictree)),
                        _queue="import-queue",
                        _url="/_ah/queue/deferred_import")

        except urlfetch.Error, e:
            logging.exception("Failed to fetch content from khanacademy.org")
  
    def fix_duplicates(self):
        dry_run = self.request.get('dry_run', False)
        video_list = [v for v in video_models.Video.all()]
        video_dict = dict()

        version = topic_models.TopicVersion.get_by_id("edit")

        videos_to_update = []
        
        for video in video_list:
            if not video.readable_id in video_dict:
                video_dict[video.readable_id] = []
            video_dict[video.readable_id].append(video)

        video_idx = 0
        print "IDX,Canon,DUP,Key,ID,YTID,Title,Topics"

        for videos in video_dict.values():
            if len(videos) > 1:
                canonical_key_id = 0
                canonical_readable_id = None
                for video in videos:
                    if topic_models.Topic.all().filter("version = ", version).filter("child_keys =", video.key()).get():
                        canonical_key_id = video.key().id()
                    if not canonical_readable_id or len(video.readable_id) < len(canonical_readable_id):
                        canonical_readable_id = video.readable_id
                
                def print_video(video, is_canonical, dup_idx):
                    canon_str = "CANONICAL" if is_canonical else "DUPLICATE"
                    topic_strings = "|".join([topic.id for topic in topic_models.Topic.all().filter("version = ", version).filter("child_keys =", video.key()).run()])
                    print "%d,%s,%d,%s,%s,%s,%s,%s" % (video_idx, canon_str, dup_idx, str(video.key()), video.readable_id, video.youtube_id, video.title, topic_strings)

                for video in videos:
                    if video.key().id() == canonical_key_id:
                        if video.readable_id != canonical_readable_id:
                            video.readable_id = canonical_readable_id
                            videos_to_update.append(video)

                        print_video(video, True, 0)

                dup_idx = 1
                for video in videos:
                    if video.key().id() != canonical_key_id:
                        new_readable_id = canonical_readable_id + "_DUP_" + str(dup_idx)

                        if video.readable_id != new_readable_id:
                            video.readable_id = new_readable_id
                            videos_to_update.append(video)

                        print_video(video, False, dup_idx)

                        dup_idx += 1

                video_idx += 1

        if len(videos_to_update) > 0:
            logging.info("Writing " + str(len(videos_to_update)) + " videos with duplicate IDs")
            if not dry_run:
                db.put(videos_to_update)
            else:
                logging.info("Just kidding! This is a dry run.")
        else:
            logging.info("No videos to update.")


class RefreshCaches(request_handler.RequestHandler):

    @user_util.developer_required
    def get(self):

        refresh_options = [
            {
                "name": "homepage",
                "description": "Homepage library content",
                "function": topic_models.preload_library_homepage
            },
            {
                "name": "browsers",
                "description": "Homepage topic browsers",
                "function": topic_models.preload_topic_browsers
            },
            {
                "name": "topicpages",
                "description": "Topic pages",
                "function": topic_models.preload_topic_pages
            },
            {
                "name": "searchindex",
                "description": "Lucene search index data",
                "function": topic_models.refresh_topictree_search_index_deferred
            },
        ]
        started_list = []

        version = topic_models.TopicVersion.get_default_version()

        for option in refresh_options:
            refresh_set = self.request_bool(option["name"], False)

            if refresh_set:
                deferred.defer(option["function"], version,
                            _queue="topics-set-default-queue",
                            _url="/_ah/queue/deferred_topics-set-default-queue")
                logging.info("Queued refresh of %s." % option["name"])
                started_list.append(option["description"])

        template_values = {
            "refresh_options": refresh_options,
            "started_list": started_list,
            }
 
        self.render_jinja2_template('topics-refresh.html', template_values)


# function to create the root, needed for first import into a dev env
def create_root(version):
    Topic.insert(title="The Root of All Knowledge",
            description="All concepts fit into the root of all knowledge",
            id="root",
            version=version)

@layer_cache.cache(layer=layer_cache.Layers.Memcache | layer_cache.Layers.Datastore, expiration=86400)
def getSmartHistoryContent():
    try:
        response = urlfetch.fetch(url="http://khan.smarthistory.org/"
                                  "youtube-urls-for-khan-academy.html", 
                                  deadline=25)
        smart_history = json.loads(response.content)
    except urlfetch.Error, e:
        logging.exception("Failed fetching smarthistory video list")
        smart_history = None
    return smart_history

class ImportSmartHistory(request_handler.RequestHandler):

    @user_util.manual_access_checking  # superuser-only via app.yaml (/admin)
    def get(self):
        """update the default and edit versions of the topic tree with smarthistory (creates a new default version if there are changes)"""
        default = topic_models.TopicVersion.get_default_version()
        edit = topic_models.TopicVersion.get_edit_version()
        
        logging.info("importing into edit version")
        # if there are any changes to the edit version
        if ImportSmartHistory.importIntoVersion(edit):

            # make a copy of the default version, 
            # update the copy and then mark it default
            logging.info("creating new default version")
            new_version = default.copy_version()
            new_version.title = "SmartHistory Update"
            new_version.put()

            logging.info("importing into new version")
            ImportSmartHistory.importIntoVersion(new_version)
                
            logging.info("setting version default")
            new_version.set_default_version()
            logging.info("done setting version default")

        logging.info("done importing smart history")

                        
    @staticmethod
    def importIntoVersion(version):
        logging.info("comparing to version number %i" % version.number)
        topic = Topic.get_by_id("art-history", version)

        if not topic:
            parent = Topic.get_by_id("humanities---other", version)
            if not parent:
                raise Exception("Could not find the Humanities & Other topic to put art history into")
            topic = Topic.insert(title="Art History",
                                 parent=parent,
                                 id="art-history",
                                 standalone_title="Art History",
                                 description="Spontaneous conversations about works of art where the speakers are not afraid to disagree with each other or art history orthodoxy. Videos are made by Dr. Beth Harris and Dr. Steven Zucker along with other contributors.")
        
        urls = topic.get_urls(include_descendants=True)
        href_to_key_dict = dict((url.url, url.key()) for url in urls)
        
        videos = topic.get_videos(include_descendants=True)
        video_dict = dict((v.youtube_id, v) for v in videos)

        content = getSmartHistoryContent()
        if content is None:
            raise Exception("Aborting import, could not read from smarthistory")

        subtopics = topic.get_child_topics()
        subtopic_dict = dict((t.title, t) for t in subtopics)
        subtopic_child_keys = {}
        
        new_subtopic_keys = []

        i = 0
        for link in content:
            href = link["href"]
            title = link["title"]
            parent_title = link["parent"]
            content = link["content"]
            youtube_id = link["youtube_id"] if "youtube_id" in link else None
            extra_properties = {"original_url": href}

            if parent_title not in subtopic_dict:
                subtopic = Topic.insert(title=parent_title,
                                 parent=topic,
                                 standalone_title="Art History: %s" 
                                                  % parent_title,
                                 description="")

                subtopic_dict[parent_title] = subtopic
            else:
                subtopic = subtopic_dict[parent_title]
           
            if subtopic.key() not in new_subtopic_keys:
                new_subtopic_keys.append(subtopic.key())

            if parent_title not in subtopic_child_keys:
                subtopic_child_keys[parent_title] = []
            
            if youtube_id:
                if youtube_id not in video_dict:
                    # make sure it didn't get imported before, but never put 
                    # into a topic
                    query = video_models.Video.all()
                    video = query.filter("youtube_id =", youtube_id).get()

                    if video is None:
                        logging.info("adding youtube video %i %s %s %s to %s" % 
                                     (i, youtube_id, href, title, parent_title))
                        
                        video_data = youtube_get_video_data_dict(youtube_id)
                        # use the title from the webpage not from the youtube 
                        # page
                        video = None
                        if video_data:
                            video_data["title"] = title
                            video_data["extra_properties"] = extra_properties
                            video = topic_models.VersionContentChange.add_new_content(
                                                                video_models.Video,
                                                                version,
                                                                video_data)
                        else:
                            logging.error(("Could not import youtube_id %s " +
                                          "for %s %s") % (youtube_id, href, title))
                            
                            raise Exception(("Could not import youtube_id %s " +
                                            " for %s %s") % (youtube_id, href, 
                                            title))

                else:
                    video = video_dict[youtube_id] 
                    if video.extra_properties != extra_properties:
                        logging.info(("changing extra properties of %i %s %s " +
                                     "from %s to %s") % (i, href, title, 
                                     video.extra_properties, extra_properties))
                        
                        video.extra_properties = extra_properties
                        video.put()
                                    
                if video:
                    subtopic_child_keys[parent_title].append(video.key())

            elif href not in href_to_key_dict:
                logging.info("adding %i %s %s to %s" % 
                             (i, href, title, parent_title))
                
                topic_models.VersionContentChange.add_new_content(
                    Url, 
                    version,
                    {"title": title,
                     "url": href
                    },
                    ["title", "url"])

                url = Url(url=href,
                          title=title,
                          id=id)

                url.put()
                subtopic_child_keys[parent_title].append(url.key())

            else:
                subtopic_child_keys[parent_title].append(href_to_key_dict[href])

            i += 1

        logging.info("updating child_keys")
        change = False
        for parent_title in subtopic_child_keys.keys():
            subtopic = subtopic_dict[parent_title]
            if subtopic.child_keys != subtopic_child_keys[parent_title]:
                change = True
                subtopic.update(child_keys=subtopic_child_keys[parent_title])
        
        if topic.child_keys != new_subtopic_keys:    
            change = True
            topic.update(child_keys=new_subtopic_keys)
        
        if change:
            logging.info("finished updating version number %i" % version.number)
        else:
            logging.info("nothing changed")

        return change
