import csv
import os
from balancebook.terminal import fwarning
from balancebook.csv import CsvFile
from balancebook.i18n import I18n, i18n_en
from enum import Enum

# Enum for the five types of accounts
class AccountType(Enum):
    ASSETS = 1
    LIABILITIES = 2
    EQUITY = 3
    INCOME = 4
    EXPENSES = 5

    def __str__(self):
        # Capitalize the first letter
        return self.name[0] + self.name[1:].lower()

class Account():
    def __init__(self, identifier: str, name: str, number: int, 
                 type: AccountType, group: str = None, subgroup: str = None, 
                 description: str = None):
        self.identifier = identifier
        self.name = name
        self.number = number
        self.type = type
        self.group = group
        self.subgroup = subgroup
        self.description = description

    def __str__(self):
        return f"Account({self.identifier})"

def load_accounts(csvFile: CsvFile, i18n: I18n = i18n_en) -> list[Account]:
    """Load accounts from the cvs file
    
    All Account fields will be of type str.
    Does not verify the consistency of the accounts.
    """
    # if file does not exist, return an empty list
    if not os.path.exists(csvFile.path):
        # print warning
        print(fwarning(i18n.t("Account file ${file} does not exist", file=csvFile.path)))
        return []
    
    csv_conf = csvFile.config
    with open(csvFile.path, encoding=csv_conf.encoding) as account_file:
        for _ in range(csv_conf.skip_X_lines):
            next(account_file)

        rows = csv.DictReader(account_file,
                        delimiter=csv_conf.column_separator,
                        quotechar=csv_conf.quotechar)
        account = []
        for r in rows:
            id = r[i18n["Identifier"]].strip()
            name = r[i18n["Name"]].strip()
            number = r[i18n["Number"]].strip()
            type = r[i18n["Type"]].strip()
            if i18n["Group"] in r and r[i18n["Group"]]:
                group = r[i18n["Group"]].strip()
            else:
                group = None
            if i18n["Subgroup"] in r and r[i18n["Subgroup"]]:
                subgroup = r[i18n["Subgroup"]].strip()
            else:
                subgroup = None
            if i18n["Description"] in r and r[i18n["Description"]]:
                desc = r[i18n["Description"]].strip()
            else:
                desc = None
            account.append(Account(id, name, number, type, group, subgroup, desc))
        return account
    
def load_and_normalize_accounts(csvFile: CsvFile, i18n: I18n = i18n_en) -> list[Account]:
    """Load accounts from the csv file
    
    - Normalize the account data from str to the appropriate type
    - Verify the consistency of the accounts"""
    accounts = load_accounts(csvFile, i18n)
    for a in accounts:
        normalize_account(a, i18n)

    verify_accounts(accounts)

    return accounts

def verify_accounts(accounts: list[Account], i18n: I18n = i18n_en) -> None:
    """Verify the consistency of the accounts
    
    - Verify the uniqueness of the account number
    - Verify the uniqueness of the account identifier"""

    # Verify the uniqueness of the account number
    account_numbers = [a.number for a in accounts]
    if len(account_numbers) != len(set(account_numbers)):
        raise Exception(i18n["The account numbers must be unique"])
    
    # Verify the uniqueness of the account identifier
    account_identifiers = [a.identifier for a in accounts]
    if len(account_identifiers) != len(set(account_identifiers)):
        raise Exception(i18n["The account identifiers must be unique"])

def normalize_account(account: Account, i18n: I18n = i18n_en) -> None:
    """Normalize the account data from str to the appropriate type and verify the consistency of the account
    
    - Check that the account identifier is not empty
    - Check that the account name is not empty
    - Check that the account type is valid
    - Check that the account number is valid"""
        
    # Check that the account identifier is not empty
    if not account.identifier:
        raise Exception(i18n["The account identifier cannot be empty"])
    
    # Check that the account name is not empty
    if not account.name:
        raise Exception(i18n["The account name cannot be empty"])

    # Check that the account number is not empty and is an integer
    if not account.number:
        raise Exception(i18n["The account number cannot be empty"])
    try:
        account.number = int(account.number)
    except ValueError:
        raise Exception(i18n["The account number must be an integer"])

    # Check that the account type is valid
    if account.type == i18n[str(AccountType.ASSETS)]:
        account.type = AccountType.ASSETS
    elif account.type == i18n[str(AccountType.LIABILITIES)]:
        account.type = AccountType.LIABILITIES
    elif account.type == i18n[str(AccountType.EQUITY)]:
        account.type = AccountType.EQUITY
    elif account.type == i18n[str(AccountType.INCOME)]:
        account.type = AccountType.INCOME
    elif account.type == i18n[str(AccountType.EXPENSES)]:
        account.type = AccountType.EXPENSES
    else:
        raise Exception(i18n.t("Unknown account type: ${accType}", accType=account.type))
    
    # Check asset account number is between 1000 and 1999
    if account.type == AccountType.ASSETS and (account.number < 1000 or account.number > 1999):
        raise Exception(i18n.t("Invalid account number: ${number}. Must be between 1000 and 1999 for asset accounts.", number=account.number))
    
    # Check liability account number is between 2000 and 2999
    if account.type == AccountType.LIABILITIES and (account.number < 2000 or account.number > 2999):
        raise Exception(i18n.t("Invalid account number: {number}. Must be between 2000 and 2999 for liability accounts.", number=account.number))
    
    # Check equity account number is between 3000 and 3999
    if account.type == AccountType.EQUITY and (account.number < 3000 or account.number > 3999):
        raise Exception(i18n.t("Invalid account number: {number}. Must be between 3000 and 3999 for equity accounts.", number=account.number))
    
    # Check income account number is between 4000 and 4999
    if account.type == AccountType.INCOME and (account.number < 4000 or account.number > 4999):
        raise Exception(i18n.t("Invalid account number: {number}. Must be between 4000 and 4999 for income accounts.", number=account.number))
    
    # Check expense account number is between 5000 and 5999
    if account.type == AccountType.EXPENSES and (account.number < 5000 or account.number > 5999):
        raise Exception(i18n.t("Invalid account number: {number}. Must be between 5000 and 5999 for expense accounts.", number=account.number))
    
def sort_accs(accs: list[Account]) -> None:
    """Sort accounts by number."""
    accs.sort(key=lambda x: x.number)

def write_accounts(accs: list[Account],csvFile: CsvFile, i18n: I18n = i18n_en) -> None:
    """Write accounts to file."""

    sort_accs(accs)
    csv_conf = csvFile.config
    with open(csvFile.path, 'w', encoding=csv_conf.encoding) as xlfile:
        writer = csv.writer(xlfile, delimiter=csv_conf.column_separator,
                          quotechar=csv_conf.quotechar, quoting=csv.QUOTE_MINIMAL)
        header = [i18n["Identifier"], i18n["Name"], i18n["Number"], i18n["Type"], 
                  i18n["Group"], i18n["Subgroup"], i18n["Description"]]
        writer.writerow(header)
        for a in accs:
            writer.writerow([a.identifier, a.name, a.number, i18n[str(a.type)], a.group, a.subgroup, a.description])