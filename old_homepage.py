import datetime
import random

from jinja2.utils import escape

import exercise_models
import library
import request_handler
import user_util
import user_models
import video_models
import layer_cache
import setting_model
import templatetags
import topic_models
from app import App
from topics_list import DVD_list
from api.auth.xsrf import ensure_xsrf_cookie


ITEMS_PER_SET = 4


def thumbnail_link_dict(video=None, exercise=None, thumb_url=None,
                        parent_topic=None):

    link_dict = None

    if video:
        if parent_topic:
            href = "/%s/v/%s" % (parent_topic.get_extended_slug(),
                                 video.readable_id)
        else:
            href = "/video/%s" % video.readable_id
        link_dict = {
            "href": href,
            "thumb_urls": (
                video_models.Video.youtube_thumbnail_urls(video.youtube_id)),
            "title": video.title,
            "desc_html": templatetags.video_name_and_progress(video),
            "teaser_html": unicode(video.description),
            "youtube_id": video.youtube_id,
            "marquee": ("marquee" in video.keywords),
            "selected": False,
            "key": unicode(video.key()),
            "type": "video-thumb",
        }

    if exercise:
        link_dict = {
            "href": exercise.relative_url,
            "thumb_urls": {"hq": thumb_url, "sd": thumb_url},
            "desc_html": escape(exercise.display_name),
            "teaser_html": ("Exercise your <em>%s</em> skills"
                            % escape(exercise.display_name)),
            "youtube_id": "",
            "marquee": False,
            "selected": False,
            "key": exercise.key(),
            "type": "exercise-thumb",
        }

    if link_dict:

        if link_dict["teaser_html"] and len(link_dict["teaser_html"]) > 60:
            link_dict["teaser_html"] = (link_dict["teaser_html"][:60]
                                        + "&hellip;")

        return link_dict

    return None


@layer_cache.cache_with_key_fxn(
        lambda *args, **kwargs: "new_and_noteworthy_link_sets_%s" %
            setting_model.Setting.topic_tree_version(),
        expiration=86400
        )
def new_and_noteworthy_link_sets():
    topic = topic_models.Topic.get_by_id("new-and-noteworthy")
    if topic is None:
        return []
    videos = topic.get_cached_videos_for_topic(topic)

    if len(videos) < 2:
        # If there's only one video, don't bother.
        return []

    exercises = []

    if len(exercises) == 0:
        # Temporary hard-coding of a couple exercises - eventually can
        # take exercises in the topic - but not until they all have
        # splashthumbnails.
        topic.tags = ['derivative_intuition', 'inequalities_on_a_number_line',
                      'multiplication_4', 'solid_geometry']
        for tag in topic.tags:
            exercise = exercise_models.Exercise.get_by_name(tag)
            if exercise:
                exercises.append(exercise)

    sets = []
    current_set = []
    next_exercise = 0

    # Randomly place exercises one per set in 2, 3, or 4
    current_set_exercise_position = random.randint(1, ITEMS_PER_SET - 1)

    exercise_icon_files = ["ex1.png", "ex2.png", "ex3.png", "ex4.png"]
    random.shuffle(exercise_icon_files)

    for video in videos:

        if len(current_set) >= ITEMS_PER_SET:
            sets.append(current_set)
            current_set = []
            current_set_exercise_position = random.randint(0,
                                                           ITEMS_PER_SET - 1)

        if (next_exercise < len(exercises) and
            len(current_set) == current_set_exercise_position):
            exercise = exercises[next_exercise]

            icon_file_index = next_exercise % (len(exercise_icon_files))
            thumb_url = "/images/splashthumbnails/exercises/%s" % (
                exercise_icon_files[icon_file_index])
            current_set.append(thumbnail_link_dict(exercise=exercise,
                                                   thumb_url=thumb_url))

            next_exercise += 1

        if len(current_set) >= ITEMS_PER_SET:
            sets.append(current_set)
            current_set = []
            current_set_exercise_position = random.randint(0,
                                                           ITEMS_PER_SET - 1)

        current_set.append(thumbnail_link_dict(video=video))

    if len(current_set) > 0:
        sets.append(current_set)

    return sets


