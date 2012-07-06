#!/usr/bin/env python
import os
import sys

gae_path = '/usr/local/google_appengine'

current_path = os.path.abspath(os.path.dirname(__file__))
tests_path = os.path.join(current_path, 'tests')
test_app_path = os.path.join(current_path, 'tests', 'app')
agar_path = os.path.join(current_path, 'agar')
agar_lib_path = os.path.join(current_path, 'lib')

sys.path[0:0] = [
    current_path,
    tests_path,
    test_app_path,
    gae_path,
    agar_path,
    agar_lib_path,
    # SDK libs.
    os.path.join(gae_path, 'lib', 'django_0_96'),
    os.path.join(gae_path, 'lib', 'yaml', 'lib'),
    os.path.join(gae_path, 'lib', 'protorpc'),
    os.path.join(gae_path, 'lib', 'simplejson'),
    os.path.join(gae_path, 'lib', 'fancy_urllib'),
    os.path.join(gae_path, 'lib', 'antlr3'),
    os.path.join(gae_path, 'lib', 'whoosh'),
    os.path.join(gae_path, 'lib', 'WebOb'),
    os.path.join(gae_path, 'lib', 'ipaddr'),
    os.path.join(gae_path, 'lib', 'webapp2'),
]

import unittest2

import logging
import tempfile

from google.appengine.api import yaml_errors
from google.appengine.tools import dev_appserver
from google.appengine.tools import dev_appserver_main


__unittest = True
from unittest2.main import main_


config = matcher = None

try:
    config, matcher, from_cache = dev_appserver.LoadAppConfig("tests/app", {})
except yaml_errors.EventListenerError, e:
    logging.error('Fatal error when loading application configuration:\n' + str(e))
except dev_appserver.InvalidAppConfigError, e:
    logging.error('Application configuration file invalid:\n%s', e)

#Configure our dev_appserver setup args
args = dev_appserver_main.DEFAULT_ARGS.copy()
args[dev_appserver_main.ARG_CLEAR_DATASTORE] = True
args[dev_appserver_main.ARG_BLOBSTORE_PATH] = os.path.join(
        tempfile.gettempdir(), 'dev_appserver.test.blobstore')
args[dev_appserver_main.ARG_DATASTORE_PATH] = os.path.join(
        tempfile.gettempdir(), 'dev_appserver.test.datastore')
args[dev_appserver_main.ARG_PROSPECTIVE_SEARCH_PATH] = os.path.join(
        tempfile.gettempdir(), 'dev_appserver.test.matcher')
args[dev_appserver_main.ARG_HISTORY_PATH] = os.path.join(
        tempfile.gettempdir(), 'dev_appserver.test.datastore.history')

dev_appserver.SetupStubs(config.application, **args)


if __name__ == "__main__":
    sys.argv = ['unit2', 'discover', '--start-directory', 'tests']
    main_()

