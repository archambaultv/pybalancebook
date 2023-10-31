import logging
from datetime import date
from balancebook.csv import CsvFile, load_csv, write_csv, CsvColumn
import balancebook.errors as bberr
from balancebook.errors import SourcePosition
from balancebook.account import Account
from balancebook.i18n import I18n
from balancebook.amount import amount_to_str

logger = logging.getLogger(__name__)

class Balance():
    def __init__(self, date: date, account: Account, statement_balance: int,
                 source: SourcePosition = None):
        self.date = date
        self.account = account
        self.statement_balance = statement_balance
        self.source = source

    def __str__(self):
        return f"Balance({self.date}, {self.account}, {amount_to_str(self.statement_balance)})"
    
    def __eq__(self, other: 'Balance'):
        return (self.date == other.date and 
                self.account == other.account and 
                self.statement_balance == other.statement_balance)
    
from functools import lru_cache

def load_balances(csvFile: CsvFile, accounts_by_number: dict[str,Account], i18n: I18n = None) -> list[Balance]:
    """Load balances from the csv file
    
    Verify the consistency of the balances"""

    if i18n is None:
        i18n = I18n()

    date_i18n = i18n["Date"]
    account_i18n = i18n["Account"]
    statement_balance_i18n = i18n["Statement balance"]
    
    csv_rows = load_csv(csvFile, [CsvColumn(date_i18n, "date", True, True), 
                                  CsvColumn(account_i18n, "str", True, True), 
                                  CsvColumn(statement_balance_i18n, "amount", True, True)],
                                  warn_extra_columns=True)
    balances = []
    for row, source in csv_rows:
        if row[account_i18n] not in accounts_by_number:
            raise bberr.UnknownAccount(row[account_i18n], source)
        balances.append(Balance(row[date_i18n], 
                                accounts_by_number[row[account_i18n]], 
                                row[statement_balance_i18n], source))

    verify_balances(balances)

    return balances

def verify_balances(bals: list[Balance]) -> None:
    """Verify the consistency of the balances"""
    
    # Check we have only one balance per account per date
    seen = set()
    for b in bals:
        key = (b.date, b.account.number)
        if key in seen:
            raise bberr.DuplicateBalance(b.date, b.account.identifier, b.source)
        seen.add(key)

def write_balances(bals: list[Balance], csvFile: CsvFile, i18n: I18n) -> None:
    """Write balances to file."""
    data = write_balances_to_list(bals, i18n, csvFile.config.decimal_separator)
    write_csv(data, csvFile)

def write_balances_to_list(bals: list[Balance], i18n: I18n, decimal_separator = ".") -> list[list[str]]:
    rows = []
    rows.append([i18n[x] for x in ["Date","Account","Statement balance"]])
    for b in bals:
       rows.append([b.date, b.account.identifier, amount_to_str(b.statement_balance, decimal_separator)])
    return rows

def balance_by_account(bals: list[Balance]) -> dict[int, list[Balance]]:
    """Return a dictionary of balances by account number."""
    balance_by_account: dict[int, list[Balance]] = {}
    if len(bals) == 0:
        return balance_by_account
    
    bals = sorted(bals, key=lambda x: (x.account.number, x.date))
    b: Balance = bals[0]
    balance_by_account[b.account.number] = [b]
    for i in range(len(bals) - 1):
        nextB = bals[i+1]
        previous: Account = bals[i].account
        next: Account = nextB.account
        if previous != next:
            balance_by_account[next.number] = [nextB]
        else:
            balance_by_account[next.number].append(nextB)
    return balance_by_account