from api.auth import xsrf
import request_handler
import user_util


class LabsRequestHandler(request_handler.RequestHandler):

    @user_util.open_access
    @xsrf.ensure_xsrf_cookie
    def get(self):
        self.render_jinja2_template('labs/labs.html', {})
