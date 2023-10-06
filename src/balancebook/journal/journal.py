from datetime import date
import logging
from datetime import timedelta

import balancebook.errors as bberr
from balancebook.account import Account, load_accounts, write_accounts
from balancebook.transaction import (Txn, load_txns, write_txns, postings_by_number_by_date, compute_account_balance,
                                     balance, reclassify, ClassificationRule)
from balancebook.balance import Balance, load_balances, write_balances
from balancebook.csv import CsvFile
from balancebook.transaction import Posting, subset_sum
from balancebook.utils import fiscal_month, fiscal_year
from balancebook.journal.autoimport import import_bank_postings, CsvImportHeader

logger = logging.getLogger(__name__)

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
        self.txns = txns
        self.balances = balances

        # Cache of various dictionaries
        self.txns_by_id: dict[int,Txn] = None
        self.balance_by_number: dict[int,list[Balance]] = None
        self.accounts_by_id: dict[str,Account] = None
        self.postings_by_number_by_date: dict[int,list[tuple[date,list[Posting]]]] = None
        self.account_balance_by_number_by_date: dict[int,list[tuple[date,int]]] = None

    def write(self, what: list[str] = None) -> None:
        """Write the journal to files
        
        what: list of what to write. If None, write everything.
        Valid values are: "accounts", "balances", "transactions"
        """

        if isinstance(what, str):
            what = [what]

        if not what or "accounts" in what:
            write_accounts(self.accounts, self.config.account_file)
        if not what or "balances" in what:
            write_balances(self.balances, self.config.balance_file)
        if not what or "transactions" in what:
            write_txns(self.txns, self.config.txn_file, False)

    def get_account(self, identifier: str) -> Account:
        """Get the account with the given identifier"""
        d = self.account_by_id_dict()
        if identifier in d:
            return d[identifier]
        else:
            raise bberr.UnknownAccount(identifier)
    
    def fiscal_month(self, dt: date) -> int:
        return fiscal_month(dt, self.config.first_fiscal_month)
    
    def fiscal_year(self, dt: date) -> int:
        return fiscal_year(dt, self.config.first_fiscal_month)
    
    def posting_keys(self, account: Account = None, after: date = None) -> dict[tuple[date,str,int,str], int]:
        keys: dict[tuple[date,str,int,str], int] = {}
        for t in self.txns:
            for p in t.postings:
                if account and p.account.number != account.number:
                    continue
                if after and t.date <= after:
                    continue

                if p.key() in keys:
                    keys[p.key()] += 1
                else:
                    keys[p.key()] = 1
        return keys

    def account_by_id_dict(self) -> dict[str,Account]:
        if self.accounts_by_id is None:
            self.accounts_by_id = dict([(a.identifier, a) for a in self.accounts])
        return self.accounts_by_id

    def balance_by_number_dict(self) -> dict[int, list[Balance]]:
        """Get the balance dictionary
        
        The dictionary is indexed by account number.
        The value is an ordered list of balances for the given account number."""
        if self.balance_by_number is None:
            # Create the balance dictionary
            self.balance_by_number: dict[int, list[Balance]] = {}
            if len(self.balances) == 0:
                return self.balance_by_number
            else:
                bals = sorted(self.balances, key=lambda x: (x.account.number, x.date))
                b: Balance = self.balances[0]
                self.balance_by_number[b.account.number] = [b]
                for i, _ in enumerate(bals[1:]):
                    previous: Account = bals[i].account
                    next: Account = bals[i+1].account
                    if previous.number != next.number:
                        self.balance_by_number[next.number] = [next]
                    else:
                        self.balance_by_number[next.number].append(next)
                
        return self.balance_by_number

    def get_newest_balance_assertions(self, account: Account) -> Balance:
        """Get the newer balance assertions for the given account"""
        d = self.balance_by_number_dict()
        if account.number in d:
            return d[account.number][-1]
        else:
            return None

    def get_txns_by_id(self) -> dict[int,Txn]:
        if self.txns_by_id is None:
            self.txns_by_id = dict([(t.id, t) for t in self.txns])
        return self.txns_by_id

    def import_from_bank_csv(self, csvFile : CsvFile, csv_header: CsvImportHeader, 
                             account: Account,
                             default_snd_account: Account,
                             rules: list[ClassificationRule],
                             import_zero_amount: bool = True) -> list[Txn]:
        """Import the transactions from the bank csv file
        
        Does not modify the journal.
        """

        # Load posting from file
        csvPs = import_bank_postings(csvFile, csv_header, account, import_zero_amount)

        # Create new transactions with default_snd_account
        #   if the date is after the newest balance assertion
        #   if the posting is not already in a transaction
        txns = []
        newest_balance = self.get_newest_balance_assertions(account)
        newest_date = newest_balance.date if newest_balance else None
        keys = self.posting_keys(account, newest_date)                   
        for (dt, p) in csvPs:
            if newest_date and dt <= newest_date:
                logger.info(f"Skipping posting {p} because it is before the newest balance assertion\n{p.source}")
                continue
            
            if p.key(dt) in keys:
                if keys[p.key(dt)] == 1:
                    del keys[p.key(dt)]
                else:
                    keys[p.key(dt)] -= 1
                logger.info(f"Skipping posting {p} because it is already in a transaction\n{p.source}")
                continue

            t = Txn(None, dt, [])
            p.parent_txn = t
            p.id = 1
            p2 = Posting(2, default_snd_account, - p.amount, t, dt, p.statement_description, p.comment, None)
            t.postings.extend([p, p2])
            txns.append(t)

        # Apply classification rules
        return reclassify(txns, rules)

    def set_txns(self, txns: list[Txn]) -> None:
        """Set the transactions"""
        self.txns = txns

        self.txns_by_id = None
        self.account_balance_by_number_by_date = None
        self.postings_by_number_by_date = None

    def update_txns(self, txns: list[Txn]) -> None:
        """Update the transactions"""
        d = self.get_txns_by_id()
        for t in txns:
            if t.id in d:
                d[t.id] = t
            else:
                raise bberr.JournalUnknownTxn(t.id)
        
        self.txns = list(d.values())
        self.txns_by_id = None
        self.account_balance_by_number_by_date = None
        self.postings_by_number_by_date = None

    def new_txns(self, txns: list[Txn]) -> None:
        """Add new transactions
        
        The transactions numbers are set automatically"""
        next_id = max([t.id for t in self.txns]) + 1
        for t in txns:
            t.id = next_id
            next_id += 1
        self.txns.extend(txns)

        self.txns_by_id = None
        self.account_balance_by_number_by_date = None
        self.postings_by_number_by_date = None

    def get_account_balance_dict(self, statement_balance: bool = False) -> dict[int,list[tuple[date,int]]]:
        if statement_balance:
            ps = postings_by_number_by_date(self.txns, True)
            return compute_account_balance(ps)

        if self.account_balance_by_number_by_date is None:
            d = self.get_postings_by_number_by_date()
            self.account_balance_by_number_by_date = compute_account_balance(d)
        return self.account_balance_by_number_by_date

    def get_postings_by_number_by_date(self) -> dict[int,dict[date,list[Posting]]]:
        if self.postings_by_number_by_date is None:
            self.postings_by_number_by_date = postings_by_number_by_date(self.txns, False)

        return self.postings_by_number_by_date

    def get_account_balance(self, account: Account, dt: date) -> int:
        """Get the account balance at the given date"""
        d = self.get_account_balance_dict()
        return balance(account, dt, d)

    def verify_balances(self) -> None:
        """ Verify that the balances are consistent with the transactions"""
        bals = sorted(self.balances, key=lambda x: (x.date, x.account.number))
        d = self.get_account_balance_dict(True)
        for b in bals:
            txnAmount = balance(b.account, b.date, d)
            if txnAmount != b.statement_balance:
                raise bberr.BalanceAssertionFailed(b.date, b.account.identifier, b.statement_balance, txnAmount, b.source)

    def auto_statement_date(self, Balance: Balance, dayslimit: int = 7) -> list[Txn]:
        """Try to adjust the statement date of the transactions to match the given balance assertion
        
        Returns the list of transactions to update. Use update_txns to update the transactions afterwards.
        Returns None if no transactions can be updated and the balance assertion is not met.
        """
        d = self.get_account_balance_dict(True)
        txnAmount = balance(Balance.account, Balance.date, d)
        if txnAmount == Balance.statement_balance:
            return []

        ps = []
        # Select the postings from psdict that matches the account and the date range
        check = lambda x: (x[0] <= Balance.date and x[0] >= Balance.date - timedelta(days=dayslimit))
        postings_by_date = filter(check, self.get_postings_by_number_by_date()[Balance.account.number])
        ps: list[Posting] = [p for _, postings in postings_by_date for p in postings]
        ps.sort(reverse=True,key=lambda x:x.parent_txn.date)

        subset = subset_sum(ps, txnAmount - Balance.statement_balance)
        if subset:
            # Multiple postings can come from the same transaction
            txns2: dict[int,Txn] = {}
            for p in subset:
                if p.parent_txn.id in txns2:
                    t2 = txns2[p.parent_txn.id]
                else:
                    t2 = p.parent_txn.copy()
                    txns2[t2.id] = t2
                for i in range(len(t2.postings)):
                    if t2.postings[i].id == p.id:
                        t2.postings[i].statement_date = Balance.date + timedelta(days=1)
                        break
            return list(txns2.values())

        else:
            return None

    def auto_balance_with_new_txn(self, b: Balance, snd_account: Account) -> Txn:
        """Balance the account with a new transaction
        
        Returns the transaction to add. Use new_txns to add the transaction afterwards.
        Returns None if the balance assertion is already met.
        """
        d = self.get_account_balance_dict(True)
        txnAmount = balance(b.account, b.date, d)
        if txnAmount == b.statement_balance:
            return None

        diff = b.statement_balance - txnAmount
        t = Txn(None, b.date, [])
        p1 = Posting(1, b.account, diff, t, b.date, None, None, None)
        p2 = Posting(2, snd_account, - diff, t, b.date, None, None, None)
        t.postings = [p1, p2]
        return t

def load_journal(config: JournalConfig) -> Journal:
    """Load the journal from the given path
  
    Normalize the journal data"""

    accounts = load_accounts(config.account_file)
    accounts_by_name = dict([(a.identifier, a) for a in accounts])
    txns = load_txns(config.txn_file, accounts_by_name)
    balances = load_balances(config.balance_file, accounts_by_name)

    return Journal(config, accounts, txns, balances)
