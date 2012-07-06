#!/usr/bin/env python
"""Run an interactive shell in the App Engine environment.

If IPython is installed, will use that as a REPL, otherwise will fall back to
regular python REPL.
"""

import os
import argparse

import appengine_tool_setup

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdk', dest='sdk', metavar='SDK_PATH',
                      help='path to the App Engine SDK')
    parser.add_argument('--datastore_path', dest='datastore_path',
                      metavar='DATASTORE_PATH',
                      default='datastore/current.sqlite',
                      help='path to the sqlite datastore. '
                           'Uses %(default)s by default.')

    args = parser.parse_args()

    # SERVER_SOFTWARE is used by dev_appserver to set various things
    # It's also used in transaction_util.ensure_in_transaction to determine
    # whether we're interfacing with the remote API.
    #
    # Without this, anything using ensure_in_transaction won't work properly
    #
    # This has to be done before fix_sys_path, because fix_sys_path sets its
    # own SERVER_SOFTWARE if one isn't already defined.
    os.environ['SERVER_SOFTWARE'] = 'Development (devshell remote-api)/1.0'

    appengine_tool_setup.fix_sys_path(args.sdk)

    # These have to be imported after fix_sys_path is called
    from google.appengine.ext.remote_api import remote_api_stub
    from testutil import handler_test_utils

    handler_test_utils.start_dev_appserver(
        db=args.datastore_path,
        persist_db_changes=True)

    remote_api_stub.ConfigureRemoteApi(
        None,
        '/_ah/remote_api',
        auth_func=(lambda: ('test', 'test')),   # username/password
        servername=handler_test_utils.appserver_url[len('http://'):])

    try:
        import IPython
        IPython.embed()
    except ImportError:
        print "=" * 78
        print "Looks like you don't have IPython installed."
        print "If you'd like to use IPython instead of the regular python REPL"
        print "pip install IPython"
        print "=" * 78
        import code
        code.interact(local=locals())
    finally:
        handler_test_utils.stop_dev_appserver()
