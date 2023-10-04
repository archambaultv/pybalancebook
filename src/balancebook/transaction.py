import csv
import logging
from bisect import bisect_right
from datetime import date
from balancebook.utils import fiscal_year, fiscal_month
from balancebook.account import Account
from balancebook.amount import amount_to_str, any_to_amount
from balancebook.csv import CsvFile, load_csv
import balancebook.errors as bberr
from balancebook.errors import SourcePosition

logger = logging.getLogger(__name__)

class Posting():
    """A posting in a transaction"""
    def __init__(self, account: Account, amount: int = None, parent_txn: 'Txn' = None,
                 statement_date: date = None, statement_description: str = None,
                 comment: str = None, source: SourcePosition = None):
        self.account = account
        self.amount = amount
        self.parent_txn = parent_txn
        self.statement_date = statement_date
        self.statement_description = statement_description
        self.comment = comment
        self.source = source

    def __str__(self):
        return f"Posting({self.account}, {amount_to_str(self.amount)})"

    def key(self, txn_date = None) -> tuple[date,str,int,str]:
        if not txn_date:
            txn_date = self.parent_txn.date
        return (txn_date, self.account.number, self.amount, self.statement_description)

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

def load_txns(csvFile: CsvFile, accounts_by_id: dict[str,Account]) -> list[Txn]:
    """Load transactions from the yaml file
    
    Verify the consistency of the transactions"""
    csv_rows = load_csv(csvFile, [("Id", "int", True), ("Date", "date", True), ("Account", "str", True), 
                                  ("Amount", "amount", True), ("Statement date", "date", False), 
                                  ("Statement description", "str", False), ("Comment", "str", False)])
    txns_dict: dict[int, Txn] = {}
    for row in csv_rows:
        source = row[7]
        st_dt = row[4] if row[4] else row[1]
        if row[2] not in accounts_by_id:
            raise bberr.UnknownAccount(row[2], source)
        p = Posting(accounts_by_id[row[2]], row[3], None, st_dt, row[5], row[6], source)
        if row[0] not in txns_dict:
            t = Txn(row[0], row[1], [p])
            p.parent_txn = t
            txns_dict[row[0]] = t
        else:
            t = txns_dict[row[0]]
            # Ensure date is the same
            if t.date != row[1]:
                raise bberr.TxnDateMismatch(t.id, t.date, row[1], source)
            p.parent_txn = t
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

def sort_txns(txns: list[Txn]) -> None:
    """Sort transactions by date, account number and id."""
    for t in txns:
        t.postings.sort(key=lambda x: x.account.number)
    txns.sort(key=lambda x: (x.date,x.postings[0].account.number, x.id))

# Export transactions to a csv file
def write_txns(txns: list[Txn], csvFile: CsvFile, extra_columns: bool = False,
               first_fiscal_month = 1):
    sort_txns(txns)
    csv_conf = csvFile.config
    with open(csvFile.path, 'w', encoding = csv_conf.encoding) as csvfile:
        writer = csv.writer(csvfile, delimiter=csv_conf.column_separator,
                            quotechar=csv_conf.quotechar, quoting=csv.QUOTE_MINIMAL)
        # Header row
        header = ["Id", "Date", "Account", "Amount", 
                  "Statement date", "Statement description", "Comment"]
        if extra_columns:
            header.extend([ "Account name", 
                            "Number",
                            "Type",
                            "Group",
                            "Subgroup",
                            "Fiscal year",
                            "Fiscal month",
                            "Other accounts"])
        writer.writerow(header)

        # Data rows
        for t in txns:
            for p in t.postings:
                row = [t.id, t.date, p.account.identifier, amount_to_str(p.amount, csv_conf.decimal_separator), 
                       p.statement_date, p.statement_description, p.comment]
                if extra_columns:
                    row.extend([p.account.name, 
                                p.account.number,
                                p.account.type,
                                p.account.group,
                                p.account.subgroup,
                                fiscal_year(t.date, first_fiscal_month),
                                fiscal_month(t.date, first_fiscal_month),
                                csv_conf.join_separator.join([x.account.name for x in t.postings if x.account.identifier != p.account.identifier])])
                writer.writerow(row)
        

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

def compute_account_balance(psdict: dict[int, list[tuple[date,list[Posting]]]]) -> dict[str, list[tuple[date,int]]]:
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

def balance(account: Account, date: date, balanceDict: dict[str, list[tuple[date,int]]]) -> int:
    """Return the balance of the account at the given date"""
    id = account.identifier
    idx = bisect_right(balanceDict[id], date, key=lambda x: x[0])
    if idx:
        return balanceDict[id][idx-1][1]
    else:
        return 0