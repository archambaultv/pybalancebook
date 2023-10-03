import unittest
from datetime import date
from balancebook.csv import CsvConfig, CsvFile
from balancebook.journal.journal import load_and_normalize_journal, JournalConfig
import balancebook.errors as bberr

class TestTxn(unittest.TestCase):
    def setUp(self) -> None:
        self.csvConfig = CsvConfig(column_separator=";", decimal_separator=",", encoding="utf-8-sig")
        self.csvTxns = CsvFile("tests/journal_en/transaction.csv", self.csvConfig)
        self.csvAccount = (CsvFile("tests/journal_en/account.csv", self.csvConfig))
        self.csvBal = CsvFile("tests/journal_en/balance.csv", self.csvConfig)
        self.jConfig = JournalConfig(self.csvAccount, self.csvTxns, self.csvBal, 1)
        
        self.journal = load_and_normalize_journal(self.jConfig)

    def test_verify_balance(self):
        try:
            self.journal.verify_balances()
        except Exception as e:
            self.fail("verify_balances() raised Exception: " + str(e))

    

if __name__ == '__main__':
    unittest.main()