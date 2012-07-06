import hashlib
import zlib
from base64 import b64encode, b64decode
from functools import wraps

from third_party import flask
from third_party.flask import request
from third_party.flask import current_app
from google.appengine.ext import db
from google.appengine.datastore import entity_pb

import api.jsonify as apijsonify
from app import App
import datetime
from layer_cache import layer_cache_check_set_return, Layers,\
    DEFAULT_LAYER_CACHE_EXPIRATION_SECONDS
import pickle_util
    

def has_flask_request_context():
    # HACK - peek into private variables since the current version of Flask
    # being used does not expose a helper for this (later versions do, and
    # the implementation is the same).
    return flask._request_ctx_stack.top is not None


def etag(func_tag_content):
    """ETag header support: check etag hdr for requests, add it to responses.

    If a function is decorated with @etag, then when a request comes
    in with an If-None-Match header, we check if that header value
    matches the given etag value and return a 304 (not modified) if
    so.  Otherwise, we run the decorated function normally and set an
    ETag header in the response, to allow future requests to use an
    If-None-Match header.

    Arguments:
      func_tag_content: a function that yields the ETag value for this
        request.  It should take the exact same arguments that the
        function-being-decorated does.  It can use these arguments to
        come up with a unique etag value.  TODO(csilvers): why not
        just pickle the args and kwargs and use that?, and replace
        func_tag_content with 'extra_args'?
    """
    def etag_wrapper(func):
        @wraps(func)
        def etag_enabled(*args, **kwargs):
            tag_content = func_tag_content(*args, **kwargs)
            # You can disable etags on a per-arg basis by returning None above.
            if tag_content is None:
                return func(*args, **kwargs)

            etag_inner_content = "%s:%s" % (tag_content, App.version)
            etag_server = '"%s"' % hashlib.md5(etag_inner_content).hexdigest()

            etag_client = request.headers.get("If-None-Match")
            if etag_client and etag_client == etag_server:
                return current_app.response_class(status=304)
            
            result = func(*args, **kwargs)

            if isinstance(result, current_app.response_class):
                result.headers["ETag"] = etag_server
                return result
            else:
                return current_app.response_class(
                    result, headers={"Etag": etag_server})
        return etag_enabled
    return etag_wrapper

_TWO_MONTHS = 60 * 60 * 24 * 60


def cacheable(caching_age=_TWO_MONTHS, cache_token_key="v"):
    """ Makes a method fully cacheable in the browser if the request has
    specified a cache_token argument in the URL.

    This allows clients who care about caching specify a token and create
    unique URL's for resources that should not change. Clients interested
    in getting updated data will find out through other means and know to
    change the value of that cache token. Cache tokens are opaque strings
    and does not affect the internal logic of this method.
    
    NOTE: If a URL end point has user specific data, it may be dangerous to
    cache it, since fully cached responses can be cached by shared caches
    according to the RFC:
    http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.9.1
    """
    def cacheable_wrapper(func):
        @wraps(func)
        def caching_enabled(*args, **kwargs):
            
            cache_token = request.args.get(cache_token_key)
            if cache_token is None:
                # If no cache_token is specified, don't treat it as cacheable
                return func(*args, **kwargs)
            
            result = func(*args, **kwargs)
            if not isinstance(result, current_app.response_class):
                result = current_app.response_class(result)
            result.cache_control.max_age = caching_age
            result.cache_control.public = True
            result.headers['Expires'] = (
                datetime.datetime.utcnow() +
                datetime.timedelta(seconds=caching_age))
            return result
        return caching_enabled
    return cacheable_wrapper


def jsonify(func):
    @wraps(func)
    def jsonified(*args, **kwargs):
        obj = func(*args, **kwargs)

        if isinstance(obj, current_app.response_class):
            return obj

        camel_cased = (has_flask_request_context() and
                       flask.request.values.get("casing") == "camel")

        return apijsonify.jsonify(obj, camel_cased=camel_cased)
    return jsonified


def jsonp(func):
    @wraps(func)
    def jsonp_enabled(*args, **kwargs):
        val = func(*args, **kwargs)

        if isinstance(val, current_app.response_class):
            return val

        callback = request.values.get("callback")
        if callback:
            val = "%s(%s)" % (callback, val)
        return current_app.response_class(
            val, mimetype="application/json; charset=utf-8")
    return jsonp_enabled


def compress(func):
    @wraps(func)
    def compressed(*args, **kwargs):
        val = func(*args, **kwargs)
        try:
            val = val.encode('utf-8')
        except Exception, why:
            if not isinstance(val, basestring):
                raise ValueError("%s [val has type %s]" % (why, type(val)))
            raise
        return zlib.compress(val)
    return compressed


def decompress(func):
    @wraps(func)
    def decompressed(*args, **kwargs):
        return zlib.decompress(func(*args, **kwargs)).decode('utf-8')
    return decompressed


def pickle(func):
    @wraps(func)
    def pickled(*args, **kwargs):
        return pickle_util.dump(func(*args, **kwargs))
    return pickled


def unpickle(func):
    @wraps(func)
    def unpickled(*args, **kwargs):
        return pickle_util.load(func(*args, **kwargs))
    return unpickled


def protobuf_encode(func):
    @wraps(func)
    def protobuf_encoded(*args, **kwargs):
        v = func(*args, **kwargs)
        if type(v) == list:
            return map(lambda entity: db.model_to_protobuf(entity).Encode(), v)
        else:
            return db.model_to_protobuf(v).Encode()

    return protobuf_encoded


def protobuf_decode(func):
    @wraps(func)
    def protobuf_decoded(*args, **kwargs):
        v = func(*args, **kwargs)
        if type(v) == list:
            return map(lambda pb: db.model_from_protobuf(
                                      entity_pb.EntityProto(pb)),
                       v)
        else:
            return db.model_from_protobuf(entity_pb.EntityProto(v))

    return protobuf_decoded


def base64_encode(func):
    @wraps(func)
    def base64_encoded(*args, **kwargs):
        return b64encode(func(*args, **kwargs))
    return base64_encoded


def base64_decode(func):
    @wraps(func)
    def base64_decoded(*args, **kwargs):
        return b64decode(func(*args, **kwargs))
    return base64_decoded


def cache_with_key_fxn_and_param(
        param_name,
        key_fxn,
        expiration=DEFAULT_LAYER_CACHE_EXPIRATION_SECONDS,
        layer=Layers.Memcache | Layers.InAppMemory,
        persist_across_app_versions=False,
        permanent_key_fxn=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            def wrapped_key_fxn(*args, **kwargs):
                underlying = key_fxn(*args, **kwargs)
                return (None if underlying is None else
                        "%s:%s=%s" % (underlying,
                                      param_name,
                                      request.values.get(param_name)))
            return layer_cache_check_set_return(func,
                                                wrapped_key_fxn,
                                                expiration,
                                                layer,
                                                persist_across_app_versions,
                                                permanent_key_fxn,
                                                *args, **kwargs)
        return wrapper
    return decorator
