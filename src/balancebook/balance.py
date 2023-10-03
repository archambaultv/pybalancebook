import csv
import os
import logging
from datetime import date
from balancebook.csv import CsvFile, read_date
import balancebook.errors as bberr
from balancebook.errors import SourcePosition
from balancebook.account import Account
from balancebook.amount import any_to_amount, amount_to_str

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
    
def load_balances(csvFile: CsvFile) -> list[Balance]:
    """Load balances from the csv file
    
    All Balance fields will be of type str.
    Does not verify the consistency of the balances"""

    # if file does not exist, return an empty list
    if not os.path.exists(csvFile.path):
        logger.warn("Balance file ${file} does not exist", file=csvFile.path)
        return []

    csv_conf = csvFile.config
    line = 1
    with open(csvFile.path, encoding=csv_conf.encoding) as bals_file:
        for _ in range(csv_conf.skip_X_lines):
            line += 1
            next(bals_file)
    
        rows = csv.DictReader(bals_file,
                        delimiter=csv_conf.column_separator,
                        quotechar=csv_conf.quotechar)
        # Check that the header is correct
        header = ["Date","Account","Statement balance"]
        for h in header:
            if h not in rows.fieldnames:
                raise bberr.MissingHeader(h, SourcePosition(csvFile.path, line, None))
            
        line += 1 # header line
        bals = []
        for r in rows:
            date = r["Date"].strip()
            account = r["Account"].strip()
            statement_balance = r["Statement balance"].strip()
            bals.append(Balance(date, account, statement_balance, SourcePosition(csvFile.path, line, None)))
            line += 1
            
        return bals

def normalize_balance(balance: Balance, accounts: dict[str,Account],
                      decimal_sep: str = ".", currency_sign: str = "$", thousands_sep: str = " ") -> None:
    """Normalize a balance
    
    - Normalize the balance data from str to the appropriate type
    - Convert date to date object if needed
    - Verify that the account exists and change it to the account object
    - Convert the statement balance using float_to_amount"""

    if isinstance(balance.date, str):
        balance.date = read_date(balance.date, balance.source)
    if balance.account not in accounts:
        raise bberr.UnknownAccount(balance.account)
    balance.account = accounts[balance.account]
    balance.statement_balance = any_to_amount(balance.statement_balance, 
                                              decimal_sep, currency_sign, thousands_sep,
                                              balance.source)

def load_and_normalize_balances(csvFile: CsvFile, accounts_by_id: dict[str,Account]) -> list[Balance]:
    """Load balances from the yaml file
    
    Verify the consistency of the balances"""
    balances = load_balances(csvFile)
    for b in balances:
        normalize_balance(b, accounts_by_id, 
                          csvFile.config.decimal_separator, 
                          csvFile.config.currency_sign, 
                          csvFile.config.thousands_separator)
    return balances

def sort_balances(bals: list[Balance]) -> None:
    """Sort balances by date and account number"""
    bals.sort(key=lambda x: (x.date, x.account.number))

def write_balances(bals: list[Balance], csvFile: CsvFile) -> None:
    """Write balances to file."""

    sort_balances(bals)
    csv_conf = csvFile.config
    with open(csvFile.path, 'w', encoding=csv_conf.encoding) as xlfile:
        writer = csv.writer(xlfile, delimiter=csv_conf.column_separator,
                          quotechar=csv_conf.quotechar, quoting=csv.QUOTE_MINIMAL)
        header = ["Date","Account","Statement balance"]
        writer.writerow(header)
        for b in bals:
            writer.writerow([b.date, b.account.identifier, amount_to_str(b.statement_balance, csv_conf.decimal_separator)])