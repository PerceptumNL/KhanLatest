"""Finds the root of the project-tree where the tests are currently being run.

Basically, it finds the directory above this file that has app.yaml in it.
"""

import os


def project_rootdir():
    appengine_root = os.path.dirname(__file__)
    while appengine_root != os.path.dirname(appengine_root):  # we're not at /
        if os.path.exists(os.path.join(appengine_root, 'app.yaml')):
            return appengine_root
        appengine_root = os.path.dirname(appengine_root)
    raise IOError('Unable to find app.yaml above cwd: %s'
                  % os.path.dirname(__file__))
