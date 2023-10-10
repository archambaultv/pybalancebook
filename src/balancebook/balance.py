import logging
from datetime import date
from balancebook.csv import CsvFile, load_csv, write_csv
import balancebook.errors as bberr
from balancebook.errors import SourcePosition
from balancebook.account import Account
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
    
def load_balances(csvFile: CsvFile, accounts_by_number: dict[str,Account]) -> list[Balance]:
    """Load balances from the csv file
    
    Verify the consistency of the balances"""

    csv_rows = load_csv(csvFile, [("Date", "date", True, True), 
                                  ("Account", "str", True, True), 
                                  ("Statement balance", "amount", True, True)])
    balances = []
    for row in csv_rows:
        source = row[3]
        if row[1] not in accounts_by_number:
            raise bberr.UnknownAccount(row[1], source)
        balances.append(Balance(row[0], accounts_by_number[row[1]], row[2], source))

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

def write_balances(bals: list[Balance], csvFile: CsvFile) -> None:
    """Write balances to file."""
    data = write_balances_to_list(bals, csvFile.config.decimal_separator)
    write_csv(data, csvFile)

def write_balances_to_list(bals: list[Balance], decimal_separator = ".") -> list[list[str]]:
    rows = [["Date","Account","Statement balance"]]
    for b in bals:
       rows.append([b.date, b.account.identifier, amount_to_str(b.statement_balance, decimal_separator)])
    return rows

def balance_by_number(bals: list[Balance]) -> dict[int, list[Balance]]:
    """Return a dictionary of balances by account number."""
    balance_by_number: dict[int, list[Balance]] = {}
    if len(bals) == 0:
        return balance_by_number
    else:
        bals = sorted(bals, key=lambda x: (x.account.number, x.date))
        b: Balance = bals[0]
        balance_by_number[b.account.number] = [b]
        for i in range(len(bals) - 1):
            previous: Account = bals[i].account
            next: Account = bals[i+1].account
            if previous.number != next.number:
                balance_by_number[next.number] = [next]
            else:
                balance_by_number[next.number].append(next)