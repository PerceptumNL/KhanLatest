"""Test pickle_util.py

In particular, test that we can successfully unpickle using the
pickle-map.
"""

import cPickle
import imp
import pickle
import sys
try:
    import unittest2 as unittest     # python 2.5
except ImportError:
    import unittest                  # python 2.6+

import pickle_util


class OldClass(object):
    _NAME = 'OldClass'

    def name(self):
        return self._NAME

    def num(self):
        return 1


class NewClassDefinition(object):
    _NAME = 'NewClass'

    def name(self):
        return self._NAME

    def num(self):
        return 1


# Now we want to install OldClassDefinition in its proper submodule
def setUpModule():
    """Install NewClassDefinition into its proper submodule."""
    mod = imp.new_module('mod')
    mod.submod1 = imp.new_module('submod1')
    mod.submod1.submod2 = imp.new_module('submod2')
    sys.modules['mod'] = mod
    sys.modules['mod.submod1'] = mod.submod1
    sys.modules['mod.submod1.submod2'] = mod.submod1.submod2
    mod.submod1.submod2.NewClass = NewClassDefinition


class CPickleTest(unittest.TestCase):
    """Tests for when we get to import cPickle as cPickle."""
    def setUp(self):
        self.orig_class_rename_map = pickle_util._CLASS_RENAME_MAP
        self.orig_oldclass = OldClass

    def tearDown(self):
        pickle_util._CLASS_RENAME_MAP = self.orig_class_rename_map
        globals()['OldClass'] = self.orig_oldclass

    def test_simple(self):
        expected = 'i am a simple type'
        actual = pickle_util.load(pickle_util.dump(expected))
        self.assertEqual(expected, actual)

    def test_simple_class(self):
        """Test pickling and unpickling a class and class instance."""
        expected = (OldClass, OldClass())
        actual = pickle_util.load(pickle_util.dump(expected))
        self.assertEqual(expected[0], actual[0])
        self.assertEqual(type(expected[1]), type(actual[1]))

    def test_rewritten_class(self):
        global OldClass
        # Mock out the rename-map.
        pickle_util._CLASS_RENAME_MAP = {
            ('pickle_util_test', 'OldClass'):
            ('mod.submod1.submod2', 'NewClass')
            }
        pickled = pickle_util.dump(OldClass)
        # Just to make this more fun, delete OldClass
        del OldClass
        actual = pickle_util.load(pickled)
        import mod.submod1.submod2
        self.assertEqual(actual, mod.submod1.submod2.NewClass)

    def test_rewritten_class_instance(self):
        global OldClass
        # Mock out the rename-map.
        pickle_util._CLASS_RENAME_MAP = {
            ('pickle_util_test', 'OldClass'):
            ('mod.submod1.submod2', 'NewClass')
            }
        pickled = pickle_util.dump(OldClass())
        # Just to make this more fun, delete OldClass
        del OldClass
        actual = pickle_util.load(pickled)
        import mod.submod1.submod2
        self.assertTrue(isinstance(actual, mod.submod1.submod2.NewClass))

    def test_unpickling_data_pickled_with_pickle(self):
        expected = 'This is a test string'
        actual = pickle_util.load(pickle.dumps(expected))
        self.assertEqual(expected, actual)

    def test_unpickling_data_pickled_with_cpickle(self):
        expected = 'This is a test string'
        actual = pickle_util.load(cPickle.dumps(expected))
        self.assertEqual(expected, actual)

    def test_unpickling_data_pickled_with_pickle_vhigh(self):
        expected = 'This is a test string'
        actual = pickle_util.load(pickle.dumps(expected,
                                               pickle.HIGHEST_PROTOCOL))
        self.assertEqual(expected, actual)

    def test_unpickling_data_pickled_with_cpickle_vhigh(self):
        expected = 'This is a test string'
        actual = pickle_util.load(cPickle.dumps(expected,
                                                cPickle.HIGHEST_PROTOCOL))
        self.assertEqual(expected, actual)

    def test_using_pickle_to_unpickle(self):
        expected = 'This is a test string'
        actual = pickle.loads(pickle_util.dump(expected))
        self.assertEqual(expected, actual)

    def test_using_cpickle_to_unpickle(self):
        expected = 'This is a test string'
        actual = cPickle.loads(pickle_util.dump(expected))
        self.assertEqual(expected, actual)


class PickleTest(CPickleTest):
    """Tests for when we cPickle gets mapped to pickle (modeling appengine)."""
    def setUp(self):
        # Force pickle_util to act as if cPickle is the same as pickle.
        self.old_cpickle = pickle_util.cPickle
        pickle_util.cPickle = pickle_util.pickle

        self.old_unpickler_class = pickle_util.g_unpickler_class
        pickle_util.g_unpickler_class = (
            pickle_util.RenamedClassUnpicklerForPicklePy)

        super(PickleTest, self).setUp()

    def tearDown(self):
        super(PickleTest, self).tearDown()
        pickle_util.cPickle = self.old_cpickle
        pickle_util.g_unpickler_class = self.old_unpickler_class


class NewStyleToOldStyleClassTest(unittest.TestCase):
    """Test the ability to unpickle classes that change style.

    This is testing pickle_util functionality that was added to handle
    a very specific error case we were seeing: when upgrading
    appengine to appengine-python2.7, we found that some appengine
    classes were changed from old-style classes to new-style.

    This wasn't a problem until we needed to roll back to
    appengine-python2.5.  Then it *was* a problem, because pickle
    cannot unpickle classes that are currently old-style, but were
    new-style when they were pickled.

    I changed pickle-util to handle that case, but only for the very
    specific circumstance that the class was pickled with protocol 2,
    and is being unpickled with pickle (not cPickle).  Fortunately,
    both of those conditions are met for the special case this code is
    intended to handle.
    """
    def test_new_class_to_old_class(self):
        class NewOldClass(object):
            """New-style class."""
            def __init__(self, x, y):
                self.x = x
                self.y = y
        # A trick so we can pickle this class even though it's nested.
        setattr(sys.modules[__name__], 'NewOldClass', NewOldClass)
        pickled_new = pickle_util.dump(NewOldClass(5, 11))

        # Redefine NewOldClass to be old-style
        del NewOldClass

        class NewOldClass:
            """Old-style class."""
            def __init__(self, x, y):
                self.x = x
                self.y = y
        setattr(sys.modules[__name__], 'NewOldClass', NewOldClass)

        # Make sure the unpickling uses pickle, not cpickle
        old_cpickle = pickle_util.cPickle
        old_unpickler_class = pickle_util.g_unpickler_class
        try:
            pickle_util.cPickle = pickle_util.pickle    
            pickle_util.g_unpickler_class = (
                pickle_util.RenamedClassUnpicklerForPicklePy)

            foo = pickle_util.load(pickled_new)
            self.assertEqual(5, foo.x)
            self.assertEqual(11, foo.y)
            self.assertEqual('Old-style class.', foo.__doc__)
        finally:
            pickle_util.cPickle = old_cpickle
            pickle_util.g_unpickler_class = old_unpickler_class
