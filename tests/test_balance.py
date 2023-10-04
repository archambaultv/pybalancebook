import unittest
from balancebook.csv import CsvConfig, CsvFile
from balancebook.account import load_accounts
from balancebook.balance import (load_balances, write_balances)

class TestBalance(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", decimal_separator=",", encoding="utf-8-sig")
        self.csvFile = CsvFile("tests/journal_en/balance.csv", self.config)
        self.accounts = load_accounts(CsvFile("tests/journal_en/account.csv", self.config))
        self.accounts_by_name = dict([(a.identifier, a) for a in self.accounts])

    def test_load_balance(self):
        try:
            load_balances(self.csvFile, self.accounts_by_name)
        except Exception as e:
            self.fail("load_balances() raised Exception: " + str(e))           

    def test_export_balances(self):
        # Test that it does not raise an exception
        bals = load_balances(self.csvFile, self.accounts_by_name)
        try:
            write_balances(bals, CsvFile("tests/journal_en/export/bals.csv", self.config))
        except Exception as e:
            self.fail("write_balances() raised Exception: " + str(e))

if __name__ == '__main__':
    unittest.main()