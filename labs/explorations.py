from api.auth.xsrf import ensure_xsrf_cookie
from custom_exceptions import MissingExerciseException
from user_util import open_access
import request_handler

EXPLORATIONS = [
    # Crypto
    'frequency-fingerprint',
    'frequency-stability',
    'perfect-secrecy',
    'pseudorandom-walk'
]


class RequestHandler(request_handler.RequestHandler):
    @open_access
    @ensure_xsrf_cookie
    def get(self, exploration=None):
        if not exploration:
            self.render_jinja2_template('labs/explorations/index.html', {})
        elif exploration in EXPLORATIONS:
            self.render_jinja2_template(
                'labs/explorations/%s.html' % exploration, {})
        else:
            raise MissingExerciseException('Missing exploration %s'
                                           % exploration)
