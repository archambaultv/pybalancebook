import logging
import re
from bisect import bisect_right
from datetime import date
from balancebook.account import Account
from balancebook.amount import amount_to_str
from balancebook.csv import CsvFile, load_csv, write_csv
import balancebook.errors as bberr
from balancebook.errors import SourcePosition

logger = logging.getLogger(__name__)

class Posting():
    """A posting in a transaction
    
    Id is unique for a given transaction."""
    def __init__(self, id: int, account: Account, amount: int = None, parent_txn: 'Txn' = None,
                 statement_date: date = None, statement_description: str = None,
                 comment: str = None, source: SourcePosition = None):
        self.id = id
        self.account = account
        self.amount = amount
        self.parent_txn = parent_txn
        self.statement_date = statement_date
        self.statement_description = statement_description
        self.comment = comment
        self.source = source

    def __str__(self):
        return f"Posting({self.account}, {amount_to_str(self.amount)})"

    def key(self, txn_date: date = None) -> tuple[date,str,int,str]:
        if not txn_date:
            txn_date = self.parent_txn.date
        return (txn_date, self.account.number, self.amount, self.statement_description)

    def copy(self):
        """Return a copy of the posting
        
        Also creates a copy of the parent transaction.
        The account is not copied"""
        t2 = self.parent_txn.copy()
        for p in t2.postings:
            if p.id == self.id:
                return p

class Txn():
    """A transaction"""
    def __init__(self,txn_id: int, date: date, postings: list[Posting]):
        self.id = txn_id
        self.date = date
        self.postings = postings

    def __str__(self):
        ps = []
        for p in self.postings:
            ps.append(p.__str__())
        ps_str = " | ".join(ps)
        return f"Txn({self.date}, {ps_str})"
    
    def copy(self):
        """Return a copy of the transaction
        
        The postings are also copied, but not their account"""
        t = Txn(self.id, self.date, [])
        for p in self.postings:
            source = SourcePosition(p.source.file, p.source.line, p.source.column)
            t.postings.append(Posting(p.id, p.account, p.amount, t, p.statement_date, p.statement_description, p.comment, source))
        return t

def load_txns(csvFile: CsvFile, accounts_by_number: dict[str,Account]) -> list[Txn]:
    """Load transactions from the yaml file
    
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
        source = row[7]
        st_dt = row[4] if row[4] else row[1]
        if row[2] not in accounts_by_number:
            raise bberr.UnknownAccount(row[2], source)
        p = Posting(None, accounts_by_number[row[2]], row[3], None, st_dt, row[5], row[6], source)
        if row[0] not in txns_dict:
            t = Txn(row[0], row[1], [p])
            p.parent_txn = t
            p.id = 1
            txns_dict[row[0]] = t
        else:
            t = txns_dict[row[0]]
            # Ensure date is the same
            if t.date != row[1]:
                raise bberr.TxnDateMismatch(t.id, t.date, row[1], source)
            p.parent_txn = t
            p.id = len(t.postings) + 1
            t.postings.append(p)

    txns = list(txns_dict.values())
    for t in txns:
        verify_txn(t)

    return txns


def verify_txn(txn: Txn) -> None:
    """Verify a transaction
    
    - Verify that there is at least two postings
    - Verify that the sum of the postings is 0"""


    # Verify that there is at least two postings
    if len(txn.postings) < 2:
        raise bberr.TxnLessThanTwoPostings(txn.id)

    # Compute the sum of the postings
    sum_amount = sum([p.amount for p in txn.postings])
    if sum_amount != 0:
        raise bberr.TxnNotBalanced(txn.id)

# Export transactions to a csv file
def write_txns(txns: list[Txn], csvFile: CsvFile):
    """Write transactions to file."""
    data = write_txns_to_list(txns, csvFile.config.decimal_separator, False)
    write_csv(data, csvFile)

def write_txns_to_list(txns: list[Txn], decimal_separator = ".", posting_id = False) -> list[list[str]]:
    header = ["Txn id","Date","Account","Amount","Statement date","Statement description","Comment"]
    if posting_id:
        header.append("Posting id")
    rows = [header]
    for t in txns:
        for p in t.postings:
            row = [t.id, t.date, p.account.identifier, amount_to_str(p.amount, decimal_separator), 
                         p.statement_date, p.statement_description, p.comment]
            if posting_id:
                row.append(p.id)
            rows.append(row)
    return rows

def postings_by_number_by_date(txns: list[Txn], statement_balance: bool = False) -> dict[int, list[tuple[date,list[Posting]]]] :
    """Return a dictionary with keys being account number and values being an ordered list of postings grouped by date"""
    
    ps_dict: dict[str, dict[date, list[Txn]]] = {}
    for t in txns:
        for p in t.postings:
            id = p.account.number
            dt = t.date if not statement_balance else p.statement_date
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