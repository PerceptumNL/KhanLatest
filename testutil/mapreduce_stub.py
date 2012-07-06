"""Routines for making mapreduce calls without needing a webserver.

This file provides mocks that are needed to run mapreduces, and a
testcase one can derive from when writing tests that want to run a
mapreduce.

The basic plan is we stub out the two components of mapreduce that
cause trouble: the google appengine taskqueue (which is how mapreduce
does its scheduling), and the webserver (which is how mapreduce
communicates between mappers, reducers, and controllers).

For the first, we use the normal GAE testbed taskqueue stub.  The only
trick there is we need to give it access to our queue.yaml file.

For the second, we use webtest, which has a mock for talking http to
wsgi apps.  We then write our own mock of httplib, both the connection
and the response.  Then, when mapreduce wants to send a url, we
intercept it, figure out from the wsgi app what handler corresponds to
that url, and call the handler with fake request info.  We then
translate the response into a fake response info, and send that back
to the user.

Even with all this mocking, mapreduces take a number of seconds to
run, so all tests that use this framework should be marked with
@testsize.large.

USAGE:

Just create a TestCase that subclasses from MapreduceTestCase, rather
than from unittest.TestCase.  Your TestCase will, in its setUp(), need
to set self._rootdir to the location of the queue.yaml file for your
source tree.  It must do this *before* it calls its parent setUp().

To actually run a mapreduce in a test, do something like

   mapreduce.control.start_map(name=..., ...)
   mapreduce_stub.run_all_mapreduces(self.testbed)
"""

import httplib
import os
import time
import webtest

import third_party.mapreduce.main
import third_party.mapreduce.model

from testutil import gae_model
from testutil import testsize


class MockHTTPResponse(object):
    """It looks like an http response, but the data is from a wsgi response."""
    def __init__(self, wsgi_response):
        self._wsgi_response = wsgi_response
        self.msg = None   # TODO(csilvers): support if we ever need this
        self.version = 'HTTP/1.mock'
        self.status = self._wsgi_response.status_int
        self.reason = self._wsgi_response.status

    def read(self):
        return self._wsgi_response.body

    def getheader(self, name, default=None):
        return self._wsgi_response.headers.get(name, default)

    def close(self):
        pass


def _mock_http_connection(wsgi_app, verbose=False):
    """Return a mock httpconnection object for some urls.

    We return an object that is a proxy for httlib.HTTPConnection.  It
    supports __init__, putrequest, putheaders, endheaders, send, and
    getresponse.  (These are what taskqueue_stub.py uses.)  At
    getresponse()-time, we call the given wsgi_app with the url (from
    putrequest), headers, and payload, and return the response that
    the appropriate wsgi handler gives back.

    Arguments:
       wsgi_app: A wsgi application.  We will mock it out and pretend
          the http has happened, even though everything will just be
          local to this server.
       verbose: If true, logs information about each http request.
    """
    class MockHTTPConnection(object):
        def __init__(self, unused_hostname):
            # We mock out the wsgi_app to support our non-network
            # communication.
            self.wsgi_app = webtest.TestApp(wsgi_app)
            self.method = None
            self.url = None
            self.headers = {}
            self.payload = ''
            # we ignore the hostname -- we're a mock!
            self.verbose = verbose
            
        def putrequest(self, method, url, *args, **kwargs):
            self.method = method
            self.url = url

        def putheader(self, key, value):
            self.headers[key] = str(value)   # webob hates unicode!

        def endheaders(self):
            pass

        def send(self, payload):
            self.payload = payload

        def getresponse(self):
            if not self.url:
                raise httplib.HTTPException(
                    'No url specified for mock http request')
            if not self.method:
                raise httplib.HTTPException(
                    'No method specified for mock http request')

            if self.verbose:
                print ('%s %s (%s headers, payload of length %s)'
                       % (self.method, self.url,
                          len(self.headers), len(self.payload)))

            if self.method.lower() == 'get':
                wsgi_response = self.wsgi_app.get(self.url, self.headers)
            elif self.method.lower() == 'post':
                wsgi_response = self.wsgi_app.post(self.url, self.payload,
                                                   self.headers)
            else:
                raise httplib.HTTPException('Unsupported method %s specified'
                                            ' for mock http request'
                                            % self.method)

            # We need to convert the wsgi_response into an HTTPResponse.
            # We create a mock for that too.
            return MockHTTPResponse(wsgi_response)

    return MockHTTPConnection


class MapreduceTestCase(gae_model.GAEModelTestCase):
    @testsize.large()
    def setUp(self, **kwargs):
        """Args are passed to the parent."""
        setup_args = kwargs.copy()
        setup_args.setdefault('db_consistency_probability', 1)
        setup_args.setdefault('queue_yaml_dir', '.')   # relative to proj-root
        super(MapreduceTestCase, self).setUp(**setup_args)

        # Mapreduces want HTTP_HOST to be set.
        os.environ.setdefault('HTTP_HOST', 'localhost')

        # But we're going to ignore it and intercept all http requests.
        self.old_httpconnection = httplib.HTTPConnection
        httplib.HTTPConnection = _mock_http_connection(
            third_party.mapreduce.main.APP, verbose=False)

    def tearDown(self):
        httplib.HTTPConnection = self.old_httpconnection
        super(MapreduceTestCase, self).tearDown()


def run_all_mapreduces(testbed):
    """Return after all mapreduces are done, or raise an exception."""
    # Start the mapreduces
    testbed.get_stub('taskqueue').StartBackgroundExecution()

    seconds_to_wait = 300  # wait for 5 minutes, until we give up
    for _ in xrange(seconds_to_wait):
        time.sleep(1)
        jobs = third_party.mapreduce.model.MapreduceState.all().fetch(50)
        if not any(job.active for job in jobs):
            break
    else:
        raise RuntimeError('mapreduce jobs have not completed'
                           ' after %s seconds' % seconds_to_wait)

    testbed.get_stub('taskqueue').Shutdown()
    time.sleep(1)  # give the taskqueue thread time to notice the shutdown
