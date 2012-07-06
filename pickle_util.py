"""Utility functions for pickling and unpickling.

These provide a thin wrapper around pickle.dumps and loads, but
automatically pick a fast pickle implementation and an efficient
pickle version.

Most important, these utilities deal with class renaming.  Sometimes
database entities are pickled -- see exercise_models.UserExercise,
which pickles AccuracyModel.  If we renamed AccuracyModel -- even just
by moving it to another location -- then unpickling UserExercise would
break.  To fix it, we keep a map in this file of oldname->newname.
Then, whenever we unpickle an object and see oldname, we can
instantiate a newname instead.
"""

import cPickle
import cStringIO
import pickle      # appengine (with python2.5) doesn't support cPickle
import sys
import types

# Provide some of the symbols from pickle so we can be a drop-in replacement.
from pickle import PicklingError   # @UnusedImport


# To update this: if you rename a subclass of db.model, add a new entry:
#   (old_modules, old_classname) -> (new_modules, new_classname)
# If you later want to rename newname to newername, you should add
#   (new_modules, new_classname) -> (newer_modules, newer_classname)
# but also modify the existing oldname entry to be:
#   (old_modules, old_classname) -> (newer_modules, newer_classname)
_CLASS_RENAME_MAP = {
    ('accuracy_model.accuracy_model', 'AccuracyModel'):
    ('exercises.accuracy_model', 'AccuracyModel'),

    ('accuracy_model', 'AccuracyModel'):
    ('exercises.accuracy_model', 'AccuracyModel'),
}


def _renamed_class_loader(module_name, class_name):
    """Return a class object for class class_name, loaded from module_name.

    The trick here is we look in _CLASS_RENAME_MAP before doing
    the loading.  So even if the class has moved to a different module
    since when this pickled object was created, we can still load it.
    """
    (actual_module_name, actual_class_name) = _CLASS_RENAME_MAP.get(
        (module_name, class_name),   # key to the map
        (module_name, class_name))   # what to return if the key isn't found

    # This is taken from pickle.py:Unpickler.find_class()
    __import__(actual_module_name)   # import the module if necessary
    module = sys.modules[actual_module_name]
    return getattr(module, actual_class_name)


class RenamedClassUnpicklerForPicklePy(pickle.Unpickler):
    """Intercept class-unpickling the pickle.py way (as opposed to cPickle)."""
    # See http://docs.python.org/library/pickle.html#subclassing-unpicklers
    def load_global(self):
        module = self.readline()[:-1]
        name = self.readline()[:-1]
        self.append(_renamed_class_loader(module, name))

    # Not in the documentation, but what the source code requires
    pickle.Unpickler.dispatch[pickle.GLOBAL] = load_global

    # This is needed for the python2.5->2.7 transition.  Some classes
    # change from old-style to new-style between the 2.5 and 2.7
    # appengine APIs.  Python can handle every case except depickling
    # a class that is now old-style, but was pickled as new-style.
    # This hack lets us support that.  Note it depends on the pickle
    # protocol being >=2, and using pickle, not cPickle, to unpickle.
    # VERY FRAGILE!
    def load_newobj(self):
        args = self.stack.pop()
        cls = self.stack[-1]
        try:
            obj = cls.__new__(cls, *args)
            self.stack[-1] = obj
        except AttributeError:        # cls is actually an old-style class
            k = len(self.stack) - 1   # point to the markobject
            self.stack.extend(args)
            self._instantiate(cls, k)
    pickle.Unpickler.dispatch[pickle.NEWOBJ] = load_newobj


# Appengine maps cPickle to pickle.  Unfortunately, the only reliable
# way to tell is to check whether its types are built-in types or not.
# (cPickle is all built-ins, and pickle isn't.)
if isinstance(cPickle.Unpickler, types.ClassType):        # not a built-in type
    g_unpickler_class = RenamedClassUnpicklerForPicklePy  # cPickle is pickle
else:
    g_unpickler_class = cPickle.Unpickler


def dump(obj):
    """Return a pickled string of obj: equivalent to pickle.dumps(obj)."""
    return cPickle.dumps(obj, cPickle.HIGHEST_PROTOCOL)


def load(s):
    """Return an unpickled object from s: equivalent to pickle.loads(s)."""
    unpickler = g_unpickler_class(cStringIO.StringIO(s))
    # This is needed when using cPickle, and harmless when using pickle.
    # See http://docs.python.org/library/pickle.html#subclassing-unpicklers
    unpickler.find_global = _renamed_class_loader
    return unpickler.load()
