import logging
from itertools import groupby
from datetime import date, timedelta
from balancebook.account import Account
from balancebook.amount import amount_to_str
from balancebook.i18n import I18n
from balancebook.csv import CsvFile, load_csv, write_csv, CsvColumn
import balancebook.errors as bberr
from balancebook.errors import SourcePosition

logger = logging.getLogger(__name__)

class Posting():
    """A posting is a variation of an account balance"""
    def __init__(self, date: date, account: Account, amount: int, payee: str = None,
                 statement_date: date = None, statement_description: str = None,
                 comment: str = None, source: SourcePosition = None):
        self.date = date
        self.account = account
        self.amount = amount
        self.payee = payee
        self.statement_date = statement_date if statement_date else date
        self.statement_description = statement_description
        self.comment = comment
        self.source = source

    def __str__(self):
        dt = self.date.strftime("%Y-%m-%d")
        return f"Posting({dt}, {self.account.identifier}, {amount_to_str(self.amount)}{', ' + self.payee if self.payee else ''})"

    def dedup_key(self) -> tuple[date,str,int,str]:
        """Return a tuple that can be used as deduplication key"""
        return (self.date, self.account.number, self.amount, self.statement_description)
    
    def equivalent_to(self, other: 'Posting') -> bool:
        """Return True if the posting date, account and amount are the same as the other posting"""
        return (self.date == other.date and 
                self.account == other.account and 
                self.amount == other.amount)

    def last91(self, today: date = None) -> bool:
        """Return True if the posting is from the last 91 days"""
        if today is None:
            today = date.today()
        return self.date >= (today - timedelta(days=91)) and self.date <= today
    
    def last182(self, today: date = None) -> bool:
        """Return True if the posting is from the last 182 days"""
        if today is None:
            today = date.today()
        return self.date >= (today - timedelta(days=182)) and self.date <= today
    
    def last365(self, today: date = None) -> bool:
        """Return True if the posting is from the last 365 days"""
        if today is None:
            today = date.today()
        return self.date >= (today - timedelta(days=365)) and self.date <= today

class Txn():
    """A transaction is a list of postings that are balanced for each date.
    
    Single-day transactions have only one distinct date.
    Multi-day transactions have multiple dates, but the sum of the postings for each date is 0."""
    def __init__(self,txn_id: int, postings: list[Posting]):
        self.id = txn_id
        self.postings = postings

    def __str__(self):
        ps = []
        for n, p in enumerate(self.postings):
            if n > 5:
                ps.append("...")
                break
            ps.append(p.__str__())
        ps_str = " | ".join(ps)
        return f"Txn({ps_str})"

    def is_single_day(self) -> bool:
        """Return True if the transaction has only one distinct date"""
        return len(set([p.date for p in self.postings])) == 1

    def is_daily_balanced(self) -> bool:
        """Return True if the transaction is balanced every day"""
        ls = sorted(self.postings, key=lambda x: x.date)
        for _, ps in groupby(ls, key=lambda x: x.date):
            ps = list(ps)
            if sum([p.amount for p in ps]) != 0:
                return False
        return True
    
    def equivalent_to(self, other: 'Txn') -> bool:
        """Return True if the transaction postings are equivalent to the other transaction postings"""
        if len(self.postings) != len(other.postings):
            return False
        
        other_ps = sorted(other.postings, key=lambda x: (x.date, x.account, x.amount))
        self_ps = sorted(self.postings, key=lambda x: (x.date, x.account, x.amount))
        for s, o in zip(self_ps, other_ps):
            if not s.equivalent_to(o):
                return False
            
        return True
    
    def accounts(self) -> list[Account]:
        """Return the list of accounts involved in the transaction"""
        return list(set([p.account for p in self.postings]))
        

def load_txns(csvFile: CsvFile, accounts_by_name: dict[str,Account], 
              i18n: I18n = None,
              enforce_single_day: bool = True) -> list[Txn]:
    """Load transactions from the csv file
    
    Verify the consistency of the transactions"""
    if i18n is None:
        i18n = I18n()
    
    txn_id_i18n = i18n["Txn id"]
    date_i18n = i18n["Date"]
    account_i18n = i18n["Account"]
    amount_i18n = i18n["Amount"]
    statement_date_i18n = i18n["Statement date"]
    statement_description_i18n = i18n["Statement description"]
    comment_i18n = i18n["Comment"]
    payee_i18n = i18n["Payee"]

    csv_rows = load_csv(csvFile, [CsvColumn(txn_id_i18n, "int", True, True), 
                                  CsvColumn(date_i18n, "date", True, True), 
                                  CsvColumn(account_i18n, "str", True, True), 
                                  CsvColumn(amount_i18n, "amount", True, True), 
                                  CsvColumn(statement_date_i18n, "date", False, False), 
                                  CsvColumn(statement_description_i18n, "str", False, False), 
                                  CsvColumn(comment_i18n, "str", False, False),
                                  CsvColumn(payee_i18n, "str", False, False)])
    txns_dict: dict[int, Txn] = {}
    for row, source in csv_rows:
        txn_id = row[txn_id_i18n]
        payee = row[payee_i18n]
        dt = row[date_i18n]
        st_dt = row[statement_date_i18n] if row[statement_date_i18n] else dt
        if row[account_i18n] not in accounts_by_name:
            raise bberr.UnknownAccount(row[account_i18n], source)
        p = Posting(dt, accounts_by_name[row[account_i18n]], 
                    row[amount_i18n], payee, st_dt, row[statement_description_i18n], 
                    row[comment_i18n], source)
        if txn_id not in txns_dict:
            t = Txn(txn_id, [p])
            txns_dict[txn_id] = t
        else:
            t = txns_dict[txn_id]
            t.postings.append(p)

    txns = list(txns_dict.values())
    for t in txns:
        source = t.postings[0].source
        if enforce_single_day and not t.is_single_day():
            raise bberr.TxnNotSingleDay(t.id, source)

        if not t.is_daily_balanced():
            raise bberr.TxnNotBalanced(t.id, source)
    
    return txns

# Export transactions to a csv file
def write_txns(txns: list[Txn], csvFile: CsvFile, i18n: I18n):
    """Write transactions to file."""
    data = write_txns_to_list(txns, i18n, csvFile.config.decimal_separator)
    write_csv(data, csvFile)

txn_header = ["Txn id","Date","Account","Amount","Payee","Statement date","Statement description","Comment"]

def write_txns_to_list(txns: list[Txn], i18n: I18n, decimal_separator = ".") -> list[list[str]]:
    rows = []
    rows.append([i18n[x] for x in txn_header])
    for t in txns:
        for p in t.postings:
            row = [t.id, p.date, p.account.identifier, amount_to_str(p.amount, decimal_separator), p.payee,
                   p.statement_date, p.statement_description, p.comment]
            rows.append(row)
    return rows
            
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