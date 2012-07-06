"""Utilities for running things inside of the App Engine environment."""

import os
import sys


def project_rootdir():
    appengine_root = os.path.dirname(__file__)
    while appengine_root != os.path.dirname(appengine_root):  # we're not at /
        if os.path.exists(os.path.join(appengine_root, 'app.yaml')):
            return appengine_root
        appengine_root = os.path.dirname(appengine_root)
    raise IOError('Unable to find app.yaml above cwd: %s'
                  % os.path.dirname(__file__))


def _discover_sdk_path():
    """Return directory from $PATH where the Google Appengine DSK lives."""
    # adapted from {http://code.google.com/p/bcannon/source/browse/
    # sites/py3ksupport-hrd/run_tests.py}

    # Poor-man's `which` command.
    for path in os.environ['PATH'].split(':'):
        if os.path.isdir(path) and 'dev_appserver.py' in os.listdir(path):
            break
    else:
        raise RuntimeError("couldn't find appcfg.py on $PATH")

    # Find out where App Engine lives so we can import it.
    app_engine_path = os.path.join(os.path.dirname(path), 'google_appengine')
    if not os.path.isdir(app_engine_path):
        raise RuntimeError('%s is not a directory' % app_engine_path)
    return app_engine_path


def fix_sys_path(appengine_sdk_dir=None):
    """Update sys.path for appengine and khan academy imports, also envvars."""
    if 'SERVER_SOFTWARE' not in os.environ:
        os.environ['SERVER_SOFTWARE'] = 'Development'
    if 'CURRENT_VERSION' not in os.environ:
        os.environ['CURRENT_VERSION'] = '764.1'

    if not appengine_sdk_dir:
        appengine_sdk_dir = _discover_sdk_path()
    sys.path.append(appengine_sdk_dir)

    # This has to be done after the path has been fixed because dev_appserver
    # is in the AppEngine SDK dirctory
    import dev_appserver

    dev_appserver.fix_sys_path()

    sys.path.insert(0, project_rootdir())
