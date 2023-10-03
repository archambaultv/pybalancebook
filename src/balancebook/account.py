import csv
import os
import logging
from balancebook.csv import CsvFile
import balancebook.errors as bberr
from balancebook.errors import SourcePosition
from enum import Enum

logger = logging.getLogger(__name__)

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
                 description: str = None, source: SourcePosition = None):
        self.identifier = identifier
        self.name = name
        self.number = number
        self.type = type
        self.group = group
        self.subgroup = subgroup
        self.description = description
        self.source = source

    def __str__(self):
        return f"Account({self.identifier})"

def load_accounts(csvFile: CsvFile) -> list[Account]:
    """Load accounts from the cvs file
    
    All Account fields will be of type str.
    Does not verify the consistency of the accounts.
    """
    # if file does not exist, return an empty list
    if not os.path.exists(csvFile.path):
        logger.warn("Account file ${file} does not exist", file=csvFile.path)
        return []
    
    csv_conf = csvFile.config
    line = 1
    with open(csvFile.path, encoding=csv_conf.encoding) as account_file:
        for _ in range(csv_conf.skip_X_lines):
            line += 1
            next(account_file)

        rows = csv.DictReader(account_file,
                        delimiter=csv_conf.column_separator,
                        quotechar=csv_conf.quotechar)
        # Check that the header is correct
        header = ["Identifier", "Name", "Number", "Type"]
        for h in header:
            if h not in rows.fieldnames:
                raise bberr.MissingHeader(h, SourcePosition(csvFile.path, line, None))

        line += 1 # header line
        account = []
        for r in rows:
            id = r["Identifier"].strip()
            name = r["Name"].strip()
            number = r["Number"].strip()
            type = r["Type"].strip()
            if "Group" in r and r["Group"]:
                group = r["Group"].strip()
            else:
                group = None
            if "Subgroup" in r and r["Subgroup"]:
                subgroup = r["Subgroup"].strip()
            else:
                subgroup = None
            if "Description" in r and r["Description"]:
                desc = r["Description"].strip()
            else:
                desc = None
            source = SourcePosition(csvFile.path, line, None)
            account.append(Account(id, name, number, type, group, subgroup, desc, source))
            line += 1
        return account
    
def load_and_normalize_accounts(csvFile: CsvFile) -> list[Account]:
    """Load accounts from the csv file
    
    - Normalize the account data from str to the appropriate type
    - Verify the consistency of the accounts"""
    accounts = load_accounts(csvFile)
    for a in accounts:
        normalize_account(a)

    verify_accounts(accounts)

    return accounts
    
def verify_accounts(accounts: list[Account]) -> None:
    """Verify the consistency of the accounts
    
    - Verify the uniqueness of the account number
    - Verify the uniqueness of the account identifier"""

    # Verify the uniqueness of the account number
    account_numbers = [a.number for a in accounts]
    if len(account_numbers) != len(set(account_numbers)):
        # Find the duplicate account numbers
        account_numbers.sort()
        duplicate_account_numbers = []
        for i in range(len(account_numbers)-1):
            if account_numbers[i] == account_numbers[i+1]:
                duplicate_account_numbers.append(account_numbers[i])
        raise bberr.AccountNumberNotUnique(duplicate_account_numbers)
    
    # Verify the uniqueness of the account identifier
    account_identifiers = [a.identifier for a in accounts]
    if len(account_identifiers) != len(set(account_identifiers)):
        # Find the duplicate account identifiers
        account_identifiers.sort()
        duplicate_account_identifiers = []
        for i in range(len(account_identifiers)-1):
            if account_identifiers[i] == account_identifiers[i+1]:
                duplicate_account_identifiers.append(account_identifiers[i])
        raise bberr.AccountIdentifierNotUnique(duplicate_account_identifiers)

def normalize_account(account: Account) -> None:
    """Normalize the account data from str to the appropriate type and verify the consistency of the account
    
    - Check that the account identifier is not empty
    - Check that the account name is not empty
    - Check that the account type is valid
    - Check that the account number is valid"""
        
    # Check that the account identifier is not empty
    if not account.identifier:
        raise bberr.AccountIdentifierEmpty(account.source)
    
    # Check that the account name is not empty
    if not account.name:
        raise bberr.AccountNameEmpty(account.source)

    # Check that the account number is not empty and is an integer
    if account.number is None:
        raise bberr.AccountNumberEmpty(account.source)
    try:
        account.number = int(account.number)
    except ValueError:
        raise bberr.AccountNumberNotInteger(account.source)

    # Check that the account type is valid
    if account.type == str(AccountType.ASSETS):
        account.type = AccountType.ASSETS
    elif account.type == str(AccountType.LIABILITIES):
        account.type = AccountType.LIABILITIES
    elif account.type == str(AccountType.EQUITY):
        account.type = AccountType.EQUITY
    elif account.type == str(AccountType.INCOME):
        account.type = AccountType.INCOME
    elif account.type == str(AccountType.EXPENSES):
        account.type = AccountType.EXPENSES
    else:
        raise bberr.AccountTypeUnknown(account.type, account.source)
    
    # Check asset account number is between 1000 and 1999
    if account.type == AccountType.ASSETS and (account.number < 1000 or account.number > 1999):
        raise bberr.AssetsNumberInvalid(account.number, account.source)
    
    # Check liability account number is between 2000 and 2999
    if account.type == AccountType.LIABILITIES and (account.number < 2000 or account.number > 2999):
        raise bberr.LiabilitiesNumberInvalid(account.number, account.source)
    
    # Check equity account number is between 3000 and 3999
    if account.type == AccountType.EQUITY and (account.number < 3000 or account.number > 3999):
        raise bberr.EquityNumberInvalid(account.number, account.source)
    
    # Check income account number is between 4000 and 4999
    if account.type == AccountType.INCOME and (account.number < 4000 or account.number > 4999):
        raise bberr.IncomeNumberInvalid(account.number, account.source)
    
    # Check expense account number is between 5000 and 5999
    if account.type == AccountType.EXPENSES and (account.number < 5000 or account.number > 5999):
        raise bberr.ExpensesNumberInvalid(account.number, account.source)
    
def sort_accs(accs: list[Account]) -> None:
    """Sort accounts by number."""
    accs.sort(key=lambda x: x.number)

def write_accounts(accs: list[Account],csvFile: CsvFile) -> None:
    """Write accounts to file."""

    sort_accs(accs)
    csv_conf = csvFile.config
    with open(csvFile.path, 'w', encoding=csv_conf.encoding) as xlfile:
        writer = csv.writer(xlfile, delimiter=csv_conf.column_separator,
                          quotechar=csv_conf.quotechar, quoting=csv.QUOTE_MINIMAL)
        header = ["Identifier", "Name", "Number", "Type", 
                  "Group", "Subgroup", "Description"]
        writer.writerow(header)
        for a in accs:
            writer.writerow([a.identifier, a.name, a.number, str(a.type), a.group, a.subgroup, a.description])