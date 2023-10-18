import logging
from itertools import groupby
from bisect import bisect_right
from datetime import date
from balancebook.account import Account
from balancebook.amount import amount_to_str
from balancebook.csv import CsvFile, load_csv, write_csv
import balancebook.errors as bberr
from balancebook.errors import SourcePosition

logger = logging.getLogger(__name__)

class Posting():
    """A posting is a variation of an account balance"""
    def __init__(self, id: int, date: date, account: Account, amount: int,
                 statement_date: date = None, statement_description: str = None,
                 comment: str = None, source: SourcePosition = None):
        self.id = id
        self.date = date
        self.account = account
        self.amount = amount
        self.statement_date = statement_date if statement_date else date
        self.statement_description = statement_description
        self.comment = comment
        self.source = source

    def __str__(self):
        return f"Posting({self.date}, {self.account.identifier}, {amount_to_str(self.amount)}, {self.statement_description if self.statement_description else ''})"

    def dedup_key(self) -> tuple[date,str,int,str]:
        """Return a tuple that can be used as deduplication key"""
        return (self.date, self.account.number, self.amount, self.statement_description)

    def copy(self):
        """Return a copy of the posting. The account is not copied"""
        return Posting(self.id, self.date, self.account, self.amount, 
                       self.statement_date, self.statement_description, self.comment, self.source)
    
    def same_as(self, other: 'Posting') -> bool:
        """Return True if the posting date, account and amount are the same as the other posting"""
        return (self.date == other.date and 
                self.account == other.account and 
                self.amount == other.amount)

class Txn():
    """A transaction is a list of postings that are balanced for each date.
    
    Single-day transactions have only one distinct date.
    Multi-day transactions have multiple dates, but the sum of the postings for each date is 0."""
    def __init__(self,txn_id: int, postings: list[Posting]):
        self.id = txn_id
        self.postings = postings

    def __str__(self):
        ps = []
        for p in self.postings:
            ps.append(p.__str__())
        ps_str = " | ".join(ps)
        return f"Txn({ps_str[0:5]}{'...' if len(ps_str) > 5 else ''})"
    
    def copy(self):
        """Return a copy of the transaction"""
        t = Txn(self.id, [])
        for p in self.postings:
            t.postings.append(p.copy())
        return t

    def is_single_day(self) -> bool:
        """Return True if all the postings have the same date"""
        return len(set([p.date for p in self.postings])) == 1
    
    def is_multi_day(self) -> bool:
        """Return True if the transaction is not a single day transaction"""
        return not self.is_single_day()
    
    def is_single_month(self) -> bool:
        """Return True if all the postings have the same month and year"""
        return len(set([(p.date.year, p.date.month) for p in self.postings])) == 1
    
    def is_single_year(self) -> bool:
        """Return True if all the postings have the same year"""
        return len(set([p.date.year for p in self.postings])) == 1
    
    def ps_dates(self) -> list[date]:
        """Return the list of dates of the postings"""
        return [p.date for p in self.postings]
    
    def min_date(self) -> date:
        """Return the minimum date of the postings"""
        return min([p.date for p in self.postings])

    def is_balanced(self) -> bool:
        """Return True if the transaction is balanced"""
        self.postings.sort(key=lambda x: x.date)
        for _, ps in groupby(self.postings, key=lambda x: x.date):
            ps = list(ps)
            if sum([p.amount for p in ps]) != 0:
                return False
        return True
    
    def same_as(self, other: 'Txn') -> bool:
        """Return True if the transaction postings are the same as the other transaction postings"""
        if len(self.postings) != len(other.postings):
            return False
        
        other_ps = sorted(other.postings, key=lambda x: (x.date, x.account, x.amount))
        self_ps = sorted(self.postings, key=lambda x: (x.date, x.account, x.amount))
        for s, o in zip(self_ps, other_ps):
            if not s.same_as(o):
                return False
            
        return True
        

