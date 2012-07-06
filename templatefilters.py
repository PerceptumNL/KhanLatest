import re
import os
import math
from urllib import quote_plus
import urlparse

import url_util
import util
import gae_bingo.gae_bingo

def urlencode(s):
    if isinstance(s, unicode):
        return quote_plus(s.encode("utf-8"))
    else:
        return quote_plus(s or "")

def timesince_ago(content):
    if not content:
        return ""
    return append_ago(seconds_to_time_string(util.seconds_since(content)))

def seconds_to_time_string(seconds_init, short_display = True):

    seconds = seconds_init

    years = math.floor(seconds / (86400 * 365))
    seconds -= years * (86400 * 365)

    days = math.floor(seconds / 86400)
    seconds -= days * 86400

    months = math.floor(days / 30.5)
    weeks = math.floor(days / 7)

    hours = math.floor(seconds / 3600)
    seconds -= hours * 3600

    minutes = math.floor(seconds / 60)
    seconds -= minutes * 60

    if years:
        return "%d year%s" % (years, pluralize(years))
    elif months:
        return "%d month%s" % (months, pluralize(months))
    elif weeks:
        return "%d week%s" % (weeks, pluralize(weeks))
    elif days and hours and not short_display:
        return "%d day%s and %d hour%s" % (days, pluralize(days), hours, pluralize(hours))
    elif days:
        return "%d day%s" % (days, pluralize(days))
    elif hours:
        if minutes and not short_display:
            return "%d hour%s and %d minute%s" % (hours, pluralize(hours), minutes, pluralize(minutes))
        else:
            return "%d hour%s" % (hours, pluralize(hours))
    else:
        if seconds and not minutes:
            return "%d second%s" % (seconds, pluralize(seconds))
        return "%d minute%s" % (minutes, pluralize(minutes))


def youtube_timestamp_links(content):
    def replace(match):
        seconds = int(match.group(2))
        seconds += 60 * int(match.group(1))
        return "<span class='youTube' seconds='%s'>%s</span>" % (
            seconds, match.group(0))

    return re.sub(r'\b(\d+):([0-5]\d)\b', replace, content)


def phantom_login_link(login_notifications, continue_url):
    return login_notifications.replace("[login]", "<a href='/login?continue="+continue_url+"' class='simple-button green'>Log in to save your progress</a>")

def append_ago(s_time):
    if not s_time:
        return ""
    return re.sub("^0 minutes ago", "just now", s_time + " ago")

def in_list(content, list):
    return content in list

def find_column_index(content, column_index_list):
    for index, column_breakpoint in enumerate(column_index_list):
        if (content < column_breakpoint):
            return index
    return len(column_index_list)

def column_height(list_item_index, column_breakpoints):
    height = list_item_index
    if not column_breakpoints.index(list_item_index) == 0:
        height = list_item_index - column_breakpoints[column_breakpoints.index(list_item_index) - 1]
    return height

def slugify(value):
    # Just like Django's version of slugify
    "Converts to lowercase, removes non-alpha chars and converts spaces to hyphens"
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)

def mygetattr(obj, name):
    return getattr(obj, name)

_base_js_escapes = (
    ('\\', r'\u005C'),
    ('\'', r'\u0027'),
    ('"', r'\u0022'),
    ('>', r'\u003E'),
    ('<', r'\u003C'),
    ('&', r'\u0026'),
    ('=', r'\u003D'),
    ('-', r'\u002D'),
    (';', r'\u003B'),
    (u'\u2028', r'\u2028'),
    (u'\u2029', r'\u2029')
)

# Escape every ASCII character with a value less than 32.
_js_escapes = (_base_js_escapes +
               tuple([('%c' % z, '\\u%04X' % z) for z in range(32)]))

# escapejs from Django: https://www.djangoproject.com/
def escapejs(value):
    """Hex encodes characters for use in JavaScript strings."""
    if not isinstance(value, basestring):
        value = str(value)

    for bad, good in _js_escapes:
        value = value.replace(bad, good)

    return value

# TODO(alpert): Why does this exist? Can it just be static_url =
# url_util.static_url? (Can it be removed?)
def static_url(relative_url):
    return url_util.static_url(relative_url)

def linebreaksbr(s):
    return unicode(s).replace('\n', '<br />')

def linebreaksbr_js(s):
    return unicode(s).replace('\\u000A', '<br />')

def linebreaksbr_ellipsis(content, ellipsis_content = "&hellip;"):

    # After a specified number of linebreaks, apply span with a CSS class
    # to the rest of the content so it can be optionally hidden or shown
    # based on its context.
    max_linebreaks = 4

    # We use our specific "linebreaksbr" filter, so we don't
    # need to worry about alternate representations of the <br /> tag.
    content = linebreaksbr(content.strip())

    rg_s = re.split("<br />", content)
    if len(rg_s) > (max_linebreaks + 1):
        # More than max_linebreaks <br />'s were found.
        # Place everything after the 3rd <br /> in a hidden span that can be exposed by CSS later, and
        # Append an ellipsis at the cutoff point with a class that can also be controlled by CSS.
        rg_s[max_linebreaks] = "<span class='ellipsisExpand'>%s</span><span class='hiddenExpand'>%s" % (ellipsis_content, rg_s[max_linebreaks])
        rg_s[-1] += "</span>"

    # Join the string back up w/ its original <br />'s
    return "<br />".join(rg_s)

def pluralize(i):
    return "" if i == 1 else "s"

def bingo_redirect_url(url, conversions):
    return gae_bingo.gae_bingo.create_redirect_url(url, conversions)

def fix_url_domain(url):
    """ Fix up the domain of the URL to point to the current domain. """

    parsed_url = urlparse.urlsplit(url)
    if parsed_url.netloc == '':
        # Leave relative paths alone
        return url

    url = urlparse.urlunsplit((parsed_url[0], os.environ['HTTP_HOST'], parsed_url[2], parsed_url[3], parsed_url[4]))
    return url

