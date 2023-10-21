import unittest
import glob
from datetime import date

from balancebook.journal.config import load_config
from balancebook.journal.journal import Journal
from tests.utils import are_files_identical

class Testi18n(unittest.TestCase):
    def test_fr(self):
        config = load_config("tests/i18n/fr/balancebook.fr.yaml")     
        self.journal = Journal(config)
        self.journal.load()

        self.journal.auto_import()
        # Compare the exported files to the expected files
        if not are_files_identical('tests/i18n/fr/importation/nouvelles transactions.csv',
                                   'tests/expected/i18n/fr/nouvelles transactions.csv'):
            self.fail("nouvelles transactions.csv is not identical to expected")
        if not are_files_identical('tests/i18n/fr/importation/descriptions non appariées.csv', 
                                   'tests/expected/i18n/fr/descriptions non appariées.csv'):
            self.fail("descriptions non appariées.csv is not identical to expected")

        
        self.journal.export(today = date(2023,9,17), output_dir = 'tests/i18n/fr/exportation')
        files = glob.glob('tests/i18n/fr/exportation/*')
        self.assertTrue(len(files) == 3)
        for f in files:
            # Compare the file to the corresponding file in tests/expected/export
            f2 = f.replace('i18n/fr/exportation', 'expected/i18n/fr')
            if not are_files_identical(f, f2):
                self.fail(f + " is not identical to expected")