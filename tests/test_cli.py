import unittest
import sys
import os
import glob
from balancebook.journal.cli import main
from tests.utils import are_files_identical

class TestTxn(unittest.TestCase):

    def test_verify(self):
        sys.argv = ['balancebook', 'verify','-c', 'tests/journal/balancebook.en.yaml']
        try:
            main()
        except Exception as e:
            self.fail("verify raised Exception: " + str(e))

    def test_export(self):
        # Remove the all files in tests/export
        files = glob.glob('tests/export/*')
        for f in files:
            os.remove(f)

        sys.argv = ['balancebook', 'export','-c', 'tests/journal/balancebook.en.yaml','--today','2023-09-17']
        try:
            main()
        except Exception as e:
            self.fail("export raised Exception: " + str(e))

        # Compare the exported files to the expected files
        files = glob.glob('tests/export/*')
        self.assertTrue(len(files) == 3)
        for f in files:
            # Compare the file to the corresponding file in tests/expected/export
            f2 = f.replace('tests/export', 'tests/expected/export')
            if not are_files_identical(f, f2):
                self.fail(f + " is not identical to expected")

    def test_reformat(self):
        files = glob.glob('tests/reformat/*')
        for f in files:
            os.remove(f)

        sys.argv = ['balancebook', 'reformat','-c', 'tests/journal/balancebook.en.yaml','-o','tests/reformat']
        try:
            main()
        except Exception as e:
            self.fail("reformat raised Exception: " + str(e))

        # Compare the exported files to the expected files
        files = glob.glob('tests/reformat/*')
        self.assertTrue(len(files) == 3)
        for f in files:
            # Compare the file to the corresponding file in tests/expected/reformat
            f2 = f.replace('tests/reformat', 'tests/expected/reformat')
            if not are_files_identical(f, f2):
                self.fail(f + " is not identical to expected")

    def test_import(self):
        sys.argv = ['balancebook', 'import','-c', 'tests/journal/balancebook.en.yaml']
        try:
            main()
        except Exception as e:
            self.fail("import raised Exception: " + str(e))
        # Compare the exported files to the expected files
        if not are_files_identical('tests/journal/import/new transactions.csv', 
                                   'tests/expected/import/new transactions.csv'):
            self.fail("new transactions.csv is not identical to expected")
        if not are_files_identical('tests/journal/import/unmatched payees.csv', 
                                   'tests/expected/import/unmatched payees.csv'):
            self.fail("unmatched payees.csv is not identical to expected")
        
    def test_autobalance(self):
        sys.argv = ['balancebook', 'autobalance','-c', 'tests/journal/balancebook.en.yaml', '-o', 'tests/autobalance']
        try:
            main()
        except Exception as e:
            self.fail("autobalance raised Exception: " + str(e))

    # Clean up after tests
    def tearDown(self) -> None:
        # Remove the all files in tests/journal/backup
        files = glob.glob('tests/journal/backup/*')
        for f in files:
            os.remove(f)

if __name__ == '__main__':
    unittest.main()