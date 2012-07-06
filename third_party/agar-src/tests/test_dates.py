from datetime import datetime
from unittest2 import TestCase

from agar.dates import parse_datetime

class ParseDateTimeTests(TestCase):
    
    def test_none_returns_none(self):
        self.assertIsNone(parse_datetime(None))

    def test_simple_date(self):
        date_string = '2011-06-01'
        date = parse_datetime(date_string)
        expect = datetime(2011, 6, 1)
        self.assertEqual(expect, date)

