from datetime import date

from balancebook.account import Account, load_and_normalize_accounts, write_accounts
from balancebook.transaction import Txn, load_and_normalize_txns, write_txns
from balancebook.balance import Balance, load_and_normalize_balances, write_balances
from balancebook.csv import CsvFile
from balancebook.utils import fiscal_month, fiscal_year

class JournalConfig():
    def __init__(self, account_file: CsvFile, txn_file: CsvFile, balance_file: CsvFile, 
                 first_fiscal_month: int = 1) -> None:
        self.account_file = account_file
        self.txn_file = txn_file
        self.balance_file = balance_file
        self.first_fiscal_month = first_fiscal_month

class Journal():
    def __init__(self, config: JournalConfig, accounts: list[Account], 
               txns: list[Txn], balances: list[Balance]) -> None:
        self.config = config
        self.accounts = accounts
        self.accounts_by_id = dict([(a.identifier, a) for a in accounts])
        self.txns = txns
        self.balances = balances

    def write(self):
        """Write the journal to files"""
        write_accounts(self.accounts, self.config.account_file)
        write_balances(self.balances, self.config.balance_file)
        write_txns(self.txns, self.config.txn_file, False)

    def fiscal_month(self, dt: date) -> int:
        return fiscal_month(dt, self.config.first_fiscal_month)
    
    def fiscal_year(self, dt: date) -> int:
        return fiscal_year(dt, self.config.first_fiscal_month)

    
def load_and_normalize_journal(config: JournalConfig) -> Journal:
    """Load the journal from the given path
  
    Normalize the journal data"""

    accounts = load_and_normalize_accounts(config.account_file)
    accounts_by_name = dict([(a.identifier, a) for a in accounts])
    txns = load_and_normalize_txns(config.txn_file, accounts_by_name)
    balances = load_and_normalize_balances(config.balance_file, accounts_by_name)

    return Journal(config, accounts, txns, balances)