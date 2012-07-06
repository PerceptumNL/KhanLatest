from gandalf.cache import flush_instance_cache


class GandalfWSGIMiddleware(object):

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):

        # Make sure instance-cached values are cleared at the start of request
        flush_instance_cache()

        result = self.app(environ, start_response)
        for value in result:
            yield value
