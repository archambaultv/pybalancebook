from christophe.account import Account, load_and_normalize_accounts, write_accounts
from christophe.transaction import Txn, load_and_normalize_txns, write_txns
from christophe.balance import Balance, load_and_normalize_balances, write_balances
from christophe.csv import CsvFile
from christophe.i18n import I18n, i18n_en

class JournalConfig():
    def __init__(self, account_file: CsvFile, txn_file: CsvFile, balance_file: CsvFile, 
                 first_fiscal_month: int = 1, i18n: I18n = i18n_en) -> None:
        self.account_file = account_file
        self.txn_file = txn_file
        self.balance_file = balance_file
        self.first_fiscal_month = first_fiscal_month
        self.i18n = i18n

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
        write_accounts(self.accounts, self.config.account_file, self.config.i18n)
        write_balances(self.balances, self.config.balance_file, self.config.i18n)
        write_txns(self.txns, self.config.txn_file, self.config.i18n, False)

def load_and_normalize_journal(config: JournalConfig) -> Journal:
    """Load the journal from the given path
  
    Normalize the journal data"""

    accounts = load_and_normalize_accounts(config.accFile, config.i18n)
    accounts_by_name = dict([(a.identifier, a) for a in accounts])
    txns = load_and_normalize_txns(config.txnFile, accounts_by_name)
    balances = load_and_normalize_balances(config.balFile, accounts_by_name, config.i18n)

    return Journal(config, accounts, txns, balances)