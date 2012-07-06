"""Model class used for automatic daily backups of all models.

If you would like your model to be backed up (off of App Engine),
just inherit from BackupModel.
"""

from google.appengine.ext import db


class BackupModel(db.Model):
    """Inherit from this and your model will be backed up (off AppEngine)."""
    backup_timestamp = db.DateTimeProperty(auto_now=True)
