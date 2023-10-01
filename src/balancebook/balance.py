import csv
import os
from datetime import date
from balancebook.terminal import fwarning
from balancebook.csv import CsvFile
from balancebook.i18n import I18n, i18n_en
from balancebook.account import Account
from balancebook.amount import any_to_amount, amount_to_str
from balancebook.transaction import balance, balancedict, Txn, compute_account_balance_from_txns

class Balance():
    def __init__(self, date: date, account: Account, statement_balance: int):
        self.date = date
        self.account = account
        self.statement_balance = statement_balance

    def __str__(self):
        return f"Balance({self.date}, {self.account}, {amount_to_str(self.statement_balance)})"
    
def load_balances(csvFile: CsvFile, i18n: I18n = i18n_en) -> list[Balance]:
    """Load balances from the csv file
    
    All Balance fields will be of type str.
    Does not verify the consistency of the balances"""

    # if file does not exist, return an empty list
    if not os.path.exists(csvFile.path):
        print(fwarning(i18n.t("Balance file ${file} does not exist", file=csvFile.path)))
        return []

    csv_conf = csvFile.config
    with open(csvFile.path, encoding=csv_conf.encoding) as bals_file:
        for _ in range(csv_conf.skip_X_lines):
            next(bals_file)
    
        rows = csv.DictReader(bals_file,
                        delimiter=csv_conf.column_separator,
                        quotechar=csv_conf.quotechar)
        bals = []
        for r in rows:
            date = r[i18n["Date"]].strip()
            account = r[i18n["Account"]].strip()
            statement_balance = r[i18n["Statement balance"]].strip()
            bals.append(Balance(date, account, statement_balance))
            
        return bals

def normalize_balance(balance: Balance, accounts: dict[str,Account],i18n: I18n = i18n_en,
                      decimal_sep: str = ".", currency_sign: str = "$", thousands_sep: str = " ") -> None:
    """Normalize a balance
    
    - Normalize the balance data from str to the appropriate type
    - Convert date to date object if needed
    - Verify that the account exists and change it to the account object
    - Convert the statement balance using float_to_amount"""

    if isinstance(balance.date, str):
        balance.date = date.fromisoformat(balance.date)
    if balance.account not in accounts:
        raise ValueError(i18n.t("Unknown account ${account}", account=balance.account))
    balance.account = accounts[balance.account]
    balance.statement_balance = any_to_amount(balance.statement_balance, decimal_sep, currency_sign, thousands_sep)

def load_and_normalize_balances(csvFile: CsvFile, accounts_by_id: dict[str,Account], i18n: I18n = i18n_en) -> list[Balance]:
    """Load balances from the yaml file
    
    Verify the consistency of the balances"""
    balances = load_balances(csvFile, i18n)
    for b in balances:
        normalize_balance(b, accounts_by_id, i18n, csvFile.config.decimal_separator)
    return balances

def verify_balances(balances: list[Balance], balanceDict: balancedict, i18n: I18n = i18n_en) -> None:
    """ Verify that the balances are consistent with the transactions"""

    for b in balances:
        txnAmount = balance(b.account, b.date, balanceDict)
        if txnAmount != b.statement_balance:
            raise Exception(i18n.t("Balance assertion of ${balAmount} for " 
                                   "${account} on ${date} does not match the balance ${txnAmount} of the transactions. "
                                   "Difference is ${difference}", account=b.account, date=b.date,balAmount=b.statement_balance, txnAmount=amount_to_str(txnAmount), difference=amount_to_str(b.statement_balance - txnAmount)))
        
def verify_balances_txns(balances: list[Balance], txns: list[Txn], statement_balance: bool = False, i18n: I18n = i18n_en) -> None:
    verify_balances(balances, compute_account_balance_from_txns(txns, statement_balance=statement_balance), i18n)

def sort_balances(bals: list[Balance]) -> None:
    """Sort balances by date and account number"""
    bals.sort(key=lambda x: (x.date, x.account.number))

def write_balances(bals: list[Balance], csvFile: CsvFile, i18n: I18n = i18n_en) -> None:
    """Write balances to file."""

    sort_balances(bals)
    csv_conf = csvFile.config
    with open(csvFile.path, 'w', encoding=csv_conf.encoding) as xlfile:
        writer = csv.writer(xlfile, delimiter=csv_conf.column_separator,
                          quotechar=csv_conf.quotechar, quoting=csv.QUOTE_MINIMAL)
        header = [i18n["Date"],i18n["Account"],i18n["Statement balance"]]
        writer.writerow(header)
        for b in bals:
            writer.writerow([b.date, b.account.identifier, amount_to_str(b.statement_balance, csv_conf.decimal_separator)])