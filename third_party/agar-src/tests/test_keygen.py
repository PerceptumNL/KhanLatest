import unittest2

import logging

class TestKeygen(unittest2.TestCase):

    def verify(self, generator, length, count=100):
        keys = set([generator() for _ in range(count)])
        for key in keys:
            self.assertTrue('Expected: %s, Actual: %s' % (length, len(key)), (length - 1) <= len(key) <= (length + 1))
        self.assertEquals(count, len(keys))

    def test_gen_short_key(self):
        from agar.keygen import gen_short_key
        self.verify(gen_short_key, 22)
        
    def test_gen_medium_key(self):
        from agar.keygen import gen_medium_key
        self.verify(gen_medium_key, 44)
    
    def test_gen_long_key(self):
        from agar.keygen import gen_long_key
        self.verify(gen_long_key, 66)
