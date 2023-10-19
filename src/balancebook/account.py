import logging
from balancebook.csv import CsvFile, load_csv, write_csv
import balancebook.errors as bberr
from balancebook.errors import SourcePosition
from balancebook.i18n import I18n
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

def valid_account_type_number(number: int, type: AccountType) -> bool:
    """Check if the account number is valid for the account type"""
    if type == AccountType.ASSETS:
        return number >= 1000 and number <= 1999
    elif type == AccountType.LIABILITIES:
        return number >= 2000 and number <= 2999
    elif type == AccountType.EQUITY:
        return number >= 3000 and number <= 3999
    elif type == AccountType.INCOME:
        return number >= 4000 and number <= 4999
    elif type == AccountType.EXPENSES:
        return number >= 5000 and number <= 5999
    else:
        return False

class Account():
    def __init__(self, identifier: str, name: str, number: int, 
                 parent: 'Account', children: list['Account'] = None,
                 description: str = None, source: SourcePosition = None):
        self.identifier = identifier
        self.name = name if name else identifier
        self.number = number
        self.parent = parent
        self.children = children if children else []
        self.description = description
        self.source = source
        self.__account_type__ = None

    def __str__(self):
        return f"Account({self.identifier})"
    
    def __eq__(self, other: 'Account'):
        return self.number == other.number
    
    def __lt__(self, other: 'Account'):
        return self.number < other.number
    
    def __hash__(self):
        return hash(self.number)
    
    def account_type(self):
        if self.parent:
            return self.parent.account_type()
        else:
            return self.__account_type__

    def get_descendants(self) -> list['Account']:
        """Return a list of all children, grand-children, etc."""
        children = []
        for c in self.children:
            children.append(c)
            children.extend(c.get_descendants())
        return children
    
    def get_account_and_descendants(self) -> list['Account']:
        """Return this account, a list of all children, grand-children, etc."""
        ls = [self]
        ls.extend(self.get_descendants())
        return ls

    def depth(self) -> int:
        """Return the depth of the account in the hierarchy.
        Starts at 1 for the top accounts"""
        if self.parent:
            return self.parent.depth() + 1
        else:
            return 1

    def get_parents(self) -> list['Account']:
        """Return a list of all parents, grand-parents, etc."""
        if self.parent:
            ls = [self.parent]
            ls.extend(self.parent.get_parents())
            return ls
        else:
            return []

    def get_account_and_parents(self) -> list['Account']:
        """Return this account, a list of all parents, grand-parents, etc."""
        ls = [self]
        ls.extend(self.get_parents())
        return ls
    
    def get_leaves(self) -> list['Account']:
        """Return a list of all leaves of the tree"""
        leaves = []
        if len(self.children) == 0:
            leaves.append(self)
        else:
            for c in self.children:
                leaves.extend(c.get_leaves())
        return leaves

ChartOfAccounts = tuple[Account, Account, Account, Account, Account]

def max_depth(chart_of_accounts: ChartOfAccounts) -> int:
    """Return the maximum depth of the chart of accounts"""
    return max([l.depth() for a in chart_of_accounts for l in a.get_leaves()])

def load_accounts(csvFile: CsvFile, i18n: I18n = None) -> ChartOfAccounts:
    """Load accounts from the cvs file
    
    Verify the consistency of the accounts.
    """
    if i18n is None:
        i18n = I18n()

    csv_rows = load_csv(csvFile, [(i18n["Identifier"], "str", True, True), 
                                  (i18n["Name"], "str", False, False), 
                                  (i18n["Number"], "int", True, True), 
                                  (i18n["Parent"], "str", True, False),
                                  (i18n["Description"], "str", False, False)])
    accounts = []
    for row in csv_rows:
        source = row[5]
        identifier = row[0]
        parent = row[3]
        desc = row[4]
        name = row[1] if row[1] else row[0]
        acc = Account(identifier, name, row[2], parent, [], desc, source)
        accounts.append(acc)
    
    return build_chart_of_accounts(accounts, i18n)

def initialize_chart_of_accounts(i18n: I18n = None) -> ChartOfAccounts:
    if i18n is None:
        i18n = I18n()

    a = i18n[str(AccountType.ASSETS)]
    assets = Account(a, a, 1000, None)
    assets.__account_type__ = AccountType.ASSETS

    l = i18n[str(AccountType.LIABILITIES)]
    liabilities = Account(l, l, 2000, None)
    liabilities.__account_type__ = AccountType.LIABILITIES

    eq = i18n[str(AccountType.EQUITY)]
    equity = Account(eq, eq, 3000, None)
    equity.__account_type__ = AccountType.EQUITY

    i = i18n[str(AccountType.INCOME)]
    income = Account(i, i, 4000, None)
    income.__account_type__ = AccountType.INCOME

    e = i18n[str(AccountType.EXPENSES)]
    expenses = Account(e, e, 5000, None)
    expenses.__account_type__ = AccountType.EXPENSES

    return (assets, liabilities, equity, income, expenses)

