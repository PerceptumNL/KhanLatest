"""
This module exposes a Jinja2 instance that is already configured and may be
used from any application, e.g. the main app, the API app.
"""

import webapp2
from webapp2_extras import jinja2

from app import App


class _Cache(object):
    """Thread-safe cache for creating and accessing properties at runtime."""
    @webapp2.cached_property
    def jinja2(self):
        # Make sure configuration is imported before we ever initialize,
        # which should only happen once
        import config_jinja  # @UnusedImport
        return jinja2.get_jinja2(app=_SHARED_APP)


_SHARED_APP = webapp2.WSGIApplication(debug=App.is_dev_server)
_CACHE = _Cache()


def get():
    return _CACHE.jinja2


def template_to_string(template_name, template_values):
    return get().render_template(template_name, **template_values)
