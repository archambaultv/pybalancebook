import unittest
from datetime import date
from christophe.csv import CsvConfig, CsvFile
from christophe.i18n import i18n_en
from christophe.account import load_and_normalize_accounts
from christophe.transaction import load_and_normalize_txns
from christophe.balance import (normalize_balance, load_balances, Balance, load_and_normalize_balances, verify_balances_txns)

class TestBalance(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", decimal_separator=",", encoding="utf-8-sig")
        self.csvFile = CsvFile("tests/journal_en/balance.csv", self.config)
        self.i18n = self.i18n = i18n_en
        self.accounts = load_and_normalize_accounts(CsvFile("tests/journal_en/account.csv", self.config), self.i18n)
        self.accounts_by_name = dict([(a.identifier, a) for a in self.accounts])

    def test_load_balance(self):
        try:
            load_balances(self.csvFile, self.i18n)
        except Exception as e:
            self.fail("load_balances() raised Exception: " + str(e))

    def test_load_normalize_balance(self):
        try:
            load_and_normalize_balances(self.csvFile, self.accounts_by_name, self.i18n)
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
            bals = load_and_normalize_balances(self.csvFile, self.accounts_by_name, self.i18n)
            txns = load_and_normalize_txns(CsvFile("tests/journal_en/transaction.csv", self.config), 
                                           self.accounts_by_name, self.i18n)
            verify_balances_txns(bals, txns, True, self.i18n)


        except Exception as e:
            self.fail("load_balances() raised Exception: " + str(e))          

if __name__ == '__main__':
    unittest.main()