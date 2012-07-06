"""Utilities for end-to-end tests on handlers.

end-to-end tests are tests that send a url to a running server and get
a response back, and check that response to make sure it is 'correct'.

If you wish to write such tests, they should be in a file all their
own, perhaps named <file>_endtoend_test.py, and that file should start with:
   from testutil import handler_test_utils
   def setUpModule():
       handler_test_utils.start_dev_appserver()
   def tearDownModule():
       handler_test_utils.stop_dev_appserver()

TODO(csilvers): figure out if we can share this among many end-to-end
tests.  Maybe have each test that needs it advertise that fact, so it
will start up if necessary, and then somehow tell the test-runner to
call stop_dev_appserver() at test-end time.

TODO(csilvers): figure out how to reset the datastore between tests,
so there are no side-effects.

Note that these end-to-end tests are quite slow, since it's not a fast
operation to create a dev_appserver instance!

dev_appserver.py must be on your path.  The tests you run here must be
run via tools/runtests.py, so the appengine path can be set up
correctly.

Also note that the dev_appserver instance, by default, is created in a
'sandbox' with no datastore contents.
TODO(csilvers): create some 'fake' data that can be used for testing.

Useful variables:
   appserver_url: url to access the running dev_appserver instance,
      e.g. 'http://localhost:8080', or None if it's not running
   tmpdir: the directory where the dev-appserver is running from,
      also where its data files are stored
   pid: the pid the dev-appserver is running on, or None if it's not
      running
"""

import os
import shutil
import socket
import subprocess
import tempfile
import time

from testutil import rootdir

appserver_url = None
tmpdir = None
pid = None


def dev_appserver_logfile_name():
    """Where we log the dev_appserver output; None if no server is running."""
    if not tmpdir:
        return None
    return os.path.join(tmpdir, 'dev_appserver.log')


def create_sandbox(db=None):
    """'Copy' files from the current project directory to a temp directory.

    This function creates a sandbox directory, and symlinks the entire
    'current' directory tree (the one in which this file is found) to
    the sandbox directory, excepting directories that hold the
    database.  This makes sure that work on the database won't change
    your current environment.

    Arguments:
       db: if not None, this file is copied into the sandbox
         datastore/ directory, and is used as the starting db for the
         test datastore.  It should be specified relative to the
         app-root of the current directory tree (the directory where
         app.yaml lives).  Note that since this file is copied, there
         are no changes made to the db file you specify.  If None, an
         empty db file is used.

    Returns:
       The root directory of the copy.  This directory will have
       app.yaml in it, but will live in /tmp or some such.
    """
    # Find the 'root' directory of the project the tests are being
    # run in.
    ka_root = rootdir.project_rootdir()

    # Create a 'sandbox' directory that symlinks to ka_root,
    # except for the 'datastore' directory (we don't want to mess
    # with your actual datastore for these tests!)
    tmpdir = tempfile.mkdtemp()
    for f in os.listdir(ka_root):
        if 'datastore' not in f:
            os.symlink(os.path.join(ka_root, f),
                       os.path.join(tmpdir, f))
    os.mkdir(os.path.join(tmpdir, 'datastore'))
    if db:
        shutil.copy(os.path.join(ka_root, db),
                    os.path.join(tmpdir, 'datastore', 'test.sqlite'))
    return tmpdir


