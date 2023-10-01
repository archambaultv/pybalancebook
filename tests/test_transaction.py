import unittest
from datetime import date
from balancebook.csv import CsvConfig, CsvFile
from balancebook.account import load_and_normalize_accounts
from balancebook.transaction import (load_txns, normalize_txn, Txn, Posting,
                                          load_and_normalize_txns, write_txns)
import balancebook.errors as bberr

class TestTxn(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", decimal_separator=",", encoding="utf-8-sig")
        self.csvFile = CsvFile("tests/journal_en/transaction.csv", self.config)
        self.accounts = load_and_normalize_accounts(CsvFile("tests/journal_en/account.csv", self.config))
        self.accounts_by_name = dict([(a.identifier, a) for a in self.accounts])

    def test_load_txns(self):
        try:
            load_txns(self.csvFile)
        except Exception as e:
            self.fail("load_txns() raised Exception: " + str(e))

    def test_load_normalize_balance(self):
        try:
            load_and_normalize_txns(self.csvFile, self.accounts_by_name)
        except Exception as e:
            self.fail("load_and_normalize_txns() raised Exception: " + str(e))   

    def test_normalize_txn(self):
        # Test that the account exists
        with self.assertRaises(bberr.UnknownAccount):
            normalize_txn(Txn(1, "2021-01-01", [Posting("a", 1000,), Posting("Chequing", -1000)]), self.accounts_by_name)

        with self.assertRaises(bberr.UnknownAccount):
            normalize_txn(Txn(1, "2021-01-01", [Posting("Chequing", 1000), Posting("b", -1000)]), self.accounts_by_name)

        # Test that the transaction is balanced
        with self.assertRaises(bberr.TxnNotBalanced):
            normalize_txn(Txn(1, "2021-01-01", [Posting("Chequing", 1000), Posting("Credit card", -999)]), self.accounts_by_name)

        # Test that there is at least two posting
        with self.assertRaises(bberr.TxnLessThanTwoPostings):
            normalize_txn(Txn(1, "2021-01-01", [Posting("Chequing", 1000)]), self.accounts_by_name)

        # Test that there is only one posting without amount
        with self.assertRaises(bberr.TxnMoreThanTwoPostingsWithNoAmount):
            normalize_txn(Txn(1, "2021-01-01", [Posting("Chequing", 1000), Posting("Credit card"), Posting("Mortgage")]), 
                          self.accounts_by_name)

        # Set the amount of the posting without amount
        t = Txn(1, "2021-01-01", [Posting("Chequing", 1000.0), Posting("Credit card",-25), Posting("Mortgage")])
        normalize_txn(t, self.accounts_by_name)
        self.assertEqual(t.postings[2].amount, -97500)

        # Set the statement date of the postings to the transaction date
        t = Txn(1, "2021-01-01", [Posting("Chequing", 1000), 
                               Posting("Credit card",-25), 
                               Posting("Mortgage", statement_date="2021-01-02")])
        normalize_txn(t, self.accounts_by_name)
        self.assertEqual(t.postings[0].statement_date, date(2021, 1, 1))
        self.assertEqual(t.postings[1].statement_date, date(2021, 1, 1))
        self.assertEqual(t.postings[2].statement_date, date(2021, 1, 2))

    def test_export_txns(self):
        # Test that it does not raise an exception
        txns = load_and_normalize_txns(self.csvFile, self.accounts_by_name)
        try:
            write_txns(txns, CsvFile("tests/journal_en/export/txns.csv", self.config), extra_columns=True)
        except Exception as e:
            self.fail("write_txns() raised Exception: " + str(e))

if __name__ == '__main__':
    unittest.main()