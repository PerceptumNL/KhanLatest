import os
import random

from auth.passwords import *
from testutil import testsize

try:
    import unittest2 as unittest
except ImportError:
    import unittest


class HashingTests(unittest.TestCase):
    def setUp(self):
        super(HashingTests, self).setUp()
        self.real_os_random = os.urandom
        random.seed(0)
        os.urandom = self.fake_urandom

    def tearDown(self):
        os.urandom = self.real_os_random
        super(HashingTests, self).tearDown()

    def fake_urandom(self, bytes):
        return str(random.getrandbits(8 * bytes))

    @testsize.medium()
    def test_hashing_is_unique(self):
        passwords = ['password',
                     'password1',
                     'thequickbrownfoxjumpsoverthelazydog',
                     'i4m$01337']
        hashes = [hash_password(pw, self.fake_urandom(8))
                  for pw in passwords]
        self.assertEquals(len(set(hashes)), len(passwords))

    @testsize.medium()
    def test_hashing_is_verifiable(self):
        passwords = ['password',
                     'password1',
                     'thequickbrownfoxjumpsoverthelazydog',
                     'i4m$01337']
        for pw in passwords:
            salt = self.fake_urandom(8)
            hash = hash_password(pw, salt)
            self.assertTrue(validate_password(pw, salt, hash))
            self.assertFalse(validate_password(pw + 'x', salt, hash))