def load_txns(csvFile: CsvFile, accounts_by_number: dict[str,Account]) -> list[Txn]:
    """Load transactions from the csv file
    
    Verify the consistency of the transactions"""
    csv_rows = load_csv(csvFile, [("Txn id", "int", True, True), 
                                  ("Date", "date", True, True), 
                                  ("Account", "str", True, True), 
                                  ("Amount", "amount", True, True), 
                                  ("Statement date", "date", False, False), 
                                  ("Statement description", "str", False, False), 
                                  ("Comment", "str", False, False)])
    txns_dict: dict[int, Txn] = {}
    for row in csv_rows:
        txn_id = row[0]
        source = row[7]
        dt = row[1]
        st_dt = row[4] if row[4] else dt
        if row[2] not in accounts_by_number:
            raise bberr.UnknownAccount(row[2], source)
        p = Posting(None, dt, accounts_by_number[row[2]], row[3], st_dt, row[5], row[6], source)
        if txn_id not in txns_dict:
            p.id = 1
            t = Txn(txn_id, [p])
            txns_dict[txn_id] = t
        else:
            t = txns_dict[txn_id]
            p.id = len(t.postings) + 1
            t.postings.append(p)

    txns = list(txns_dict.values())
    for t in txns:
        verify_txn(t)

    return txns


def verify_txn(txn: Txn) -> None:
    """Verify a transaction
    
    - Verify that the transaction is balanced"""

    # Verify that the transaction is balanced
    if not txn.is_balanced():
        source = txn.postings[0].source if txn.postings else None
        raise bberr.TxnNotBalanced(txn.id, source)

# Export transactions to a csv file
def write_txns(txns: list[Txn], csvFile: CsvFile):
    """Write transactions to file."""
    data = write_txns_to_list(txns, csvFile.config.decimal_separator)
    write_csv(data, csvFile)

txn_header = ["Txn id","Date","Account","Amount","Statement date","Statement description","Comment"]

def write_txns_to_list(txns: list[Txn], decimal_separator = ".") -> list[list[str]]:
    header = txn_header
    rows = [header]
    for t in txns:
        for p in t.postings:
            row = [t.id, p.date, p.account.identifier, amount_to_str(p.amount, decimal_separator), 
                         p.statement_date, p.statement_description, p.comment]
            rows.append(row)
    return rows

def postings_by_account(txns: list[Txn]) -> dict[int, list[Posting]]:
    """Return a dictionary with keys being account number and values being an ordered list of postings"""
    
    ps_dict: dict[str, list[Posting]] = {}
    for t in txns:
        for p in t.postings:
            id = p.account.number
            if id not in ps_dict:
                ps_dict[id] = []
            ps_dict[id].append(p)

    for key, value in ps_dict.items():
        ps_dict[key] = sorted(value, key=lambda x: x.date)

    return ps_dict

def postings_by_account_by_date(txns: list[Txn], statement_balance: bool = False) -> dict[int, list[tuple[date,list[Posting]]]] :
    """Return a dictionary with keys being account number and values being an ordered list of postings grouped by date"""
    
    ps_dict: dict[str, dict[date, list[Txn]]] = {}
    for t in txns:
        for p in t.postings:
            id = p.account.number
            dt = p.date if not statement_balance else p.statement_date
            if id not in ps_dict:
                ps_dict[id] = {}
            if dt not in ps_dict[id]:
                ps_dict[id][dt] = []

            ps_dict[id][dt].append(p)

    for key, value in ps_dict.items():
        ps_dict[key] = sorted(value.items(), key=lambda x:x[0])

    return ps_dict

def compute_account_balance(psdict: dict[int, list[tuple[date,list[Posting]]]]) -> dict[int, list[tuple[date,int]]]:
    """Compute the balance of the accounts"""
  
    balancedict = {}
    for acc, ps in psdict.items():
        total = 0
        balanceList = []
        for (dt, ts) in ps:
            total += sum([p.amount for p in ts])
            balanceList.append((dt, total))

        balancedict[acc] = balanceList

    return balancedict

def balance(account: Account, dt: date, balance_dict: dict[int, list[tuple[date,int]]]) -> int:
    """Return the balance of the account at the given date"""
    if account.number not in balance_dict:
        return 0
    idx = bisect_right(balance_dict[account.number], dt, key=lambda x: x[0])
    if idx:
        return balance_dict[account.number][idx-1][1]
    else:
        return 0
            
def subset_sum (postings: list[Posting], target: int) -> list[Posting]:
    """Finds the subset of postings that matches the target amount
    
    This is a brute force algorithm that tries all the possible combinations.

    You can use it to find the postings that matches the balance assertion difference and
    bump the statement date of those postings."""
    if target == 0:
        return []
    
    previous: list[list[int]] = []
    len_postings = len(postings)
    for i in range(len_postings):
        amnt = postings[i].amount
        if amnt == target:
            return [postings[i]]

        len_previous = len(previous)
        previous.append([i])
        for j in range(len_previous):
            xs = previous[j].copy()
            xs.append(i)
            s = sum([postings[k].amount for k in xs])
            if s == target:
                return [postings[k] for k in xs]
            previous.append(xs)

    return None