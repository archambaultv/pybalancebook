import unittest
from datetime import date
from balancebook.journal.config import load_config
from balancebook.balance import Balance
from balancebook.journal.journal import Journal
from balancebook.transaction import Txn, Posting

class TestTxn(unittest.TestCase):
    def setUp(self) -> None:
        config = load_config("tests/journal/balancebook.yaml")     
        self.journal = Journal(config)
        self.journal.load()

    def test_fiscal_year(self):
        self.assertEqual(2020, self.journal.fiscal_year(date(2020, 1, 1)))
        self.assertEqual(2034, self.journal.fiscal_year(date(2034, 1, 1)))
        self.assertEqual(1997, self.journal.fiscal_year(date(1997, 12, 12)))

        self.journal.config.data.first_fiscal_month = 4
        self.assertEqual(2020, self.journal.fiscal_year(date(2020, 3, 31)))
        self.assertEqual(2021, self.journal.fiscal_year(date(2020, 4, 1)))
        self.assertEqual(2021, self.journal.fiscal_year(date(2020, 12, 12)))

    def test_fiscal_month(self):
        self.assertEqual(1, self.journal.fiscal_month(date(2020, 1, 1)))
        self.assertEqual(6, self.journal.fiscal_month(date(2034, 6, 1)))
        self.assertEqual(12, self.journal.fiscal_month(date(1997, 12, 12)))

        self.journal.config.data.first_fiscal_month = 4
        self.assertEqual(12, self.journal.fiscal_month(date(2020, 3, 31)))
        self.assertEqual(1, self.journal.fiscal_month(date(2020, 4, 1)))
        self.assertEqual(9, self.journal.fiscal_month(date(2020, 12, 12)))

    def test_auto_balance(self):
        re_acc = self.journal.get_account_by_name()["Retirement"]
        acc2 = self.journal.get_account_by_name()["Unrealized gains"]
        self.journal.new_balances([Balance(date(2023, 9, 30), re_acc, 6200000)])
        txns = self.journal.auto_balance()
        self.assertEqual(len(txns), 1)
        t_target = Txn(None, [Posting(1, date(2023, 9, 30), re_acc, 400000),
                              Posting(2, date(2023, 9, 30), acc2, -400000)])
        self.assertTrue(txns[0].same_as(t_target))

    def test_auto_statement_date(self):
        cc = self.journal.get_account_by_name()["Credit card"]
        me = self.journal.get_account_by_name()["Misc. expenses"]
        new_txn = Txn(None, [Posting(1, date(2023, 8, 30), cc, -4700),
                             Posting(2, date(2023, 8, 30), me, 4700)])

        self.journal.new_txns([new_txn])

        ps = self.journal.auto_statement_date()
        
        # self.assertEqual(len(ps), 1)
        # self.assertTrue(ps[0].same_as(Posting(1, date(2023, 9, 1), cc, 4700)))
        self.journal.verify_balances()
        

if __name__ == '__main__':
    unittest.main()