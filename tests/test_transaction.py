import unittest
from datetime import date
from balancebook.csv import CsvConfig, CsvFile
from balancebook.account import load_accounts
from balancebook.transaction import verify_txn, Txn, Posting, write_txns
import balancebook.errors as bberr

class TestTxn(unittest.TestCase):
    def test_normalize_txn(self):
        # Test that the transaction is balanced
        with self.assertRaises(bberr.TxnNotBalanced):
            verify_txn(Txn(1, [Posting("2021-01-01", "Chequing", 1000), 
                               Posting("2021-01-01", "Credit card", -999)]))

        with self.assertRaises(bberr.TxnNotBalanced):
            verify_txn(Txn(1, [Posting("2021-01-01", "Chequing", 1000)]))

if __name__ == '__main__':
    unittest.main()