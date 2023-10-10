import unittest
from datetime import date
from balancebook.csv import CsvConfig, CsvFile
from balancebook.account import load_accounts
from balancebook.balance import (load_balances, write_balances, verify_balances, Balance)
from balancebook.errors import DuplicateBalance

class TestBalance(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", decimal_separator=",", encoding="utf-8-sig")
        self.csvFile = CsvFile("tests/journal/data/balances.csv", self.config)
        self.accounts = load_accounts(CsvFile("tests/journal/data/accounts.csv", self.config))
        self.accounts_by_name = dict([(a.identifier, a) for a in self.accounts])

    def test_duplicate_balance(self):
        # Test that it raises an exception
        with self.assertRaises(DuplicateBalance):
            verify_balances([Balance(date(2021, 1, 1), self.accounts_by_name["Chequing"], 1000),
                             Balance(date(2021, 1, 1), self.accounts_by_name["Chequing"], 1000)])

if __name__ == '__main__':
    unittest.main()