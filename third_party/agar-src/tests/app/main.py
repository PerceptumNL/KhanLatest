#!/usr/bin/env python

from env_setup import setup_django
setup_django()

from agar.env import on_production_server
from agar.config import Config


class MainApplicationConfig(Config):
    """
    :py:class:`~agar.config.Config` settings for the ``main`` `webapp2.WSGIApplication`_.
    Settings are under the ``main_application`` namespace.

    The following settings (and defaults) are provided::

        main_application_NOOP = None

    To override ``main`` `webapp2.WSGIApplication`_ settings, define values in the ``appengine_config.py`` file in the
    root of your project.
    """
    _prefix = 'main_application'

    #: A no op.
    NOOP = None


from webapp2 import RequestHandler, WSGIApplication


class MainHandler(RequestHandler):
    def get(self):
        html = """
        <html>
            <body>
              <ul>
                <li><a href="/lib_config">lib_config settings</a></li>
                <li><a href="/api/v1/model1">/api/v1/model1</a></li>
                <li><a href="/api/v2/model1">/api/v2/model1</a></li>
              </ul>
            </body>
        </html>
        """
        self.response.out.write(html)

def get_application():
    return WSGIApplication(
        [('/', MainHandler)],
        debug=not on_production_server
    )
application = get_application()

def main():
    from google.appengine.ext.webapp import util
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
