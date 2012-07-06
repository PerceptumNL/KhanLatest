import logging


class WSGICompatHeaderMiddleware(object):
    """Report headers with non-str names or values.

    App Engine's CGI library allow headers to be unicode, but the WSGI
    library is strict and will throw exceptions for non-str headers.

    We want to use WSGI handlers because multithreading requires them
    and because the CGI layer requires a hack to be efficient. See
    http://blog.notdot.net/2011/10/Migrating-to-Python-2-7-part-1-Threadsafe
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):

        def wrapped_start_response(status, headers, exc_info=None):
            for name, value in headers:
                if type(name) != str or type(value) != str:
                    logging.warn('Non-str header (%r, %s)' %
                                 (name, type(value)))
            return start_response(status, headers, exc_info)

        result = self.app(environ, wrapped_start_response)
        for value in result:
            yield value
