from __future__ import absolute_import

import request_handler
import user_util
from api.auth.xsrf import ensure_xsrf_cookie


class SocratesHandler(request_handler.RequestHandler):
    @user_util.open_access
    @ensure_xsrf_cookie
    def get(self, path, video_id):
        if not path:
            return

        path_list = path.split('/')

        if not path_list:
            return

        topic_id = path_list[-1]
        from main import ViewVideo
        context = ViewVideo.show_video(self, video_id, topic_id)
        if not context:
            return

        context['has_socrates'] = True

        self.render_jinja2_template('labs/socrates/viewvideo.html', context)


class SocratesIndexHandler(request_handler.RequestHandler):
    @user_util.open_access
    @ensure_xsrf_cookie
    def get(self):
        self.render_jinja2_template("labs/socrates/index.html", {})
        return
