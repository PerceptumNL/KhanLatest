import logging
import os

from google.appengine.ext import db

import auth.passwords as passwords
import backup_model
import transaction_util


class Credential(db.Model):
    """ An abstraction around a password for a given user.

    All Credential instances must have a UserData object as an ancestor to show
    association, and does not store actual username / email information itself.
    """

    hashed_pass = db.StringProperty(indexed=False)
    salt = db.StringProperty(indexed=False)

    @staticmethod
    def make_for_user(user_data, raw_password):
        salt = os.urandom(8).encode('hex')
        return Credential(
                parent=user_data,
                hashed_pass=passwords.hash_password(raw_password, salt),
                salt=salt)

    @staticmethod
    def retrieve_for_user(user_data):
        return Credential.all().ancestor(user_data).get()

    def validate_password(self, raw_password):
        # TODO(benkomalo): shortcut this to check if raw_password isn't
        # even a valid password.
        return passwords.hash_password(
                raw_password, self.salt) == self.hashed_pass


class CredentialedUser(backup_model.BackupModel):
    # Randomly generated string representing a "credential version". This
    # is used to mint auth tokens and authenticate the user. A new value is
    # re-generated when the user changes his/her password, and all tokens
    # get invalidated
    credential_version = db.StringProperty(indexed=False)

    _serialize_blacklist = ["credential_version", "backup_timestamp"]

    def set_password(self, raw_password):
        """ Updates the password for this user and invalidates previous ones.

        This operation will update this UserData object as well, so any
        outstanding changes on it will be persisted.

        Authentication tokens distributed via auth/tokens.py will also be
        invalidated as a result of this operation (e.g. the user's auth cookie)

        """
        new_cred_version = os.urandom(16).encode('hex')

        def txn():
            c = Credential.retrieve_for_user(self)
            if c is not None:
                c.delete()
            new_cred = Credential.make_for_user(self, raw_password)
            self.credential_version = new_cred_version
            db.put([new_cred, self])
            
        # The Remote API doesn't support queries inside transactions
        transaction_util.ensure_in_transaction(txn)

    def validate_password(self, raw_password):
        """ Tests the specified password for this user.

        Does not do throttling if the attempt fails - this is expected
        to be done in higher layers.
        """
        if not self.credential_version:
            # Haven't ever set a password
            return False

        c = Credential.retrieve_for_user(self)
        if c is None:
            logging.error("Can't retrieve password info for user %s" %
                          self.key())
            return False

        return c.validate_password(raw_password)

    def set_password_from_user(self, other_user):
        """ Sets the password for this user to be the same as that of
        another user.

        To be used sparingly! This should only be done for user migrations
        and other admin-related items.

        """

        def txn():
            credential = Credential.retrieve_for_user(other_user)
            cred_copy = None
            if credential:
                cred_copy = Credential(parent=self)
                cred_copy.hashed_pass = credential.hashed_pass
                cred_copy.salt = credential.salt
            self.credential_version = other_user.credential_version
            if cred_copy:
                db.put([cred_copy, self])
            else:
                db.put(self)

        transaction_util.ensure_in_transaction(txn, xg_on=True)

    def delete(self):
        # Override delete so that we can also delete associated Credential
        # models in the same transaction.
        def txn():
            credential = Credential.retrieve_for_user(self)
            if credential:
                credential.delete()

            # Delegate to the base class implementation of db.Model.delete
            # to do the actual deletion of this class.
            super(CredentialedUser, self).delete()

        transaction_util.ensure_in_transaction(txn)


class UserNonce(db.Model):
    """ A user-specific nonce that can be used for various security related
    purposes.

    Nonce values are "typed" so that clients may make multiple nonce values
    for a user and differentiate them from each other. Only one nonce can be
    made per type per user. Nonce values are not guaranteed to be unique
    across users.

    """

    value = db.StringProperty(indexed=False)

    @staticmethod
    def make_for(user_data, type="default"):
        """ Creates a new nonce value for the given user and type.

        This will override any existing nonce values for the same user/type.

        """

        nonce = UserNonce(parent=user_data,
                          key_name=type,
                          value=os.urandom(8).encode("hex"))
        nonce.put()
        return nonce

    @staticmethod
    def get_for(user_data, type="default"):
        return UserNonce.get_by_key_name(type, parent=user_data)
