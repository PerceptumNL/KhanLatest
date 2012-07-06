"""A handler to return a subset of the appengine logs.

This is motivated by the following discussion with appengine support:

   Created By: Wen Gong (4/3/2012 11:14 AM)
   Hi Ben,

   For large amount of logs, it's a known issue that the appcfg.py
   does not work well. We recommend to use the LogService API:
   https://developers.google.com/appengine/docs/python/logservice/functions

   1) There is, however, a limit on a daily log download, which is set
   to 1 million log records per day, and for applications that are
   Tier-0 in quovadis (I'm guessing your app would be in this
   category), that number is 25 million.

   2) If you have large log, you may want to create multiple tasks
   (using taskqueue) with each task download a small portion of the
   logs (i.e., 5s worth of logs).

   3) You can't write the logs to local file in this way. However, you
   can store the logs into Blobstore, and download it from there:
   http://code.google.com/appengine/docs/python/blobstore/overview.html

   4) It would seem logical then perhaps you build in some logic in
   the tasks dealing with the log download, and do your analysis right
   there so you can store the data in a way that can be easily used.

   5) If you also provide a Blobstore Serving servlet, you could
   potentially navigate the logs using a browser.

This handler does a simpler version: it makes the logservice calls
synchronously, and just returns them via http.  You specify the
start-time and end-time (as a time_t).
"""

import os

from google.appengine.api import logservice
from third_party.flask import request

import api.auth.decorators
import api.decorators
from api import route_decorator


route = route_decorator.route


def _header_lines(appengine_versions):
    """Return the first lines of our API response, as a list of strings."""
    return ['appengine_versions: %s' % ','.join(appengine_versions),
            ]


def _unicodify(s):
    """Returns a version of s that's a unicode string, if necessary."""
    assert isinstance(s, basestring)
    if isinstance(s, str):
        return s.decode('utf-8', errors='replace')
    return s


def _request_log_to_string(log):
    """Given a logservice RequestLog object, return a string version.

    Arguments:
       log: a logservice RequestLog object.

    Returns:
        The string version is the same as what appengine logs:

        <apache logline content> "<host>" ms=### cpu_ms=### api_cpu_ms=### \
           cpm_usd=### queue_name=xxx task_name=### pending_ms=### instance=###
        \t<log message if any>
        \t<log message if any>
        [...]

        Note this may be multiple lines long.  The return value includes
        the trailing newline!
    """
    if log.task_queue_name and log.task_name:
        taskqueue_info = (' queue_name=%s task_name=%s'
                          % (log.task_queue_name, log.task_name))
    else:
        taskqueue_info = ''

    loglines = ['%s "%s" ms=%s cpu_ms=%s api_cpu_ms=%s cpm_usd=%.6f'
                '%s pending_ms=%s instance=%s'
                % (log.combined,
                   log.host or '<unknown>',
                   int(log.latency * 1000),
                   log.mcycles,      # TODO(csilvers): convert to ms!
                   log.api_mcycles,  # TODO(csilvers): convert to ms!
                   log.cost,
                   taskqueue_info,
                   int(log.pending_time * 1000),
                   log.instance_key)
                ]

    for app_log in log.app_logs:
        loglines.append('\t%s:%s %s' % (app_log.level, app_log.time,
                                        app_log.message))

    return '\n'.join(loglines)


def fetch_logs(start_time_t, end_time_t, appengine_versions=None):
    return logservice.fetch(start_time=start_time_t, end_time=end_time_t,
                            include_app_logs=True,
                            version_ids=appengine_versions)


@route("/api/v1/fetch_logs/<int:start_time_t>/<int:end_time_t>",
       methods=["GET"])
@api.auth.decorators.developer_required
@api.decorators.compress
def api_fetch_logs(start_time_t, end_time_t):
    """Return the appengine logs as zlib-compressed data, one log per line.

    The format is the same as what the google logserver does.

    Arguments:
        start_time_t: return only logs from this time and afterwards.
        end_time_t: return only logs from before this time.

    Returns:
       Some header lines, followed by a blank line, followed by a list
       of loglines, the same format as google makes its logs
       available.  This output is zlib-compressed, appropriate to be
       decompressed with zlib.uncompress().  Note that this is *not*
       gzip-compressed!  You can't use gunzip or similar on it.  It
       must be zlib.
    """
    appengine_versions = request.values.getlist("appengine_version")
    if not appengine_versions:
        # We are explicit about which appengine versions we're
        # fetching in order to be able to log that information.
        major_and_minor_version = os.getenv('CURRENT_VERSION_ID', 'unknown.x')
        current_version = major_and_minor_version.split('.', 1)[0]
        appengine_versions = [current_version]

    logs = fetch_logs(start_time_t, end_time_t, appengine_versions)

    retval = _header_lines(appengine_versions)
    retval.append('')   # blank line separating headers from loglines
    retval.extend(_unicodify(_request_log_to_string(rl)) for rl in logs)
    retval.append('')   # to get a trailing newline
    return '\n'.join(retval)
