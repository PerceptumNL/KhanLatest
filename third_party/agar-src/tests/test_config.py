import unittest

from agar.config import Config

class SampleConfig(Config):
    _prefix = 'test'

    STRING_CONFIG = 'defaultstring'


class ConfigTest(unittest.TestCase):
    def test_config(self):
        config = SampleConfig.get_config()
        self.assertEqual(config.STRING_CONFIG, 'defaultstring')

    def test_override_config(self):
        config = SampleConfig.get_config(STRING_CONFIG='customstring')
        self.assertEqual(config.STRING_CONFIG, 'customstring')

    def test_invalid_override(self):
        try:
            SampleConfig.get_config(INVALID_CONFIG=None)
            self.fail("Able to set an invalid config property")
        except AttributeError, e:
            self.assertEqual(e.message, "Invalid config key: INVALID_CONFIG")
