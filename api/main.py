import logging
from types import GeneratorType

from google.appengine.ext.webapp.util import run_wsgi_app

import request_cache
from app import App
from gae_mini_profiler import profiler
from gae_bingo import middleware
import wsgi_compat

# While not referenced directly, these imports have necessary side-effects.
# (e.g. Paths are mapped to the API request handlers with the "route" wrapper)
from api.route_decorator import api_app
import api.api_request_class  # @UnusedImport
import api.auth.auth_handlers  # @UnusedImport
import api.v0.handlers  # @UnusedImport
import api.v1  # @UnusedImport
import api.labs.handlers  # @UnusedImport
import api.v1_fetch_logs  # @UnusedImport


class ProfilerMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # This is the main function for profiling
        # We've renamed our original main() above to real_main()
        import cProfile
        import pstats
        prof = cProfile.Profile()

        # Get profiled wsgi result
        result = prof.runcall(
            lambda *args, **kwargs: self.app(environ, start_response),
            None,
            None)

        # If we're dealing w/ a generator, profile all of the .next
        # calls as well
        if type(result) == GeneratorType:
            while True:
                try:
                    yield prof.runcall(result.next)
                except StopIteration:
                    break
        else:
            for value in result:
                yield value

        print "<pre>"
        stats = pstats.Stats(prof)
        stats.sort_stats("cumulative")  # time or cumulative
        stats.print_stats(80)  # 80 = how many to print
        # The rest is optional.
        # stats.print_callees()
        stats.print_callers()
        print "</pre>"


application = request_cache.RequestCacheMiddleware(api_app)
application = profiler.ProfilerWSGIMiddleware(application)
application = middleware.GAEBingoWSGIMiddleware(application)
application = wsgi_compat.WSGICompatHeaderMiddleware(application)

if App.is_dev_server:
    try:
        # Run debugged app
        from third_party.werkzeug_debugger_appengine import get_debugged_app
        api_app.debug = True
        application = get_debugged_app(application)
    except Exception, e:
        api_app.debug = False
        logging.warning("Error running debugging version of werkzeug app, "
                        "running production version: %s" % e)
    
# Uncomment the following line to enable profiling 
#application = ProfilerMiddleware(application)


def main():
    run_wsgi_app(application)

# Use App Engine app caching
if __name__ == "__main__":
    main()
