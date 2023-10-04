import unittest

from balancebook.csv import CsvFile, CsvConfig
from balancebook.account import (Account, AccountType, load_accounts, verify_account,
                                      verify_accounts, write_accounts, account_type_from_str)
import balancebook.errors as bberr

class TestAccount(unittest.TestCase):
    def setUp(self) -> None:
        self.config = CsvConfig(column_separator=";", encoding="utf-8-sig")
        self.csvFile = CsvFile("tests/journal_en/account.csv", self.config)

    def test_load_accounts(self):
        try:
            load_accounts(self.csvFile)
        except Exception as e:
            self.fail("load_accounts() raised Exception: " + str(e))

    def test_normalize_account_number(self):
        # Test wrong numbers
        with self.assertRaises(bberr.AssetsNumberInvalid):
            verify_account(Account("a", "a", 0, AccountType.ASSETS))

        with self.assertRaises(bberr.AssetsNumberInvalid):
            verify_account(Account("a", "a", -1001, AccountType.ASSETS))

        with self.assertRaises(bberr.AssetsNumberInvalid):
            verify_account(Account("a", "a", 6001, AccountType.ASSETS))

        # Test that the number not corresponding to the account type is rejected
        for x in AccountType:
            for i in range(1, 5):
                if i != x.value:
                    with self.assertRaises(bberr.BBookException):
                        verify_account(Account("a", "a", 1000*i, x))

        # Test that the number corresponding to the account type is accepted
        try:
            verify_account(Account("a", "a", 1001, AccountType.ASSETS))
            verify_account(Account("a", "a", 2001, AccountType.LIABILITIES))
            verify_account(Account("a", "a", 3001, AccountType.EQUITY))
            verify_account(Account("a", "a", 4001, AccountType.INCOME))
            verify_account(Account("a", "a", 5001, AccountType.EXPENSES))
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
            verify_accounts([Account("a", "a1", 1001, AccountType.ASSETS),
                             Account("a", "a2", 1002, AccountType.ASSETS)])

        # Test that the account numbers must be unique
        with self.assertRaises(bberr.AccountNumberNotUnique):
            verify_accounts([Account("a1", "a1", 1001, AccountType.ASSETS),
                             Account("a2", "a2", 1001, AccountType.ASSETS)])

    def test_export_accounts(self):
        # Test that it does not raise an exception
        txns = load_accounts(self.csvFile)
        try:
            write_accounts(txns, CsvFile("tests/journal_en/export/accs.csv", self.config))
        except Exception as e:
            self.fail("write_accounts() raised Exception: " + str(e))

if __name__ == '__main__':
    unittest.main()