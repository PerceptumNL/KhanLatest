"""
The configuration file used by :py:mod:`agar.config` implementations and other libraries using the
`google.appengine.api.lib_config`_ configuration library. Configuration overrides go in this file.
"""

##############################################################################
# AGAR SETTINGS
##############################################################################

# Root level WSGI application modules that 'agar.url.uri_for()' will search
agar_url_APPLICATIONS = ['main', 'api']

# Configure the service validation error logging level for the validate_service decorator
# import logging
# agar_django_LOG_SERVICE_VALIDATION_ERRORS = logging.WARN

# Enable logging of raw request value of fields with validation errors for the validate_service decorator
# agar_django_LOG_SERVICE_VALIDATION_VALUES = True
