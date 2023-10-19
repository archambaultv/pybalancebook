import unittest

from balancebook.journal.config import load_config
from balancebook.journal.journal import Journal
from balancebook.utils import are_files_identical

class Testi18n(unittest.TestCase):
    def test_fr(self):
        config = load_config("tests/i18n/fr/balancebook.fr.yaml")     
        self.journal = Journal(config)
        self.journal.load()

        self.journal.auto_import()
        # Compare the exported files to the expected files
        self.assertTrue(are_files_identical('tests/i18n/fr/importation/nouvelles transactions.csv', 
                                            'tests/expected/i18n/fr/nouvelles transactions.csv'))
        self.assertTrue(are_files_identical('tests/i18n/fr/importation/descriptions non appariées.csv', 
                                            'tests/expected/i18n/fr/descriptions non appariées.csv'))