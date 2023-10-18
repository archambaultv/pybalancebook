import unittest

from balancebook.csv import CsvFile, CsvConfig
from balancebook.account import (Account, AccountType, load_accounts, build_chart_of_accounts,
                                      verify_accounts, account_type_from_str, max_depth)
import balancebook.errors as bberr

class TestAccount(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", encoding="utf-8-sig")
        self.csvFile = CsvFile("tests/journal/data/accounts.csv", self.config)

    def test_load_accounts(self):
        coa = load_accounts(self.csvFile)
        self.assertEqual(max_depth(coa), 3)

    def test_normalize_account_number(self):
        # Test wrong numbers
        with self.assertRaises(bberr.AssetsNumberInvalid):
            build_chart_of_accounts([Account("a", "a", 0, str(AccountType.ASSETS))])

        with self.assertRaises(bberr.AssetsNumberInvalid):
            build_chart_of_accounts([Account("a", "a", -1001, str(AccountType.ASSETS))])

        with self.assertRaises(bberr.AssetsNumberInvalid):
            build_chart_of_accounts([Account("a", "a", 6001, str(AccountType.ASSETS))])

        # Test that the number not corresponding to the account type is rejected
        for x in AccountType:
            for i in range(1, 5):
                if i != x.value:
                    with self.assertRaises(bberr.BBookException):
                        build_chart_of_accounts([Account("a", "a", 1000*i, str(x))])

        # Test that the number corresponding to the account type is accepted
        try:
            build_chart_of_accounts([Account("a", "a", 1001, str(AccountType.ASSETS))])
            build_chart_of_accounts([Account("a", "a", 2001, str(AccountType.LIABILITIES))])
            build_chart_of_accounts([Account("a", "a", 3001, str(AccountType.EQUITY))])
            build_chart_of_accounts([Account("a", "a", 4001, str(AccountType.INCOME))])
            build_chart_of_accounts([Account("a", "a", 5001, str(AccountType.EXPENSES))])
        except Exception as e:
            self.fail("verify_account() raised Exception: " + str(e))
        

    def test_normalize_account_type(self):
        with self.assertRaises(bberr.AccountTypeUnknown):
            account_type_from_str("hello")

        with self.assertRaises(bberr.AccountTypeUnknown):
            account_type_from_str("")

    def test_verify_accounts(self):
        # Test that the account identifiers must be unique
        with self.assertRaises(bberr.AccountIdentifierNotUnique):
            verify_accounts([Account("a", "a1", 1001, str(AccountType.ASSETS)),
                             Account("a", "a2", 1002, str(AccountType.ASSETS))])

        # Test that the account numbers must be unique
        with self.assertRaises(bberr.AccountNumberNotUnique):
            verify_accounts([Account("a1", "a1", 1001, str(AccountType.ASSETS)),
                             Account("a2", "a2", 1001, str(AccountType.ASSETS))])


if __name__ == '__main__':
    unittest.main()