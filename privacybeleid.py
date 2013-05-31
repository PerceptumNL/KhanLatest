#import request_handler
#import user_util
#from api.auth.xsrf import ensure_xsrf_cookie

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

class ViewPrivacybeleidPage(request_handler.RequestHandler):
    @user_util.open_access
    @ensure_xsrf_cookie
    def get(self):
        some_value = 100
        template_values = {'some_value': some_value,}
        self.render_jinja2_template('privacybeleid.html', template_values)
        layer_cache.enable()
