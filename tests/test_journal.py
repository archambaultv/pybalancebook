import unittest
from datetime import date
from balancebook.csv import CsvConfig, CsvFile
from balancebook.journal.journal import load_journal, JournalConfig
from balancebook.journal.autoimport import CsvImportHeader, AmountType
import balancebook.errors as bberr

class TestTxn(unittest.TestCase):
    def setUp(self) -> None:
        self.csvConfig = CsvConfig(column_separator=";", decimal_separator=",", encoding="utf-8-sig")
        self.csvTxns = CsvFile("tests/journal/transaction.csv", self.csvConfig)
        self.csvAccount = (CsvFile("tests/journal/account.csv", self.csvConfig))
        self.csvBal = CsvFile("tests/journal/balance.csv", self.csvConfig)
        self.jConfig = JournalConfig(self.csvAccount, self.csvTxns, self.csvBal, 1)
        
        self.journal = load_journal(self.jConfig)

    def test_verify_balance(self):
        try:
            self.journal.verify_balances()
        except Exception as e:
            self.fail("verify_balances() raised Exception: " + str(e))

    def test_fiscal_year(self):
        self.assertEqual(2020, self.journal.fiscal_year(date(2020, 1, 1)))
        self.assertEqual(2034, self.journal.fiscal_year(date(2034, 1, 1)))
        self.assertEqual(1997, self.journal.fiscal_year(date(1997, 12, 12)))

        self.journal.config.first_fiscal_month = 4
        self.assertEqual(2020, self.journal.fiscal_year(date(2020, 3, 31)))
        self.assertEqual(2021, self.journal.fiscal_year(date(2020, 4, 1)))
        self.assertEqual(2021, self.journal.fiscal_year(date(2020, 12, 12)))

    def test_fiscal_month(self):
        self.assertEqual(1, self.journal.fiscal_month(date(2020, 1, 1)))
        self.assertEqual(6, self.journal.fiscal_month(date(2034, 6, 1)))
        self.assertEqual(12, self.journal.fiscal_month(date(1997, 12, 12)))

        self.journal.config.first_fiscal_month = 4
        self.assertEqual(12, self.journal.fiscal_month(date(2020, 3, 31)))
        self.assertEqual(1, self.journal.fiscal_month(date(2020, 4, 1)))
        self.assertEqual(9, self.journal.fiscal_month(date(2020, 12, 12)))

    def test_auto_import(self):
        csvBank = CsvFile("tests/journal/bank data/chequing.csv", self.csvConfig)
        csvHeader = CsvImportHeader("Date",
                                    AmountType(False, "Debit", "Credit"), 
                                    None, 
                                    ["Description","Category"])
        acc = self.journal.get_account("Chequing")
        acc2 = self.journal.get_account("Misc. expenses")
        rules = []
        try:
            self.journal.import_from_bank_csv(csvBank, csvHeader, acc, acc2, rules)
        except Exception as e:
            self.fail("import_from_bank_csv() raised Exception: " + str(e))

if __name__ == '__main__':
    unittest.main()