import unittest

from balancebook.journal.config import load_config
from balancebook.journal.journal import Journal

class Testi18n(unittest.TestCase):
    def test_fr(self):
        config = load_config("tests/i18n/fr/balancebook.fr.yaml")     
        self.journal = Journal(config)
        self.journal.load()