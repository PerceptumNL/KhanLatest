"""Routines to ease dealing with appengine transactions."""

import os
from google.appengine.ext import db


def ensure_in_transaction(func, *args, **kwargs):
    """ Runs the specified method in a transaction, if the current thread is
    not currently running in a transaction already.

    However, if we're running as part of the remote-api service, do
    *not* run in a transaction, since remote-api does not support
    transactions well (in particular, you can't do any queries while
    inside a transaction).  The remote-api shell marks itself in the
    SERVER_SOFTWARE environment variable; other remote-api users
    should do similarly.

    Arguments:
       func: the function to run in transcation
       *args, **kwargs: the args/kwargs to pass to func, with the
          exception of:
       xg_on: if True allow XG transactions (which are disallowed by default)
    """
    if 'xg_on' in kwargs:
        xg_on = kwargs['xg_on']
        del kwargs['xg_on']
    else:
        xg_on = None

    if db.is_in_transaction() or 'remote' in os.environ["SERVER_SOFTWARE"]:
        return func(*args, **kwargs)

    if xg_on is not None:
        options = db.create_transaction_options(xg=xg_on)
        return db.run_in_transaction_options(options, func, *args, **kwargs)
    else:
        return db.run_in_transaction(func, *args, **kwargs)
