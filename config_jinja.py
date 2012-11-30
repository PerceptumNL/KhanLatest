# Jinja2 config

# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

import os
from webapp2_extras import jinja2

# Bring in our globally available custom templates and tags.
# When possible, we now use jinja macros instead of these global tags.
from user_models import UserData
import templatetags
import templatefilters
import avatars.templatetags
import badges.templatetags
import profiles.templatetags
import phantom_users.templatetags
import js_css_packages.templatetags
import gae_mini_profiler.templatetags
import gandalf.bridge
import api.auth.xsrf
import url_util
import util
from app import App
import handlebars.render

_file_dir = os.path.dirname(__file__)

jinja2.default_config = {
    "template_path": os.path.join(_file_dir, "templates"),
    "compiled_path": os.path.join(_file_dir, "compiled_templates.zip"),

    # Only use compiled templates in production
    "force_compiled": not App.is_dev_server,

    # Only cache in production
    "cache_size": 0 if App.is_dev_server else -1,

    # Don't check for template updates in production
    "auto_reload": App.is_dev_server,

    "globals": {
        "templatetags": templatetags,
        "profiles": profiles.templatetags,
        "avatars": avatars.templatetags,
        "badges": badges.templatetags,
        "phantom_users": phantom_users.templatetags,
        "js_css_packages": js_css_packages.templatetags,
        "gae_mini_profiler": gae_mini_profiler.templatetags,
        "xsrf": api.auth.xsrf,
        "UserData": UserData,
        "json": json,
        "App": App,
        "handlebars_template": handlebars.render.render_from_jinja,
        "gandalf": gandalf.bridge.gandalf,
    },
    "filters": {
        "urlencode": templatefilters.urlencode,
        "strip": lambda s: (s or "").strip(),
        "escapejs": templatefilters.escapejs,
        "phantom_login_link": templatefilters.phantom_login_link,
        "slugify": templatefilters.slugify,
        "pluralize": templatefilters.pluralize,
        "linebreaksbr": templatefilters.linebreaksbr,
        "linebreaksbr_js": templatefilters.linebreaksbr_js,
        "linebreaksbr_ellipsis": templatefilters.linebreaksbr_ellipsis,
        "youtube_timestamp_links": templatefilters.youtube_timestamp_links,
        "timesince_ago": templatefilters.timesince_ago,
        "seconds_to_time_string": templatefilters.seconds_to_time_string,
        "mygetattr": templatefilters.mygetattr,
        "find_column_index": templatefilters.find_column_index,
        "in_list": templatefilters.in_list,
        "column_height": templatefilters.column_height,
        "bingo_redirect_url": templatefilters.bingo_redirect_url,
        "thousands_separated": util.thousands_separated_number,
        "static_url": url_util.static_url,
        "login_url": url_util.create_login_url,
        "fix_url_domain": templatefilters.fix_url_domain,
        "formatdate": templatefilters.formatdate,
    },
    "environment_args": {
        "autoescape": False,
        "extensions": [],
        },
    }
