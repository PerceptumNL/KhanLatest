from __future__ import absolute_import

import base64
import datetime
import hashlib
import hmac
import logging

from app import App
from auth.models import UserNonce


_FORMAT = "%Y%j%H%M%S"


def _to_timestamp(dt):
    return "%s.%s" % (dt.strftime(_FORMAT), dt.microsecond)


def _from_timestamp(s):
    if not s:
        return None
    main, ms = s.split('.')
    try:
        result = datetime.datetime.strptime(main, _FORMAT)
        result = result.replace(microsecond=int(ms))
    except Exception:
        return None
    return result


class TokenError(Exception):
    """Indicates an error when minting tokens of any type."""
    pass


class BaseSecureToken(object):
    """A base secure token used to identify and authenticate a user.

    Note that instances may be created that are invalid (it may be expired
    or an external revocation process may have invalidated it).
    Clients must check is_valid() to ensure the contents of the token are
    valid.

    Different token types may be created by extending and having subclasses
    override the method to generate the token signature.
    """

    def __init__(self, user_id, timestamp, signature):
        self.user_id = user_id
        self.timestamp = timestamp
        self.signature = signature
        self._value_internal = None

    @staticmethod
    def sign_payload(user_data, timestamp, *payload_args):
        """Sign a given payload for use in a secure token.

        Arguments:
            user_data: The user object that this secure token should belong
                to (must have a non-empty user_id property)
            timestamp: The timestamp for the payload creation (always
                required in a token so that it can be expired)
            payload_args: Additional values to be used in the payload.
                Must specify at least one value. IMPORTANT - these values
                cannot contain newline characters!

        Returns:
            A string representing a secure signature from the given payload.

        Raises:
            TokenError: Raised if the payload arguments are invalid.
        """

        if not payload_args:
            raise TokenError("Need a payload to sign for token signature")
        if any("\n" in arg for arg in payload_args):
            raise TokenError("Can't have newlines in token values")

        payload = "\n".join([user_data.user_id] +
                            list(payload_args) +
                            [timestamp])
        secret = App.token_recipe_key
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()

    @staticmethod
    def make_token_signature(user_data, timestamp):
        """Subclasses should override this so to return a unique signature
        a user given a particular token type.

        This may alter state for the user_data, so subclasses
        may define behavior such that subsequent calls to
        make_token_signature may return varying results. To ensure a signature
        is valid, override validate_signature().
        """
        raise Exception("Not implemented in base class")

    @classmethod
    def for_user(cls, user_data, clock=None):
        """Generate a secure token for a user."""

        timestamp = _to_timestamp((clock or datetime.datetime).utcnow())
        signature = cls.make_token_signature(user_data, timestamp)
        return cls(user_data.user_id, timestamp, signature)

    @classmethod
    def for_value(cls, token_value):
        """Parse a string intended to be an secure token value.

        Returns None if the string is invalid, and an instance of the token
        otherwise. Note that this essentially only checks well-formedness,
        and the token itself may be expired or invalid so clients must call
        is_valid or equivalent to verify.
        """

        try:
            contents = base64.b64decode(token_value)
        except TypeError:
            # Not proper base64 encoded value.
            logging.info("Tried to decode auth token that isn't " +
                         "base64 encoded")
            return None

        parts = contents.split("\n")
        if len(parts) != 3:
            # Wrong number of parts / malformed.
            logging.info("Tried to decode malformed auth token")
            return None
        user_id, timestamp, signature = parts
        return cls(user_id, timestamp, signature)

    @classmethod
    def get_user_for_value(cls, token_value, id_to_model, clock=None):
        """Retrieve a user_data object given a token_value, if it is valid.
        Returns None if the token value is invalid.

        This attempts to be somewhat model-agnostic and requires clients
        to specify the getter to retrieve the model given a user_id
        """

        if not token_value:
            return None

        token = cls.for_value(token_value)
        if not token:
            return None

        user_data = id_to_model(token.user_id)
        if user_data and token.is_valid(user_data, clock=clock):
            return user_data
        return None

    DEFAULT_EXPIRY = datetime.timedelta(days=14)
    DEFAULT_EXPIRY_SECONDS = DEFAULT_EXPIRY.days * 24 * 60 * 60

    def is_expired(self, time_to_expiry=DEFAULT_EXPIRY, clock=None):
        """Determine whether or not the specified token is expired.

        Note that tokens encapsulate timestamp on creation, so the application
        may change the expiry lengths at any time and invalidate historical
        tokens with such changes.
        """

        dt = _from_timestamp(self.timestamp)
        now = (clock or datetime.datetime).utcnow()
        return not dt or (now - dt) > time_to_expiry

    def validate_signature_for(self, user_data):
        """Validate the signature for this token against the expected
        value for a token for the specified user."""

        # The default implementation is to just re-build the signature
        # and check equivalence.
        expected = self.make_token_signature(user_data, self.timestamp)
        return expected == self.signature

    def is_authentic(self, user_data):
        """Determine if the token is valid for a given user.

        Users may invalidate all existing auth tokens by changing his/her
        password.
        """

        if self.user_id != user_data.user_id:
            return False

        return self.validate_signature_for(user_data)

    def is_valid(self, user_data,
                 time_to_expiry=DEFAULT_EXPIRY, clock=None):
        return (not self.is_expired(time_to_expiry, clock) and
                self.is_authentic(user_data))

    def __str__(self):
        return self.value

    def __unicode__(self):
        return self.value

    @property
    def value(self):
        if self._value_internal is None:
            self._value_internal = base64.b64encode(
                    "\n".join([self.user_id,
                               self.timestamp,
                               self.signature]))
        return self._value_internal


