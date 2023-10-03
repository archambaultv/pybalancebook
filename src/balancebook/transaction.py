import csv
import os
import logging
from bisect import bisect_right
from datetime import date
from balancebook.utils import fiscal_year, fiscal_month
from balancebook.account import Account
from balancebook.amount import amount_to_str, any_to_amount
from balancebook.csv import CsvFile, read_date
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
        return f"Posting({self.account}, {amount_to_str(self.amount,',')})"

    def key(self) -> tuple[date,str,int,str]:
        return (self.parent_txn.date, self.account.number, self.amount, self.statement_description)

class Txn():
    """A transaction"""
    def __init__(self,id: int, date: date, postings: list[Posting]):
        self.id = id
        self.date = date
        self.postings = postings

    def __str__(self):
        ps = []
        for p in self.postings:
            ps.append(p.__str__())
        ps_str = " | ".join(ps)
        return f"Txn({self.date}, {ps_str})"

def load_txns(csvFile: CsvFile) -> list[Txn]:
    """Load transactions from the yaml file
    
    All Txn fields will be of type str.
    Does not verify the consistency of the transactions"""

    # if file does not exist, return an empty list
    if not os.path.exists(csvFile.path):
        logger.warn(f"Transaction file {csvFile.path} does not exist")
        return []
    
    line = 1
    csv_conf = csvFile.config
    with open(csvFile.path, encoding=csv_conf.encoding) as txns_file:
        for _ in range(csv_conf.skip_X_lines):
            line += 1
            next(txns_file)
            
        rows = csv.DictReader(txns_file,
                        delimiter=csv_conf.column_separator,
                        quotechar=csv_conf.quotechar)
        
        # Check that the header is correct
        header = ["Id", "Date", "Account", "Amount", 
                  "Statement date", "Statement description", "Comment"]
        for h in header:
            if h not in rows.fieldnames:
                raise bberr.MissingHeader(h, SourcePosition(csvFile.path, line, None))
            
        txns: dict[int, Txn] = {}
        line += 1 # header line
        for r in rows:
            id = r["Id"].strip()
            date = r["Date"].strip()
            account = r["Account"].strip()
            amount = r["Amount"].strip()
            statement_date = r["Statement date"].strip()
            statement_description = r["Statement description"].strip()
            comment = r["Comment"].strip()

            if id not in txns:
                txns[id] = Txn(id, date, [])
            t = txns[id]
            t.postings.append(Posting(account, amount, t, statement_date, statement_description, comment))
            line += 1

        return list(txns.values())

def load_and_normalize_txns(csvFile: CsvFile, accounts_by_name: dict[str,Account]) -> list[Txn]:
    """Load transactions from the yaml file
    
    - Normalize the Txn data from str to the appropriate type
    - Verify the consistency of the transactions"""
    txns = load_txns(csvFile)
    for t in txns:
        normalize_txn(t, accounts_by_name, 
                      csvFile.config.decimal_separator,
                        csvFile.config.currency_sign,
                        csvFile.config.thousands_separator)
    return txns

def normalize_txn(txn: Txn, accounts: dict[str,Account],
                  decimal_sep: str = ".", currency_sign: str = "$", thousands_sep: str = " ") -> None:
    """Normalize a transaction
    
    - Normalize the Txn data from str to the appropriate type
    - If the date is a string, convert it to a date
    - Verify that there is at least two postings
    - Verify that there is only one posting without amount
    - Convert amount using float_to_amount
    - Verify that the sum of the postings is 0
    - If posting amount is not set, set it to the opposite of the sum of the other postings
    - If posting statement date is not set, set it to the transaction date
    - Verify that the account exists and change it to the account object"""

    # Verify that the transaction has an id
    if not txn.id:
        raise bberr.TxnIdEmpty
    
    # Verify that the transaction id in an integer
    try:
        txn.id = int(txn.id)
    except ValueError:
        raise bberr.TxnIdNotInteger(txn.id)

    # Verify that there is at least two postings
    if len(txn.postings) < 2:
        raise bberr.TxnLessThanTwoPostings(txn.id)

    # Verify that the account exists and change it to the account object
    for p in txn.postings:
        if p.account not in accounts:
            raise bberr.UnknownAccount(p.account, p.source)
        else:
            p.account = accounts[p.account]

    # Compute the sum of the postings
    noAmount = 0
    sum = 0
    for p in txn.postings:
        if p.amount:
            p.amount = any_to_amount(p.amount, decimal_sep, currency_sign, thousands_sep, p.source)
            sum += p.amount
        else:
            noAmount += 1

    # If there is more than two postings without amount, raise an exception
    if noAmount > 1:
        raise bberr.TxnMoreThanTwoPostingsWithNoAmount(txn.id)
    
    # If the sum is not 0 when there is no posting without amount, raise an exception 
    if noAmount == 0 and sum != 0:
        raise bberr.TxnNotBalanced(txn.id)
    
    # Set the amount of the posting without amount
    if noAmount == 1:
        for p in txn.postings:
            if not p.amount:
                p.amount = -sum
                break

    # if the date is a string, convert it to a date
    if not isinstance(txn.date, date):
        txn.date = read_date(txn.date)

    # Set the statement date of the postings to the transaction date
    for p in txn.postings:
        if not p.statement_date:
            p.statement_date = txn.date
        elif not isinstance(p.statement_date, date):
            try:
                p.statement_date = read_date(p.statement_date, p.source)
            except bberr.InvalidDateFormat as e:
                raise bberr.AddSourcePosition(p.source) from e

    # Set the parent transaction of the postings
    for p in txn.postings:
        if not p.parent_txn:
            p.parent_txn = txn

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