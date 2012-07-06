"""A database entity for parents wanting to create under-13 accounts.

This collects an interest list for parents interested in creating
under-13 accounts before the feature is actually ready.
"""

from google.appengine.ext import db


class ParentSignup(db.Model):
    # The key_name stores the e-mail.
    pass
