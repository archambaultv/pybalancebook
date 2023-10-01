import unittest
from datetime import date
from balancebook.csv import CsvConfig, CsvFile
from balancebook.i18n import i18n_en
from balancebook.account import load_and_normalize_accounts
from balancebook.transaction import load_and_normalize_txns
from balancebook.balance import (normalize_balance, load_balances, Balance, load_and_normalize_balances, 
                                verify_balances_txns, write_balances)

class TestBalance(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", decimal_separator=",", encoding="utf-8-sig")
        self.csvFile = CsvFile("tests/journal_en/balance.csv", self.config)
        self.accounts = load_and_normalize_accounts(CsvFile("tests/journal_en/account.csv", self.config))
        self.accounts_by_name = dict([(a.identifier, a) for a in self.accounts])

    def test_load_balance(self):
        try:
            load_balances(self.csvFile)
        except Exception as e:
            self.fail("load_balances() raised Exception: " + str(e))

    def test_load_normalize_balance(self):
        try:
            load_and_normalize_balances(self.csvFile, self.accounts_by_name)
        except Exception as e:
            self.fail("load_balances() raised Exception: " + str(e))        

    def test_normalize_txn(self):
        # Test that the account exists
        with self.assertRaises(Exception):
            normalize_balance(Balance("2023-10-01", "a", "1000"), self.accounts_by_name)

        # Test that the statement balance is converted to int
        b = Balance("2023-10-01", "Chequing", "1000.0")
        normalize_balance(b, self.accounts_by_name)
        self.assertEqual(b.statement_balance, 100000)

    def test_verify(self):
        try:
            bals = load_and_normalize_balances(self.csvFile, self.accounts_by_name)
            txns = load_and_normalize_txns(CsvFile("tests/journal_en/transaction.csv", self.config), 
                                           self.accounts_by_name)
            verify_balances_txns(bals, txns, True)


        except Exception as e:
            self.fail("load_balances() raised Exception: " + str(e))          

    def test_export_balances(self):
        # Test that it does not raise an exception
        bals = load_and_normalize_balances(self.csvFile, self.accounts_by_name)
        try:
            write_balances(bals, CsvFile("tests/journal_en/export/bals.csv", self.config))
        except Exception as e:
            self.fail("write_balances() raised Exception: " + str(e))

if __name__ == '__main__':
    unittest.main()