class ViewHomePage(request_handler.RequestHandler):

    @user_util.open_access
    def head(self):
        # Respond to HEAD requests for our homepage so twitter's tweet
        # counter will update:
        # https://dev.twitter.com/docs/tweet-button/faq#count-api-increment
        pass

    # See https://sites.google.com/a/khanacademy.org/forge/for-team-members/how-to-use-new-and-noteworthy-content
    # for info on how to update the New & Noteworthy videos
    @user_util.open_access
    @ensure_xsrf_cookie    # TODO(csilvers): remove this (test w/ autocomplete)
    def get(self):
        version_number = None

        if (user_models.UserData.current() and
            user_models.UserData.current().developer):
            version_number = self.request_string('version', default=None)

        thumbnail_link_sets = new_and_noteworthy_link_sets()

        # If all else fails, just show the TED talk on the homepage
        marquee_video = {
            "youtube_id": "gM95HHI4gLk",
            "href": "/video?v=%s" % "gM95HHI4gLk",
            "thumb_urls": (
                video_models.Video.youtube_thumbnail_urls("gM95HHI4gLk")),
            "title": "Salman Khan talk at TED 2011",
            "key": "",
        }
        if len(thumbnail_link_sets) > 1:

            day = datetime.datetime.now().day

            # Switch up the first 4 New & Noteworthy videos on a daily basis
            current_link_set_offset = day % len(thumbnail_link_sets)

            # Switch up the marquee video on a daily basis
            marquee_videos = []
            for thumbnail_link_set in thumbnail_link_sets:
                marquee_videos += filter(lambda item: item["marquee"],
                                         thumbnail_link_set)

            if marquee_videos:
                marquee_video = marquee_videos[day % len(marquee_videos)]
                marquee_video["selected"] = True

            thumbnail_link_sets = (
                thumbnail_link_sets[current_link_set_offset:]
                + thumbnail_link_sets[:current_link_set_offset])

            # If there is a set of videos that isn't full,
            # move it to the last position in the carousel.
            for i, link_set in enumerate(thumbnail_link_sets):
                if len(link_set) < ITEMS_PER_SET:
                    thumbnail_link_sets[i], thumbnail_link_sets[-1] = (
                            thumbnail_link_sets[-1], thumbnail_link_sets[i])

        content_uninitialized = (
            topic_models.TopicVersion.get_default_version() is None)

        if content_uninitialized:
            library_content = ('<h1>Content not initialized. '
                               '<a href="/devadmin/content?autoupdate=1">'
                               'Click here</a> '
                               'to autoupdate from khanacademie.nl.')
        elif version_number:
            layer_cache.disable()
            library_content = library.library_content_html(
                version_number=int(version_number))
        elif self.is_mobile_capable():
            # Only running ajax version of homepage for non-mobile clients
            library_content = library.library_content_html(ajax=False)
        else:
            library_content = library.library_content_html(ajax=True)

        from gae_bingo.gae_bingo import create_redirect_url

        donate_redirect_url = create_redirect_url("/donate",
                                                  "hp_donate_button_click")

        from rssblog_model import RSSBlog
        template_values = {
            'rssblog': RSSBlog.get(0, 4),
            'marquee_video': marquee_video,
            'thumbnail_link_sets': thumbnail_link_sets,
            'library_content': library_content,
            'DVD_list': DVD_list,
            'is_mobile_allowed': True,
            'approx_vid_count': video_models.Video.approx_count(),
            'link_heat': self.request_bool("heat", default=False),
            'version_number': version_number,
            'donate_redirect_url': donate_redirect_url
            }

        self.render_jinja2_template('old_homepage.html', template_values)

        layer_cache.enable()
