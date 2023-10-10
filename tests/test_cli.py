import unittest
import sys
from balancebook.journal.cli import main, parser

class TestTxn(unittest.TestCase):

    def test_verify(self):
        sys.argv = ['balancebook', 'verify','-c', 'tests/journal/balancebook.yaml']
        try:
            main()
        except Exception as e:
            self.fail("verify raised Exception: " + str(e))

    def test_export(self):
        sys.argv = ['balancebook', 'export','-c', 'tests/journal/balancebook.yaml']
        try:
            main()
        except Exception as e:
            self.fail("export raised Exception: " + str(e))

    def test_reformat(self):
        sys.argv = ['balancebook', 'reformat','-c', 'tests/journal/balancebook.yaml']
        try:
            main()
        except Exception as e:
            self.fail("reformat raised Exception: " + str(e))

    # def test_auto_import(self):
    #     csvBank = CsvFile("tests/journal/bank data/chequing.csv", self.csvConfig)
    #     csvHeader = CsvImportHeader("Date",
    #                                 AmountType(False, "Debit", "Credit"), 
    #                                 None, 
    #                                 ["Description","Category"])
    #     acc = self.journal.get_account("Chequing")
    #     acc2 = self.journal.get_account("Misc. expenses")
    #     rules = load_classification_rules(CsvFile("tests/journal/rules.csv", self.csvConfig), 
    #                                       self.journal.account_by_id_dict())

    #     try:
    #         txns1 = self.journal.import_from_bank_csv(csvBank, csvHeader, acc, acc2, rules)
    #     except Exception as e:
    #         self.fail("import_from_bank_csv() raised Exception: " + str(e))
    #     self.assertEqual(3, len(txns1))
    #     self.assertEqual("Food", txns1[0].postings[1].account.identifier)
    #     self.assertEqual("Misc. expenses", txns1[1].postings[1].account.identifier)
    #     self.assertEqual("Salary", txns1[2].postings[1].account.identifier)

if __name__ == '__main__':
    unittest.main()