def build_chart_of_accounts(accounts: list[Account], i18n: I18n = None) -> ChartOfAccounts:
    """Build the chart of accounts from the list of accounts.
    Returns new instances of the five top accounts

    - Set the parent of each account
    - Set the children of each account
    - Return the list of accounts sorted by account number"""
    if i18n is None:
        i18n = I18n()

    verify_accounts(accounts)

    chart_of_accounts = list(initialize_chart_of_accounts(i18n))

    # Check if the user redefined the reserved account identifiers
    # This allows for specifying the account number, account name, account description of the top accounts
    without_top_accounts: list[Account] = []
    for acc in accounts:
        top_account = False
        for i, t in enumerate(AccountType):
            if acc.identifier == str(t):
                if acc.parent:
                    raise bberr.ReservedAccountId(acc.identifier, acc.source)
                if not valid_account_type_number(acc.number, t):
                    raise bberr.AssetsNumberInvalid(acc.number, acc.source)
                acc.__account_type__ = t
                chart_of_accounts[i] = acc
                top_account = True
                break

        if not top_account:
            without_top_accounts.append(acc)

    # Double check top accounts numbers are not duplicated
    top_numbers = [a.number for a in chart_of_accounts]
    for n in top_numbers:
        for a in without_top_accounts:
            if a.number == n:
                raise bberr.AccountNumberReserved(a.identifier, a.source)

    with_top_accounts: list[Account] = chart_of_accounts.copy()
    with_top_accounts.extend(without_top_accounts)
    account_by_id_dict = dict([(a.identifier, a) for a in with_top_accounts])
    
    # Set the parent of each account
    for acc in without_top_accounts:
        if not acc.parent:
            raise bberr.ParentAccountNotSpecified(acc.identifier, acc.source)
        if acc.parent not in account_by_id_dict:
            raise bberr.ParentAccountNotFound(acc.parent, acc.source)
        acc.parent = account_by_id_dict[acc.parent]
    
    # Set the children of each account
    for acc in without_top_accounts:
        acc.parent.children.append(acc)

    # Verify we don't have a cycle in the account hierarchy
    for acc in with_top_accounts:
        if acc.parent:
            parent = acc.parent
            while parent:
                if parent == acc:
                    raise bberr.AccountCycle(acc.identifier, acc.source)
                parent = parent.parent

    # Since we don't have any cycles and all provided accounts have a specified parent,
    # we know that the top accounts are the roots of the tree

    # Sort children by account number
    for acc in with_top_accounts:
        acc.children.sort(key=lambda a: a.number)

    verify_chart_of_accounts(chart_of_accounts)
    return tuple(chart_of_accounts)

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
        accounts.sort(key=lambda a: a.number)
        duplicate_account_numbers: list[Account] = []
        for i in range(len(accounts)-1):
            if accounts[i].number == accounts[i+1].number:
                duplicate_account_numbers.append(accounts[i])
        # FIXME should return the complete list of duplicate account identifiers
        wrong = duplicate_account_numbers[0]
        raise bberr.AccountNumberNotUnique(wrong.number, wrong.source)

    # Verify the uniqueness of the account identifier
    account_identifiers = [a.identifier for a in accounts]
    if len(account_identifiers) != len(set(account_identifiers)):
        # Find the duplicate account identifiers
        accounts.sort(key=lambda a: a.identifier)
        duplicate_account_identifiers: list[Account] = []
        for i in range(len(accounts)-1):
            if accounts[i].identifier == accounts[i+1].identifier:
                duplicate_account_identifiers.append(accounts[i])
        # FIXME should return the complete list of duplicate account identifiers
        wrong = duplicate_account_identifiers[0]
        raise bberr.AccountIdentifierNotUnique(wrong.identifier, wrong.source)

def verify_chart_of_accounts(account: ChartOfAccounts) -> None:
    """Verify the consistency of the chart of accounts

    - Check that the account number is valid"""
    
    # Check asset account number is between 1000 and 1999
    for acc in account[0].get_descendants():
        if not valid_account_type_number(acc.number, AccountType.ASSETS):
            raise bberr.AssetsNumberInvalid(acc.number, acc.source)
    
    # Check liability account number is between 2000 and 2999
    for acc in account[1].get_descendants():
        if not valid_account_type_number(acc.number, AccountType.LIABILITIES):
            raise bberr.LiabilitiesNumberInvalid(acc.number, acc.source)
    
    # Check equity account number is between 3000 and 3999
    for acc in account[2].get_descendants():
        if not valid_account_type_number(acc.number, AccountType.EQUITY):
            raise bberr.EquityNumberInvalid(acc.number, acc.source)
    
    # Check income account number is between 4000 and 4999
    for acc in account[3].get_descendants():
        if not valid_account_type_number(acc.number, AccountType.INCOME):
            raise bberr.IncomeNumberInvalid(acc.number, acc.source)
    
    # Check expense account number is between 5000 and 5999
    for acc in account[4].get_descendants():
        if not valid_account_type_number(acc.number, AccountType.EXPENSES):
            raise bberr.ExpensesNumberInvalid(acc.number, acc.source)

def write_chart_of_accounts(chart_of_accounts: ChartOfAccounts, csvFile: CsvFile) -> None:
    """Write the chart of accounts to file."""
    accounts = write_chart_of_accounts_to_list(chart_of_accounts)
    write_csv(accounts, csvFile)

def write_accounts(accs: list[Account],csvFile: CsvFile, i18n: I18n) -> None:
    """Write accounts to file."""
    accounts = write_accounts_to_list(accs, i18n)
    write_csv(accounts, csvFile)

def write_chart_of_accounts_to_list(chart_of_accounts: ChartOfAccounts, i18n: I18n, header: bool = True) -> list[list[str]]:
    """Write the chart of accounts to a list of lists."""

    rows =[]
    if header:
        rows = [account_header]
    for a in chart_of_accounts:
        rows.extend(write_accounts_to_list(a.get_descendants(), i18n, False))
    return rows

account_header = ["Identifier", "Name", "Number", "Parent", "Description"]

def write_accounts_to_list(accs: list[Account], i18n: I18n, header: bool = True) -> list[list[str]]:
    """Write accounts to a list of lists."""

    rows =[]
    if header:
        rows.append([i18n[x] for x in account_header])
    for a in accs:
        parent = a.parent.identifier if a.parent else ""
        rows.append([a.identifier, a.name, a.number, parent, a.description])
    return rows