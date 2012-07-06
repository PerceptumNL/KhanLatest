import datetime
import urllib

from google.appengine.ext import db

from consts import KEY_SIZE, SECRET_SIZE, CONSUMER_KEY_SIZE, CONSUMER_STATES,\
                   PENDING, ACCEPTED, VERIFIER_SIZE, MAX_URL_LENGTH,\
                   TIMESTAMP_THRESHOLD_SECONDS

def generate_random(length=10, allowed_chars='abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'):
    "Generates a random password with the given length and given allowed_chars"
    # Note that default value of allowed_chars does not have "I" or letters
    # that look like it -- just to avoid confusion.
    from random import choice
    return ''.join([choice(allowed_chars) for i in range(length)])

class Nonce(db.Model):
    token_key = db.StringProperty()
    consumer_key = db.StringProperty()
    key_ = db.StringProperty()
    created = db.DateTimeProperty(
            # Explicitly disable auto_now_add -- it overrides the default
            auto_now_add=False,
            # Default is the date this property was added
            default=datetime.datetime(2012, 05, 23))

    @property
    def is_expired(self):
        """ True if this Nonce is expired and ignorable.
        
        If anybody sends us a Nonce that matches a previous Nonce sent over
        a couple days ago, the duplicate is not a candidate for a replay attack
        after that length of time, and we can let it succeed.
        """

        # Nonces remain valid exactly twice as long as each request's timestamp
        # parameter. This means nonces will still be active to protect us from
        # replay attacks within the TIMESTAMP_THRESHOLD_SECONDS boundary, and
        # after nonces expire, timestamp verification will deny any old replay
        # attacks.
        expiration_seconds = TIMESTAMP_THRESHOLD_SECONDS * 2

        return ((datetime.datetime.now() - self.created) > 
                datetime.timedelta(seconds=expiration_seconds))

    def __unicode__(self):
        return u"Nonce %s for %s" % (self.key, self.consumer_key)

#need to determine what this is for
class Resource(db.Model):
    name = db.StringProperty( )
    url = db.TextProperty()
    is_readonly = db.BooleanProperty(default=True)

    def __unicode__(self):
        return u"Resource %s with url %s" % (self.name, self.url)

class Consumer(db.Model):
    name = db.StringProperty()
    description = db.TextProperty()
    website = db.StringProperty()
    phone = db.StringProperty()
    company = db.StringProperty()

    # True if we've given this consumer the right to make
    # protected API calls, such as those that update user history.
    anointed = db.BooleanProperty(default = False)

    key_ = db.StringProperty()
    secret = db.StringProperty()

    status = db.IntegerProperty(choices=[state[0] for state in CONSUMER_STATES], default=PENDING)
    user = db.UserProperty(required=False)

    def __unicode__(self):
        return u"Consumer %s with key %s" % (self.name, self.key)

    def generate_random_codes(self):

        key_ = generate_random(length=KEY_SIZE)
        secret = generate_random(length=SECRET_SIZE)

        while Consumer.all().filter('key_ =', key_).filter('secret =', secret).count():
            key_ = generate_random(length=KEY_SIZE)
            secret = generate_random(length=SECRET_SIZE)

        self.key_ = key_
        self.secret = secret
        self.put()
        db.get(self.key())  # force-commit (needed for the high-repl datastore)

class Token(db.Model):
    REQUEST = 1
    ACCESS = 2
    TOKEN_TYPES = (REQUEST, ACCESS)

    key_ = db.StringProperty()
    secret = db.StringProperty()
    token_type = db.IntegerProperty(choices=TOKEN_TYPES)
    timestamp = db.IntegerProperty()
    is_approved = db.BooleanProperty(default=False)

    user = db.UserProperty(required=False)
    consumer = db.ReferenceProperty(Consumer, collection_name="tokens")
    resource = db.ReferenceProperty(Resource, collection_name="resources")

    ## OAuth 1.0a stuff
    verifier = db.StringProperty()
    callback = db.StringProperty(required=False)
    callback_confirmed = db.BooleanProperty(default=False)


    def __unicode__(self):
        return u"%s Token %s for %s" % (self.get_token_type_display(), self.key_, self.consumer)

    def to_string(self, only_key=False):
        token_dict = {
            'oauth_token': self.key_,
            'oauth_token_secret': self.secret
        }

        if self.callback_confirmed:
            token_dict.update({'oauth_callback_confirmed': 'true'})

        if self.verifier:
            token_dict.update({ 'oauth_verifier': self.verifier })

        if only_key:
            del token_dict['oauth_token_secret']
            if token_dict.has_key('oauth_callback_confirmed'):
                del token_dict['oauth_callback_confirmed']

        return urllib.urlencode(token_dict)


    def generate_random_codes(self):
        key = generate_random(length=KEY_SIZE)
        secret = generate_random(length=SECRET_SIZE)

        while Token.all().filter('key_ =',key).count():
            key = generate_random(length=KEY_SIZE)
            secret = generate_random(length=SECRET_SIZE)

        self.key_ = key
        self.secret = secret
        self.put()
        db.get(self.key())  # force-commit (needed for the high-repl datastore)

    def get_callback_url(self):
        """
        OAuth 1.0a, append the oauth_verifier.
        """
        if self.callback and self.verifier:
            parts = urlparse.urlparse(self.callback)
            scheme, netloc, path, params, query, fragment = parts[:6]
            if query:
                query = '%s&oauth_verifier=%s' % (query, self.verifier)
            else:
                query = 'oauth_verifier=%s' % self.verifier
            return urlparse.urlunparse((scheme, netloc, path, params,
                query, fragment))
        return self.callback

    def create_token(cls, consumer, token_type, timestamp, resource,
            user=None, callback=None, callback_confirmed=False):
        """Shortcut to create a token with random key/secret."""
        token = Token(
            consumer=consumer,
            token_type=token_type,
            timestamp=timestamp,
            resource=resource,
            user=user,
            callback=callback,
            callback_confirmed=callback_confirmed)
        token.generate_random_codes()
        token.put()
        db.get(token.key())  # force-commit, needed for the high-repl datastore

        return token
    create_token = classmethod(create_token)


#admin.site.register(Token)
