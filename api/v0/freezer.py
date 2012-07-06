import json
import urllib2
import urllib

"""
v0 of our API is officially deprecated.

We've frozen static versions of old v0 results to keep old friendly
clients running that haven't managed to switch yet (like HP's Playbook
app).

We can and should remove this in the future if it becomes problematic
in any way.
"""


def safe_file_name(filename):
    # Production app engine doesn't like filenames w/ special chars
    return urllib.quote(filename).replace("%", "")


def freeze(api_url_suffix):

    print "Freezing %s" % api_url_suffix

    request = urllib2.urlopen("http://www.khanacademy.org/api/%s" %
                              api_url_suffix)

    response = ""
    response_json = None

    try:
        response = request.read()
        response_json = json.loads(response)
    finally:
        request.close()

    result = open("frozen_content/%s" % safe_file_name(api_url_suffix), "w")
    result.write(response)

    print "Froze %s" % api_url_suffix

    return response_json


def freeze_v0():
    playlists = freeze("playlists")

    for playlist in playlists:
        freeze("playlistvideos?playlist=%s" % urllib.quote(playlist["title"]))

    freeze("videolibrary")
    freeze("videolibrarylastupdated")

if __name__ == "__main__":
    freeze_v0()