class AuthToken(BaseSecureToken):
    """A secure token used to authenticate a user that has a password set.

    Note that instances may be created that are invalid (e.g. it may be expired
    or the user may have changed her password). Clients must check
    is_valid() to ensure the contents of the token are valid.
    """

    @staticmethod
    def make_token_signature(user_data, timestamp):
        """Generate a signature to be embedded inside of an auth token.
        This signature serves two goals. The first is to validate the rest of
        the contents of the token, much like a simple hash. The second is to
        also encode a unique user-specific string that can be invalidated if
        all existing tokens of the given type need to be invalidated.
        """

        return BaseSecureToken.sign_payload(user_data,
                                            timestamp,
                                            user_data.credential_version)


class TransferAuthToken(BaseSecureToken):
    """A short-lived authentication token that can be minted for signed
    in users to transfer identities across domains.

    This is useful since Khan Academy domains on HTTP and HTTPS differ, and
    iframes that need to be in HTTPS may not be able to read the normal auth
    cookies on HTTP. For this purpose, TransferAuthToken's are used to
    temporarily authenticate iframes for users.
    """

    @staticmethod
    def make_token_signature(user_data, timestamp):
        nonce = UserNonce.make_for(user_data, "https_transfer").value
        return BaseSecureToken.sign_payload(user_data, timestamp, nonce)

    def validate_signature_for(self, user_data):
        nonce_entity = UserNonce.get_for(user_data, "https_transfer")
        if nonce_entity is None:
            return False
        nonce = nonce_entity.value
        expected = BaseSecureToken.sign_payload(user_data,
                                                self.timestamp,
                                                nonce)
        return expected == self.signature

    # Force a short expiry for these tokens.
    DEFAULT_EXPIRY = datetime.timedelta(hours=1)

    def is_expired(self, time_to_expiry=DEFAULT_EXPIRY, clock=None):
        dt = _from_timestamp(self.timestamp)
        now = (clock or datetime.datetime).utcnow()
        return not dt or (now - dt) > time_to_expiry


class PasswordResetToken(BaseSecureToken):
    """A short-lived token used to allow users to reset a password on her
    account.
    """

    @staticmethod
    def make_token_signature(user_data, timestamp):
        if not user_data.credential_version:
            raise TokenError("Can't make password reset token for "
                             "user with no password.")

        nonce = UserNonce.make_for(user_data, "pw_reset").value
        return BaseSecureToken.sign_payload(user_data,
                                            timestamp,
                                            nonce,
                                            user_data.credential_version)

    def validate_signature_for(self, user_data):
        nonce_entity = UserNonce.get_for(user_data, "pw_reset")
        if nonce_entity is None:
            return False

        nonce = nonce_entity.value
        expected = BaseSecureToken.sign_payload(user_data,
                                                self.timestamp,
                                                nonce,
                                                user_data.credential_version)
        return expected == self.signature

    # Force a short expiry for these tokens.
    DEFAULT_EXPIRY = datetime.timedelta(hours=1)

    def is_expired(self, time_to_expiry=DEFAULT_EXPIRY, clock=None):
        dt = _from_timestamp(self.timestamp)
        now = (clock or datetime.datetime).utcnow()
        return not dt or (now - dt) > time_to_expiry
