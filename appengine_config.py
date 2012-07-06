#########################################
# Remote_API Authentication configuration.
#
# See google/appengine/ext/remote_api/handler.py for more information.
# For datastore_admin datastore copy, you should set the source appid
# value.  'HTTP_X_APPENGINE_INBOUND_APPID', ['trusted source appid here']
#
remoteapi_CUSTOM_ENVIRONMENT_AUTHENTICATION = (
    'HTTP_X_APPENGINE_INBOUND_APPID', ['khanexercises'])

# Increase the number of stack frames appstats is willing to capture when
# tracking the source of an RPC. Makes for easier stack tracing. See
# http://code.google.com/p/appengine-ndb-experiment/issues/detail?id=29
appstats_MAX_STACK = 15
