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

class ViewBrowsePage(request_handler.RequestHandler):
    @user_util.open_access
    @ensure_xsrf_cookie    # TODO(csilvers): remove this (test w/ autocomplete)
    def get(self):
        version_number = None

        if (user_models.UserData.current() and
            user_models.UserData.current().developer):
            version_number = self.request_string('version', default=None)

        content_uninitialized = (
            topic_models.TopicVersion.get_default_version() is None)
#        '''
        if content_uninitialized:
            library_content = ('<h1>Content not initialized. '
                               '<a href="/devadmin/content?autoupdate=1">'
                               'Click here</a> '
                               'to autoupdate from iktel.nl.')
        elif version_number:
            layer_cache.disable()
            library_content = library.library_content_html(
                version_number=int(version_number))
        elif self.is_mobile_capable():
            # Only running ajax version of homepage for non-mobile clients
            library_content = library.library_content_html(ajax=False)
        else:
            library_content = library.library_content_html(ajax=True)
 #       '''

#        library_content = library.library_content_html(ajax=True)

        template_values = {
            'library_content': library_content,
        }
        self.render_jinja2_template('browsepage.html', template_values)

        layer_cache.enable()
