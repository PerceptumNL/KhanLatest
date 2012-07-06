from __future__ import absolute_import
import datetime
import time

import request_handler
import user_util
from google.appengine.api import memcache
from google.appengine.api.capabilities import CapabilitySet


class MemcacheStatus(request_handler.RequestHandler):
    """Handle requests to show information about the current state of memcache.

    Gives raw data, suitable for plotting.

    This is open-access so it's easy to write a script to download this
    data and store it.  Nothing here is sensitive.
    TODO(csilvers): save the data and show a pretty graphy.
    """

    @user_util.open_access
    def get(self):
        now = datetime.datetime.now()
        now_time_t = int(time.mktime(now.timetuple()))
        is_enabled = CapabilitySet('memcache').is_enabled()
        memcache_stats = memcache.get_stats()

        if self.request.get('output') in ('text', 'txt'):
            self.response.out.write(now_time_t)
            self.response.out.write(' up' if is_enabled else ' down')
            self.response.out.write(' h:%(hits)s'
                                    ' m:%(misses)s'
                                    ' bh:%(byte_hits)s'
                                    ' i:%(items)s'
                                    ' b:%(bytes)s'
                                    ' oia:%(oldest_item_age)s'
                                    '\n' % memcache_stats)
            self.response.headers['Content-Type'] = "text/text"
        else:
            template_values = {
                'now': now.ctime(),
                'now_time_t': now_time_t,
                'is_enabled': is_enabled,
                'memcache_stats': memcache_stats,
            }
            self.render_jinja2_template("memcache_stats.html", template_values)
