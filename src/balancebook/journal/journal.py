from datetime import date
import re
from bisect import bisect_right

import balancebook.errors as bberr
from balancebook.account import Account, load_accounts, write_accounts
from balancebook.transaction import Txn, load_txns, write_txns, postings_by_number_by_date, compute_account_balance
from balancebook.balance import Balance, load_balances, write_balances
from balancebook.csv import CsvFile
from balancebook.transaction import Posting
from balancebook.utils import fiscal_month, fiscal_year
from balancebook.journal.autoimport import import_bank_postings, normalize_bank_postings, CsvImportHeader

class JournalConfig():
    def __init__(self, account_file: CsvFile, txn_file: CsvFile, balance_file: CsvFile, 
                 first_fiscal_month: int = 1) -> None:
        self.account_file = account_file
        self.txn_file = txn_file
        self.balance_file = balance_file
        self.first_fiscal_month = first_fiscal_month

class ClassificationRule():
    """Rule to reclassify a transaction.

    If one of the posting matches the rule, the transaction is reclassified.
    All other postings are discarded and the transaction is balanced with the
    second account provided in the rule.
    """
    def __init__(self, match_date: (date, date), 
                       match_amnt: (int, int), 
                       match_account: str,
                       match_statement_description: str,
                       second_account: Account) -> None:
        self.match_date = match_date
        self.match_amnt = match_amnt
        self.match_account = match_account
        self.match_statement_description = match_statement_description
        self.second_account = second_account

class Journal():
    def __init__(self, config: JournalConfig, accounts: list[Account], 
               txns: list[Txn], balances: list[Balance]) -> None:
        self.config = config
        self.accounts = accounts
        self.txns = txns
        # The balances are sorted by account number and date
        # This must be an invariant
        self.balances = sorted(balances, key=lambda x: (x.account.number, x.date))

        # Cache of various dictionaries
        self.balance_by_number: dict[int,list[Balance]] = None
        self.accounts_by_id: dict[str,Account] = None
        self.postings_by_number_by_date: dict[int,list[tuple[date,list[Posting]]]] = None
        self.account_balance_by_number_by_date: dict[int,list[tuple[date,int]]] = None

    def write(self):
        """Write the journal to files"""
        write_accounts(self.accounts, self.config.account_file)
        write_balances(self.balances, self.config.balance_file)
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
                b: Balance = self.balances[0]
                self.balance_by_number[b.account.number] = [b]
                for i, _ in enumerate(self.balances[1:]):
                    previous: Account = self.balances[i].account
                    next: Account = self.balances[i+1].account
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

    def import_from_bank_csv(self, csvFile : CsvFile, csv_header: CsvImportHeader, 
                             account: Account,
                             default_snd_account: Account,
                             rules: list[ClassificationRule]) -> list[Txn]:
        """Import the transactions from the bank csv file
        
        Does not modify the journal.
        """

        # Load posting from file
        config = csvFile.config
        csvPsStr = import_bank_postings(csvFile, csv_header, account)
        csvPs = normalize_bank_postings(csvPsStr, config.decimal_separator, config.currency_sign, config.thousands_separator)
        
        # Create new transactions with default_snd_account
        #   if the date is after the newest balance assertion
        #   if the posting is not already in a transaction
        txns = []
        keys = self.posting_keys(account, self.get_newest_balance_assertions(account).date)                   
        for (dt, p) in csvPs:
            if dt > self.get_newest_balance_assertions(account).date:
                continue
            
            if p.key() in keys:
                if keys[p.key()] == 1:
                    del keys[p.key()]
                else:
                    keys[p.key()] -= 1
                continue

            t = Txn(None, dt, [])
            p.parent_txn = t
            p2 = Posting(default_snd_account, p.amount, t, dt, p.statement_description, p.comment, None)
            t.postings.extend([p, p2])
            txns.append(t)

        # Apply classification rules
        return reclassify(txns, rules)
    
    def reclassify(self, rules: list[ClassificationRule]) -> None:
        """Reclassify the transactions according to the rules."""
        self.txns = reclassify(self.txns, rules)
        self.account_balance_by_number_by_date = None
        self.postings_by_number_by_date = None

    def get_account_balance_dict(self) -> dict[int,list[tuple[date,int]]]:
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
        if account.number not in d:
            return 0
        idx = bisect_right(d[account.number], dt, key=lambda x: x[0])
        if idx:
            return d[account.number][idx-1][1]
        else:
            return 0

    def verify_balances(self) -> None:
        """ Verify that the balances are consistent with the transactions"""

        for b in self.balances:
            txnAmount = self.get_account_balance(b.account, b.date)
            if txnAmount != b.statement_balance:
                raise bberr.BalanceAssertionFailed(b.date, b.account.identifier, b.statement_balance, txnAmount)

def load_journal(config: JournalConfig) -> Journal:
    """Load the journal from the given path
  
    Normalize the journal data"""

    accounts = load_accounts(config.account_file)
    accounts_by_name = dict([(a.identifier, a) for a in accounts])
    txns = load_txns(config.txn_file, accounts_by_name)
    balances = load_balances(config.balance_file, accounts_by_name)

    return Journal(config, accounts, txns, balances)

def reclassify(txns: list[Txn], rules: list[ClassificationRule]) -> None:
    """Reclassify the transactions according to the rules.
    
    The rules are applied in the order they are provided.
    The transactions are modified in place.
    """
    for t in txns:
        # Find the first rule that matches
        r = None
        for rule in rules:
            if rule.match_date[0] and t.date < rule.match_date[0]:
                continue
            if rule.match_date[1] and t.date > rule.match_date[1]:
                continue

            p_match = None
            for p in t.postings:
                if rule.match_amnt[0] and p.amount < rule.match_amnt[0]:
                    continue
                if rule.match_amnt[1] and p.amount > rule.match_amnt[1]:
                    continue

                # Match account identifier with a full regex
                if rule.match_account and not re.fullmatch(rule.match_account, p.account.identifier):
                    continue

                # Match statement description with a full regex
                if rule.match_statement_description and not re.fullmatch(rule.match_statement_description, p.statement_description):
                    continue

                p_match = p
                r = rule
                break
            if p_match:
                break

        if r:
            p2 = Posting(r.second_account, - p_match.amount, t, t.date, p_match.statement_description, p_match.comment, None)
            t.postings = [p_match, p2]