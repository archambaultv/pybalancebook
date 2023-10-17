import unittest
from datetime import date
from balancebook.csv import CsvConfig, CsvFile
from balancebook.account import load_accounts
from balancebook.transaction import verify_txn, Txn, Posting, write_txns
import balancebook.errors as bberr

class TestTxn(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", decimal_separator=",", encoding="utf-8-sig")
        self.csvFile = CsvFile("tests/journal/data/transactions.csv", self.config)
        self.accounts = load_accounts(CsvFile("tests/journal/data/accounts.csv", self.config))
        self.accounts_by_name = dict([(a.identifier, a) for a in self.accounts])

    def test_normalize_txn(self):
        # Test that the transaction is balanced
        with self.assertRaises(bberr.TxnNotBalanced):
            verify_txn(Txn(1, [Posting(1, "2021-01-01", "Chequing", 1000), 
                               Posting(2, "2021-01-01", "Credit card", -999)]))

        with self.assertRaises(bberr.TxnNotBalanced):
            verify_txn(Txn(1, [Posting(1, "2021-01-01", "Chequing", 1000)]))

if __name__ == '__main__':
    unittest.main()