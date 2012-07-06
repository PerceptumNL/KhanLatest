import datetime
import logging

from google.appengine.ext import db

import config
from urlparse import urlparse
from oauth_provider.oauth import OAuthError

OAUTH_BLACKLISTED_HOSTNAMES = getattr(config,'OAUTH_BLACKLISTED_HOSTNAMES',[])

import oauth

from models_oauth import Nonce, Token, Consumer, Resource, generate_random
from consts import VERIFIER_SIZE, MAX_URL_LENGTH, OUT_OF_BAND

def set_trace():
    import pdb, sys
    warningger = pdb.Pdb(stdin=sys.__stdin__, stdout=sys.__stdout__)
    warningger.set_trace(sys._getframe().f_back)

class GAEOAuthDataStore(oauth.OAuthDataStore):
    def __init__(self, oauth_request):
        self.signature = oauth_request.parameters.get('oauth_signature', None)
        self.timestamp = oauth_request.parameters.get('oauth_timestamp', None)

        if self.timestamp is not None:
            self.timestamp = int(self.timestamp)


    def lookup_consumer(self, key):
        consumers = Consumer.all().filter("key_ =",key).fetch(1000)
        if len(consumers) == 1:
            self.consumer = consumers[0]
            return self.consumer
        elif len(consumers) == 0:
            return None
        else:
            raise Exception('More than one consumer matches Consumer key "%s"'%key)

    def lookup_token(self, token_type, token):
        if token_type == 'request':
            token_type = Token.REQUEST
        elif token_type == 'access':
            token_type = Token.ACCESS

        request_tokens = (Token.all().
                filter('key_ =', token).
                filter('token_type =', token_type).
                fetch(1000))

        if len(request_tokens) == 1:
            self.request_token = request_tokens[0]
            return self.request_token
        elif len(request_tokens) == 0:
            logging.info("No token found")
            return None
        else:
            logging.info("%d tokens found" % len(request_tokens))
            raise Exception('More than one %s token matches token "%s"'%(token_type,token))


    def lookup_nonce(self, oauth_consumer, oauth_token, nonce):

        if oauth_token is None:
            return None

        nonces = (Nonce.all().
                filter('consumer_key =', oauth_consumer.key_).
                filter('token_key =', oauth_token.key_).
                filter('key_ =', nonce).
                fetch(1000))

        # Filter out all expired nonces
        #
        # TODO: one day we may need to do this at the datastore query level
        # and create the appropriate index to do so in case we have a very
        # active client w/ an old token who has submitted 1000+ identical
        # legitimate Nonces.
        nonces = [n for n in nonces if not n.is_expired]

        if len(nonces) == 1:
            nonce = nonces[0]
            return nonce.key_
        elif len(nonces) == 0:
            #create a nonce
            nonce_obj = Nonce(consumer_key=oauth_consumer.key_,
                token_key=oauth_token.key_,
                key_=nonce,
                created=datetime.datetime.now())
            nonce_obj.put()
            return None
        else:
            raise Exception('More than one nonce matches consumer_key "%s", \
                token_key "%s", key_ "%S"'%(oauth_consumer.key,oauth_token.key, nonce))


    def fetch_request_token(self, oauth_consumer, oauth_callback):

        if oauth_consumer.key != self.consumer.key:
            raise OAuthError('Consumer key does not match.')

        # OAuth 1.0a: if there is a callback, check its validity
        callback = None
        callback_confirmed = False
        if oauth_callback:
            if oauth_callback != OUT_OF_BAND:
                if check_valid_callback(oauth_callback):
                    callback = oauth_callback
                    callback_confirmed = True
                else:
                    raise oauth.OAuthError('Invalid callback URL.')

        # Not going to implement scope just yet-so just hard code this for now
        # We create a default resource if it doesn't already exist.
        resource = Resource.get_or_insert("default", name="default")

        #try:
        #    resource = Resource.objects.get(name=self.scope)
        #except:
        #    raise OAuthError('Resource %s does not exist.' % escape(self.scope))

        self.request_token = Token.create_token(consumer=self.consumer,
                                                        token_type=Token.REQUEST,
                                                        timestamp=self.timestamp,
                                                        resource=resource,
                                                        callback=callback,
                                                        callback_confirmed=callback_confirmed)

        return self.request_token


    def fetch_access_token(self, oauth_consumer, oauth_token, oauth_verifier):
        if (oauth_consumer.key_ == self.consumer.key_ and
                oauth_token.key_ == self.request_token.key_ and
                self.request_token.is_approved):
            # OAuth 1.0a: if there is a callback confirmed, check the verifier
            if ((self.request_token.callback_confirmed and
                    oauth_verifier == self.request_token.verifier) or
                    not self.request_token.callback_confirmed):
                self.access_token = Token.create_token(
                        consumer=self.consumer,
                        token_type=Token.ACCESS,
                        timestamp=self.timestamp,
                        user=self.request_token.user,
                        resource=self.request_token.resource)
                return self.access_token
        raise oauth.OAuthError("Consumer key or token key does not match. " +
                               "Make sure your request token is approved. " +
                               "Check your verifier too if you use OAuth 1.0a.")

    def authorize_request_token(self, oauth_token, user):
        if oauth_token.key == self.request_token.key:
            # authorize the request token in the store
            self.request_token.is_approved = True

            # OAuth 1.0a: if there is a callback confirmed, we must set a verifier
            if self.request_token.callback_confirmed:
                self.request_token.verifier = generate_random(VERIFIER_SIZE)

            self.request_token.user = user
            self.request_token.put()
            # Flush the db transaction.
            db.get(self.request_token.key())

            return self.request_token
        raise OAuthError('Token key does not match.')

def check_valid_callback(callback):
    """
    Checks the size and nature of the callback.
    """
    callback_url = urlparse(callback)
    return (callback_url.scheme
            and callback_url.hostname not in OAUTH_BLACKLISTED_HOSTNAMES
            and len(callback) < MAX_URL_LENGTH)

