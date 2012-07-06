# From http://kovshenin.com/archives/app-engine-python-objects-in-the-google-datastore/

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
