import unittest
from datetime import date
from balancebook.csv import CsvConfig, CsvFile
from balancebook.account import load_accounts
from balancebook.transaction import (load_txns, verify_txn, Txn, Posting,
                                     write_txns)
import balancebook.errors as bberr

class TestTxn(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", decimal_separator=",", encoding="utf-8-sig")
        self.csvFile = CsvFile("tests/journal/transaction.csv", self.config)
        self.accounts = load_accounts(CsvFile("tests/journal/account.csv", self.config))
        self.accounts_by_name = dict([(a.identifier, a) for a in self.accounts])

    def test_load_txns(self):
        try:
            load_txns(self.csvFile, self.accounts_by_name)
        except Exception as e:
            self.fail("load_txns() raised Exception: " + str(e)) 

    def test_normalize_txn(self):
        # Test that the transaction is balanced
        with self.assertRaises(bberr.TxnNotBalanced):
            verify_txn(Txn(1, "2021-01-01", [Posting("Chequing", 1000), Posting("Credit card", -999)]))

        # Test that there is at least two posting
        with self.assertRaises(bberr.TxnLessThanTwoPostings):
            verify_txn(Txn(1, "2021-01-01", [Posting("Chequing", 1000)]))

    def test_export_txns(self):
        # Test that it does not raise an exception
        txns = load_txns(self.csvFile, self.accounts_by_name)
        try:
            write_txns(txns, CsvFile("tests/journal/export/txns.csv", self.config), extra_columns=True)
        except Exception as e:
            self.fail("write_txns() raised Exception: " + str(e))

if __name__ == '__main__':
    unittest.main()