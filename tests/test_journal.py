import unittest
from datetime import date
from balancebook.journal.config import load_config
from balancebook.balance import Balance
from balancebook.journal.journal import Journal
from balancebook.transaction import Txn, Posting

class TestTxn(unittest.TestCase):
    def setUp(self) -> None:
        config = load_config("tests/journal/balancebook.en.yaml")     
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
        re_acc = self.journal.get_account_by_ident("Retirement")
        acc2 = self.journal.get_account_by_ident("Unrealized gains")
        self.journal.add_balances([Balance(date(2023, 9, 30), re_acc, 6200000)])
        txns = self.journal.auto_balance()
        self.assertEqual(len(txns), 1)
        t_target = Txn(None, [Posting(date(2023, 9, 30), re_acc, 400000),
                              Posting(date(2023, 9, 30), acc2, -400000)])
        self.assertTrue(txns[0].equivalent_to(t_target))

    def test_auto_balance_subaccounts(self):
        # Check that auto balance considers subaccounts
        re_acc = self.journal.get_account_by_ident("Chequing") # Subaccount = Project North
        acc2 = self.journal.get_account_by_ident("Salary")
        self.journal.add_balances([Balance(date(2023, 9, 30), re_acc, 500000)])
        self.journal.config.auto_balance.accounts[re_acc] = acc2
        txns = self.journal.auto_balance()
        self.assertEqual(len(txns), 1)
        t_target = Txn(None, [Posting(date(2023, 9, 30), re_acc, 200000),
                              Posting(date(2023, 9, 30), acc2, -200000)])
        self.assertTrue(txns[0].equivalent_to(t_target))         

    def test_auto_statement_date(self):
        cc = self.journal.get_account_by_ident("Credit card")
        me = self.journal.get_account_by_ident("Misc. expenses")
        new_txn = Txn(None, [Posting(date(2023, 8, 30), cc, -4700),
                             Posting(date(2023, 8, 30), me, 4700)])

        self.journal.add_txns([new_txn])

        ps = self.journal.auto_statement_date()
        
        self.assertEqual(len(ps), 1)
        self.assertTrue(ps[0].equivalent_to(Posting(date(2023, 8, 30), cc, -4700, statement_date=date(2023, 9, 1))))
        try:
            self.journal.verify_balances()
        except Exception as e:
            self.fail("verify_balances raised Exception: " + str(e))
        

if __name__ == '__main__':
    unittest.main()