def start_dev_appserver(db=None, persist_db_changes=False):
    """Start up a dev-appserver instance on an unused port, return its url.

    This function creates a sandbox directory, and symlinks the entire
    'current' directory tree (the one in which this file is found) to
    the sandbox directory, excepting directories that hold the
    database.  This makes sure that work on the dev_appserver won't
    change your current environment.

    It starts looking on port 9000 for a free port, and will check
    10000 ports, so it should be able to start up no matter what.

    This function sets the module-global variables appserver_url,
    tmpdir, and pid.  Applications are free to examine these.  They
    are None if a dev_appserver instance isn't currently running.

    Arguments:
       db: if not None, this file will be used as the starting db for the
         datastore.  It should be specified relative to the app-root of the
         current directory tree (the directory where app.yaml lives). If None,
         an empty db file is used.

       persist_db_changes: if db is not None and persist_db_changes is True,
         the database is symlinked into the sandbox instead of copied. This
         will result in changes to the database mutating the specified db file.
         Ignored if db is None.
    """
    global appserver_url, tmpdir, pid

    ka_root = rootdir.project_rootdir()

    tmpdir = create_sandbox(db)

    sandbox_db_path = os.path.join(tmpdir, 'datastore', 'test.sqlite')

    if persist_db_changes:
        # Symlink the db rather than copying it, so that changes get made to
        # the "master" copy.
        os.unlink(sandbox_db_path)
        os.symlink(os.path.join(ka_root, db), sandbox_db_path)

    # Find an unused port to run the appserver on.  There's a small
    # race condition here, but we can hope for the best.  Too bad
    # dev_appserver doesn't allow input to be port=0!
    for port in xrange(9000, 19000):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        try:
            sock.connect(('', port))
            del sock   # reclaim the socket
        except socket.error:   # means nothing is running on that socket!
            dev_appserver_port = port
            break
    else:     # for/else: if we got here, we never found a good port
        raise IOError('Could not find an unused port in range 9000-19000')

    # Start dev_appserver
    args = ['dev_appserver.py',
            '-p%s' % dev_appserver_port,
            '--use_sqlite',
            '--high_replication',
            '--address=0.0.0.0',
            '--skip_sdk_update_check',
            ('--datastore_path=%s' % sandbox_db_path),
            ('--blobstore_path=%s'
             % os.path.join(tmpdir, 'datastore/blobs')),
            tmpdir]
    # Its output is noisy, but useful, so store it in tmpdir.  Third
    # arg to open() uses line-buffering so the output is available.
    dev_appserver_file = dev_appserver_logfile_name()
    dev_appserver_output = open(dev_appserver_file, 'w', 1)
    print 'NOTE: Starting dev_appserver.py; output in %s' % dev_appserver_file

    # Run the tests with USE_SCREEN to spawn the API server in a screen
    # to make it interactive (useful for pdb)
    #
    # e.g.
    # USE_SCREEN=1 python tools/runtests.py --max-size=large api/labs
    #
    # This works especially well if you're already in a screen session, since
    # it will just open a new screen window in your pre-existing sesssion
    if os.environ.get('USE_SCREEN'):
        args = ['/usr/bin/screen'] + args

    pid = subprocess.Popen(args,
                           stdout=dev_appserver_output,
                           stderr=subprocess.STDOUT).pid

    # Wait for the server to start up
    time.sleep(1)          # it *definitely* takes at least a second
    connect_seconds = 60   # wait for 60 seconds, until we give up
    for _ in xrange(connect_seconds * 5):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        try:
            sock.connect(('', dev_appserver_port))
            break
        except socket.error:
            del sock   # reclaim the socket
            time.sleep(0.2)
    else:    # for/else: we get here if we never hit the 'break' above
        raise IOError('Unable to connect to localhost:%s even after %s seconds'
                      % (dev_appserver_port, connect_seconds))

    # Set the useful variables for subclasses to use
    global appserver_url
    appserver_url = 'http://localhost:%d' % dev_appserver_port

    return appserver_url


def stop_dev_appserver(delete_tmpdir=True):
    global appserver_url, tmpdir, pid

    # Try very hard to kill the dev_appserver process.
    if pid:
        try:
            os.kill(pid, 15)
            time.sleep(1)
            os.kill(pid, 15)
            time.sleep(1)
            os.kill(pid, 9)
        except OSError:   # Probably 'no such process': the kill succeeded!
            pass
        pid = None

    # Now delete the tmpdir we made.
    if delete_tmpdir and tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)
        tmpdir = None

    # We're done tearing down!
    appserver_url = None
