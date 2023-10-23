import unittest
from datetime import date
from balancebook.transaction import Txn, Posting
import balancebook.errors as bberr

class TestTxn(unittest.TestCase):
    def test_daily_balanced(self):
        # Test that the transaction is balanced
        self.assertFalse(Txn(1, [Posting(date(2021,1,1), "Chequing", 1000), 
                                 Posting(date(2021,1,1), "Credit card", -999)]).is_daily_balanced())

        self.assertFalse(Txn(1, [Posting(date(2021,1,1), "Chequing", 1000)]).is_daily_balanced())

    def test_single_day(self):
        self.assertFalse(Txn(1, [Posting(date(2021,1,1), "Chequing", 1000), 
                                 Posting(date(2021,1,2), "Credit card", -1000)]).is_single_day())

if __name__ == '__main__':
    unittest.main()