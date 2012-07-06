import urllib
import urllib2

# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

from google.appengine.api import memcache

from custom_exceptions import TumblrException
from app import App
from coach_resources import util_coach
import user_util

SCHOOLS_TUMBLR_URL = "http://ka-implementations.tumblr.com"
POSTS_PER_PAGE = 5


class BlogPost:
    def __init__(self, dict_json):
        self.post_id = dict_json["id"]
        self.title = dict_json["regular-title"]
        self.body = dict_json["regular-body"]
        self.dt = dict_json["date"]
        self.url = dict_json["url-with-slug"]
        self.slug = dict_json["slug"]

    def local_url(self):
        return "/coach/schools-blog"


class TumblrDownBlogPost(BlogPost):
    def __init__(self):
        self.post_id = ""
        self.title = "Temporarily unavailable"
        self.body = ("Our blog is temporarily unavailable but will be "
                     "back soon.")
        self.dt = ""
        self.url = "/coach/schools-blog"
        self.slug = ""


def strip_json(json_string):

    json_string = json_string.strip()

    if not json_string.startswith("{"):
        json_string = json_string[json_string.index("{"):]

    if not json_string.endswith("}"):
        json_string = json_string[:json_string.rindex("}") + 1]

    return json_string


def get_posts(offset=0, post_id=None, force_refresh=False):

    json_string = ""

    params = {"start": offset, "num": POSTS_PER_PAGE + 1, "type": "text"}
    if post_id:
        params = {"id": post_id}

    params_encoded = urllib.urlencode(params)

    memcache_key = "blog_posts_%s" % params_encoded
    posts = memcache.get(memcache_key, namespace=App.version)

    if not posts or force_refresh:
        try:
            request = urllib2.urlopen("%s/api/read/json" % SCHOOLS_TUMBLR_URL,
                                      params_encoded)
            json_string = request.read()
        except:
            raise TumblrException(
                "Error while grabbing blog posts from Tumblr.")

        posts = []

        try:
            json_string = strip_json(json_string)
            posts = parse_json_posts(json_string)
        except:
            raise TumblrException("Error while parsing blog posts from Tumblr")

        if posts:
            # Cache for an hour
            memcache.set(memcache_key, posts, time=60 * 60,
                         namespace=App.version)

    return posts


def get_single_post(post_id, force_refresh=False):
    posts = get_posts(0, post_id, force_refresh)
    if len(posts):
        return posts[0]
    return None


def parse_json_posts(json_string):

    dict_json = None
    dict_json = json.loads(json_string)

    if not dict_json:
        return []

    posts = []
    for json_post in dict_json["posts"]:
        post = BlogPost(json_post)
        posts.append(post)

    return posts


class ViewBlog(util_coach.CoachResourcesRequestHandler):

    @user_util.open_access
    def get(self):

        offset = self.request_int("offset", default=0)
        force_refresh = self.request_bool("force_refresh", default=False)

        posts = []
        try:
            posts = get_posts(offset, None, force_refresh)
        except TumblrException:
            posts = [TumblrDownBlogPost()]

        has_prev = offset > 0
        has_next = len(posts) > POSTS_PER_PAGE
        prev_offset = max(0, offset - POSTS_PER_PAGE)
        next_offset = offset + POSTS_PER_PAGE

        posts = posts[:POSTS_PER_PAGE]

        dict_context = {
                "posts": posts, 
                "has_prev": has_prev, 
                "has_next": has_next, 
                "prev_offset": prev_offset,
                "next_offset": next_offset,
                "selected_id": "schools-blog",
                "not_in_toolkit_format": 1,
                "base_url": "/toolkit",
        }

        self.render_jinja2_template('coach_resources/view_blog.html',
                                    dict_context)
