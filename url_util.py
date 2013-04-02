import os
import re
import urllib
import urlparse

from app import App
from google.appengine.api.app_identity import get_default_version_hostname


def create_login_url(dest_url):
    return "/login?continue=%s" % urllib.quote_plus(dest_url)


def create_mobile_oauth_login_url(dest_url):
    return "/login/mobileoauth?continue=%s" % urllib.quote_plus(dest_url)


def create_post_login_url(dest_url):
    if dest_url.startswith("/postlogin"):
        return dest_url
    else:
        if (dest_url == '/' or
                dest_url == absolute_url('/')):
            return "/postlogin"
        else:
            return "/postlogin?continue=%s" % urllib.quote_plus(dest_url)


def create_logout_url(dest_url):
    # If the user is viewing a profile page (their own or someone else's)
    # or a coaching page (class_profile or students), go to the home page
    # on logout.
    #
    # Even if the profile page is visible publicly, it doesn't seem like
    # staying there is a particular win. And being kicked to the login
    # screen for the coach pages seems a little awkward.
    #
    if re.search(r'/profile\b|/class_profile\b|/students\b', dest_url):
        return "/logout"
    else:
        return "/logout?continue=%s" % urllib.quote_plus(dest_url)


def _get_url_parts(url):
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
    if not netloc:
        # No server_name - must be a relative url.
        if 'HTTP_HOST' in os.environ:
            netloc = os.environ['HTTP_HOST']  # includes port string
        else:
            server_name = os.environ['SERVER_NAME']

            # Note that this is always a string
            port = os.environ['SERVER_PORT']
            if port == "80":
                netloc = server_name
            else:
                netloc = "%s:%s" % (server_name, port)
    return (scheme, netloc, path, query, fragment)


def secure_url(url):
    """ Given a Khan Academy URL (i.e. not to an external site), returns an
    absolute https version of the URL, if possible.

    Abstracts away limitations of https, such as non-support in vanity domains
    and dev servers.

    """

    if url.startswith("https://"):
        return url

    if App.is_dev_server:
        # Dev servers can't handle https.
        return url

    _, netloc, path, query, fragment = _get_url_parts(url)

    if netloc.lower().endswith(".khanacademie.nl"):
        # Vanity domains can't handle https - but all the ones we own
        # are simple CNAMEs to the default app engine instance.
        # http://code.google.com/p/googleappengine/issues/detail?id=792
        netloc = "%s.appspot.com" % get_default_version_hostname()

    return urlparse.urlunsplit(("https", netloc, path, query, fragment))


def insecure_url(url):
    """ Given a Khan Academy URL (i.e. not to an external site), returns an
    absolute http version of the URL.

    In dev servers, this always just returns the same URL since dev servers
    never convert to/from secure URL's.

    """

    if url.startswith("http://"):
        return url

    if App.is_dev_server:
        # Dev servers can't handle https/http conversion
        return url

    _, netloc, path, query, fragment = _get_url_parts(url)

    if netloc.lower() == "%s" % get_default_version_hostname():
        # https://khan-academy.appspot.com is the HTTPS equivalent of the
        # default appengine instance
        netloc = "www.khanacademie.nl"

    return urlparse.urlunsplit(("http", netloc, path, query, fragment))


def opengraph_url(relative_url):
    """ Returns a public URL that can be accessed by Facebook's crawlers.

    This URL can be used instead of host-dependent URLs for defining Open
    Graph objects (badges, videos). This simplifies local testing of Open
    Graph actions, as this URL will point to already-deployed pages that
    Facebook can crawl and which are associated with our Facebook app.

    Examples for relative_url == "/badges/getting-started":
        Host beta.wild.khanacademy.org =>
            http://beta.wild.khanacademy.org/badges/getting-started
        Host 127.0.0.1 =>
            http://www.khanacademy.org/badges/getting-started
        Host khan-academy.appspot.com =>
            http://www.khanacademy.org/badges/getting-started

    """
    host = os.environ['HTTP_HOST']
    if App.is_dev_server or not host.endswith(".khanacademie.nl"):
        return absolute_url(relative_url, host="www.khanacademie.nl")
    else:
        return absolute_url(relative_url)


def absolute_url(relative_url, host=None):
    host = host or os.environ['HTTP_HOST']
    return 'http://%s%s' % (host, relative_url)


def static_url(relative_url):
    host = os.environ['HTTP_HOST'].lower()
    if not get_default_version_hostname() or not host.endswith(".khanacademie.nl"):
        return relative_url
    else:
        # when using a wildcard url to serve a nondefault version, ensure
        # static urls point at the correct nondefault version
        match = re.match(r"([\w-]+)\.wild\.khanacademie\.nl", host)
        if match:
            version = match.group(1)
            return ("http://%s.%s%s" %
                    (version, get_default_version_hostname(), relative_url))
        else:
            return "http://%s.%s" % (get_default_version_hostname(), relative_url)


def iri_to_uri(iri):
    """Convert an Internationalized Resource Identifier (IRI) for use in a URL.

    This function follows the algorithm from section 3.1 of RFC 3987 and is
    idempotent, iri_to_uri(iri_to_uri(s)) == iri_to_uri(s)

    Args:
        iri: A unicode string.

    Returns:
        An ASCII string with the encoded result. If iri is not unicode it
        is returned unmodified.
    """
    # Implementation heavily inspired by django.utils.encoding.iri_to_uri()
    # for its simplicity. We make the further assumption that the incoming
    # argument is a unicode string or is ignored.
    #
    # See also werkzeug.urls.iri_to_uri() for a more complete handling of
    # internationalized domain names.
    if isinstance(iri, unicode):
        byte_string = iri.encode("utf-8")
        return urllib.quote(byte_string, safe="/#%[]=:;$&()+,!?*@'~")
    return iri


def is_khanacademy_url(url):
    """ Determines whether or not the specified URL points to a Khan Academy
    property.

    Relative URLs are considered safe and owned by Khan Academy.
    """

    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
    # Check all absolute URLs
    if (netloc and
            not netloc.endswith(".khanacademie.nl") and
            not netloc.endswith(".%s" % get_default_version_hostname()) and
            not netloc == "%s" % get_default_version_hostname()):
        return False

    # Relative URL's are considered to be a Khan Academy URL.
    return True


def build_params(dict):
    """ Builds a query string given a dictionary of key/value pairs for the
    query parameters.

    Values will be automatically encoded. If a value is None, it is ignored.

    """

    return "&".join("%s=%s" % (k, urllib.quote_plus(v))
                    for k, v in dict.iteritems()
                    if v)
