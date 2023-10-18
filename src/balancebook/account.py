import logging
from balancebook.csv import CsvFile, load_csv, write_csv
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

def account_type_from_str(s: str, source: SourcePosition = None) -> AccountType:
    # Check that the account type is valid
    if s == str(AccountType.ASSETS):
        return AccountType.ASSETS
    elif s == str(AccountType.LIABILITIES):
        return AccountType.LIABILITIES
    elif s == str(AccountType.EQUITY):
        return AccountType.EQUITY
    elif s == str(AccountType.INCOME):
        return AccountType.INCOME
    elif s == str(AccountType.EXPENSES):
        return AccountType.EXPENSES
    else:
        raise bberr.AccountTypeUnknown(s, source)
    
class Account():
    def __init__(self, identifier: str, name: str, number: int, 
                 type: AccountType, group: str = None, subgroup: str = None, 
                 description: str = None, source: SourcePosition = None):
        self.identifier = identifier
        self.name = name if name else identifier
        self.number = number
        self.type = type
        self.group = group
        self.subgroup = subgroup
        self.description = description
        self.source = source

    def __str__(self):
        return f"Account({self.identifier})"
    
    def __eq__(self, other: 'Account'):
        return self.number == other.number
    
    def __lt__(self, other: 'Account'):
        return self.number < other.number
    
    def __hash__(self):
        return hash(self.number)

def load_accounts(csvFile: CsvFile) -> list[Account]:
    """Load accounts from the cvs file
    
    Verify the consistency of the accounts.
    """
    csv_rows = load_csv(csvFile, [("Identifier", "str", True, True), 
                                  ("Name", "str", False, False), 
                                  ("Number", "int", True, True), 
                                  ("Type", "str", True, True), ("Group", "str", False, False), 
                                  ("Subgroup", "str", False, False), 
                                  ("Description", "str", False, False)])
    accounts = []
    for row in csv_rows:
        source = row[7]
        acc_type = account_type_from_str(row[3], source)
        name = row[1] if row[1] else row[0]
        acc = Account(row[0], name, row[2], acc_type, row[4], row[5], row[6], source)
        verify_account(acc)
        accounts.append(acc)

    verify_accounts(accounts)    
    
    return accounts
    
def verify_accounts(accounts: list[Account]) -> None:
    """Verify the consistency of the accounts
    
    - Verify the uniqueness of the account number
    - Verify the uniqueness of the account identifier"""

    if len(accounts) == 0:
        return

    # Verify the uniqueness of the account number
    account_numbers = [a.number for a in accounts]
    if len(account_numbers) != len(set(account_numbers)):
        # Find the duplicate account numbers
        account_numbers.sort()
        duplicate_account_numbers = []
        for i in range(len(account_numbers)-1):
            if account_numbers[i] == account_numbers[i+1]:
                duplicate_account_numbers.append(account_numbers[i])
        if accounts[0].source:
            src = SourcePosition(accounts[0].source.file, None, None)
        else:
            src = None
        raise bberr.AccountNumberNotUnique(duplicate_account_numbers, src)
    
    # Verify the uniqueness of the account identifier
    account_identifiers = [a.identifier for a in accounts]
    if len(account_identifiers) != len(set(account_identifiers)):
        # Find the duplicate account identifiers
        account_identifiers.sort()
        duplicate_account_identifiers = []
        for i in range(len(account_identifiers)-1):
            if account_identifiers[i] == account_identifiers[i+1]:
                duplicate_account_identifiers.append(account_identifiers[i])
        if accounts[0].source:
            src = SourcePosition(accounts[0].source.file, None, None)
        else:
            src = None
        raise bberr.AccountIdentifierNotUnique(duplicate_account_identifiers, src)

def verify_account(account: Account) -> None:
    """Normalize the account data from str to the appropriate type and verify the consistency of the account
    
    - Check that the account number is valid"""
    
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

def write_accounts(accs: list[Account],csvFile: CsvFile) -> None:
    """Write accounts to file."""
    accounts = write_accounts_to_list(accs)
    write_csv(accounts, csvFile)

def write_accounts_to_list(accs: list[Account]) -> list[list[str]]:
    """Write accounts to a list of lists."""

    rows = [["Identifier", "Name", "Number", "Type", "Group", "Subgroup", "Description"]]
    for a in accs:
        rows.append([a.identifier, a.name, a.number, str(a.type), a.group, a.subgroup, a.description])
    return rows