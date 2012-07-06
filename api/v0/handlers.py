
"""
v0 of our API is officially deprecated.

We've frozen static versions of old v0 results to keep old friendly
clients running that haven't managed to switch yet (like HP's Playbook
app).

We can and should remove this in the future if it becomes problematic
in any way.
"""

import urllib

from api.route_decorator import route
from api.decorators import jsonp
import api.auth.decorators

from third_party.flask import request


def safe_file_name(filename):
    # Production app engine doesn't like filenames w/ special chars
    return urllib.quote(filename).replace("%", "")


def frozen_json_content(url_suffix):
    result = ""

    try:
        f = open("v0/frozen_content/%s" % safe_file_name(url_suffix), "r")
        result = f.read()
    except Exception:
        # We simply aren't concerned enough with this API to log these errors.
        # We'll hear from anyone who really cares, and this can be removed
        # soon.
        pass

    return result


@route("/api/playlists", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
def playlists():
    return frozen_json_content("playlists")


@route("/api/playlistvideos", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
def playlist_videos():
    playlist_title = request.values["playlist"]
    return frozen_json_content("playlistvideos?playlist=%s" %
                               urllib.quote(playlist_title))


@route("/api/videolibrary", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
def video_library():
    return frozen_json_content("videolibrary")


@route("/api/videolibrarylastupdated", methods=["GET"])
@api.auth.decorators.open_access
@jsonp
def video_library_last_updated():
    return frozen_json_content("videolibrarylastupdated")
