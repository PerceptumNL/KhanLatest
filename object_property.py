"""Contains custom app engine properties (see
developers.google.com/appengine/docs/python/datastore/typesandpropertyclasses
and developers.google.com/appengine/docs/python/datastore/propertyclass).

TODO(david): Rename this file to something more appropriate since it holds more
    than just ObjectProperty now, or split it up.
"""

try:
    import json
except ImportError:
    import simplejson as json

from google.appengine.ext import db
import pickle_util


class ObjectProperty(db.BlobProperty):
    """A property that can be used to store arbitrary objects, via pickling.

    IMPORTANT: this uses pickle to serialize the object contents
    and, as a result, is fragile when used with objects that
    contain non-primitive data, since alterations to their
    class definitions (moving from one module to another, etc)
    can make the serialized contents no longer deserializable.

    It is recommended this is only used with primitive types
    or dicts containing primitive types.

    From http://kovshenin.com/2010/app-engine-json-objects-google-datastore/
    """
    def validate(self, value):
        """Validate that value is pickle-able (raise an exception if not)."""
        pickled_value = pickle_util.dump(value)
        _ = super(ObjectProperty, self).validate(pickled_value)
        return value

    def get_value_for_datastore(self, model_instance):
        result = (super(ObjectProperty, self)
                  .get_value_for_datastore(model_instance))
        result = pickle_util.dump(result)
        return db.Blob(result)

    def make_value_from_datastore(self, value):
        value = pickle_util.load(str(value))
        return super(ObjectProperty, self).make_value_from_datastore(value)


class UnvalidatedObjectProperty(ObjectProperty):
    """Like ObjectProperty but just assumes passed-in values can be pickled."""
    def validate(self, value):
        # pickle.dumps can be slooooooow, sometimes we just want to
        # trust that the item is pickle'able (and that it fills all
        # the validity requirements of db.BlobProperty as well.)
        return value


class JsonProperty(db.TextProperty):
    """An alternative to ObjectProperty that uses JSON for serialization. Note:
    keys and values must all be primitives (eg. datetime objects as keys will
    raise an error on put).

    JSON is generally faster and smaller in Python (see
    http://kovshenin.com/2010/pickle-vs-json-which-is-faster/ and
    http://inkdroid.org/journal/2008/10/24/json-vs-pickle/), but can only be
    used for serializing primitives. Pickle can be used to serialize classes,
    for example, but storing classes is brittle and could cause issues if
    changing class names, moving classes to different files, or switching
    between Python 2.5 and 2.7.

    Modified from
    http://kovshenin.com/2010/app-engine-json-objects-google-datastore/
    """

    def validate(self, value):
        jsoned_value = json.dumps(str(value))
        _ = super(JsonProperty, self).validate(jsoned_value)
        return value

    def get_value_for_datastore(self, model_instance):
        result = super(JsonProperty, self).get_value_for_datastore(
                model_instance)
        result = json.dumps(result)
        return db.Text(result)

    def make_value_from_datastore(self, value):
        value = json.loads(str(value))
        return super(JsonProperty, self).make_value_from_datastore(value)


class TsvProperty(db.TextProperty):
    '''
    An alternative to StringListProperty that serializes lists using a simple
    tab-separated format. This is much faster than StringPropertyList, however
    elements with tabs are not permitted.
    '''
    data_type = list

    def __init__(self, default=None, **kwds):
        if default is None:
            default = []
        super(TsvProperty, self).__init__(default=default, **kwds)

    def get_value_for_datastore(self, model_instance):
        value = (super(TsvProperty, self)
                 .get_value_for_datastore(model_instance))
        return db.Text("\t".join(value or []))

    def make_value_from_datastore(self, value):
        return self.str_to_tsv(value)

    @staticmethod
    def str_to_tsv(value):
        return value.split("\t") if value else []

    def empty(self, value):
        """Is list property empty.

        [] is not an empty value.

        Returns:
          True if value is None, else false.
        """
        return value is None

    def default_value(self):
        """Default value for list.

        Because the property supplied to 'default' is a static value,
        that value must be shallow copied to prevent all fields with
        default values from sharing the same instance.

        Returns:
          Copy of the default value.
        """
        return list(super(TsvProperty, self).default_value())

# the following properties are useful for migrating StringListProperty to
# the faster TsvProperty


class TsvCompatStringListProperty(db.StringListProperty):
    """A StringListProperty that can also read lists serialized as tab
    separated strings"""
    def make_value_from_datastore(self, value):
        if isinstance(value, list):
            return (super(TsvCompatStringListProperty, self)
                    .make_value_from_datastore(value))
        else:
            return TsvProperty.str_to_tsv(value)


class StringListCompatTsvProperty(TsvProperty):
    'A TsvProperty that can also read lists serialized as native Python lists'
    def make_value_from_datastore(self, value):
        if isinstance(value, list):
            return value
        else:
            return (super(StringListCompatTsvProperty, self)
                    .make_value_from_datastore(value))
