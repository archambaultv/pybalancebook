import csv
import logging
import re
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

class ClassificationRule():
    """Rule to reclassify a transaction.

    If one of the posting matches the rule, the transaction is reclassified.
    All other postings are discarded and the transaction is balanced with the
    second account provided in the rule.

    If second account is None, the transaction is discarded.
    """
    def __init__(self, match_date: (date, date), 
                       match_amnt: (int, int), 
                       match_account: str,
                       match_statement_description: str,
                       second_account: Account,
                       comment: str = None,
                       source: SourcePosition = None) -> None:
        self.match_date = match_date
        self.match_amnt = match_amnt
        self.match_account = match_account
        self.match_statement_description = match_statement_description
        self.second_account = second_account
        self.comment = comment
        self.source = source

    def is_drop_all_rule(self) -> bool:
        """Return True if the rule is a drop all rule"""
        return all([True if x is None else False for x in 
                    [self.match_date[0], self.match_date[1], 
                     self.match_amnt[0], self.match_amnt[1], 
                     self.match_account, self.match_statement_description,
                     self.second_account]])
    
    def __str__(self):
        return f"ClassificationRule({self.match_date}, {self.match_amnt}, {self.match_account}, {self.match_statement_description}, {self.second_account})"

def load_txns(csvFile: CsvFile, accounts_by_id: dict[str,Account]) -> list[Txn]:
    """Load transactions from the yaml file
    
    Verify the consistency of the transactions"""
    csv_rows = load_csv(csvFile, [("Id", "int", True, True), 
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

# Export transactions to a csv file
def write_txns(txns: list[Txn], csvFile: CsvFile, extra_columns: bool = False,
               first_fiscal_month = 1):
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
    
def reclassify(txns: list[Txn], rules: list[ClassificationRule]) -> list[Txn]:
    """Reclassify the transactions according to the rules.
    
    The rules are applied in the order they are provided.
    The transactions are modified in place.
    """
    ls = []
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
                if rule.match_account and not re.match(rule.match_account, p.account.identifier):
                    continue

                # Match statement description with a full regex
                if rule.match_statement_description and not re.match(rule.match_statement_description, p.statement_description):
                    continue

                p_match = p
                r = rule
                break

            if p_match:
                break

        if r:
            if not r.second_account:
                logger.info(f"Discarding transaction {t} because no second account is provided by the rule")
                continue
            new_t = Txn(t.id, t.date, [])
            if r.comment:
                comment = r.comment
            else:
                comment = p_match.comment
            p1 = Posting(p_match.account, p_match.amount, new_t, p_match.statement_date, p_match.statement_description, comment, p_match.source)
            p2 = Posting(r.second_account, - p_match.amount, new_t, new_t.date, p_match.statement_description, comment, None)
            new_t.postings = [p1, p2]
            ls.append(new_t)
        else:
            ls.append(t)

    return ls

def load_classification_rules(csvFile: CsvFile, accounts_by_id: dict[str,Account], filter_drop_all: bool = True) -> list[ClassificationRule]:
    """Load classification rules from the csv file
    
    By defaut does not load drop all rules to avoid discarding all transactions by mistake."""
    csv_rows = load_csv(csvFile, [("Date from", "date", True, False), 
                                  ("Date to", "date", True, False), 
                                  ("Amount from", "amount", True, False), 
                                  ("Amount to", "amount", True, False), 
                                  ("Account", "str", True, False), 
                                  ("Statement description", "str", True, False), 
                                  ("Second account", "str", True, False),
                                  ("Comment", "str", True, False)])
    rules = []
    for row in csv_rows:
        source = row[8]
        if row[6] is None:
            acc2 = None
        elif row[6] not in accounts_by_id:
            raise bberr.UnknownAccount(row[6], source)
        else:
            acc2 = accounts_by_id[row[6]]
        mdate = (row[0], row[1])
        mamnt = (row[2], row[3])
        acc_re = row[4]
        desc_re = row[5]
        comment = row[7]
        r = ClassificationRule(mdate, mamnt, acc_re, desc_re, acc2,comment, source)
        if filter_drop_all and r.is_drop_all_rule():
            logger.info(f"Skipping drop all rule at {r.source}")
            continue
        rules.append(r)
    return rules

def write_classification_rules(csvFile: CsvFile, rules: list[ClassificationRule]) -> None:
    """Write classification rules to file."""
    csv_conf = csvFile.config
    with open(csvFile.path, 'w', encoding=csv_conf.encoding) as xlfile:
        writer = csv.writer(xlfile, delimiter=csv_conf.column_separator,
                          quotechar=csv_conf.quotechar, quoting=csv.QUOTE_MINIMAL)
        header = ["Date from","Date to","Amount from","Amount to","Account","Statement description","Second account","Comment"]
        writer.writerow(header)
        for r in rules:
            ident = r.second_account.identifier if r.second_account else None
            amnt_from = amount_to_str(r.match_amnt[0],csv_conf.decimal_separator) if r.match_amnt[0] else None
            amnt_to = amount_to_str(r.match_amnt[1],csv_conf.decimal_separator) if r.match_amnt[1] else None
            writer.writerow([r.match_date[0], 
                             r.match_date[1], 
                             amnt_from, 
                             amnt_to, 
                             r.match_account, r.match_statement_description, ident, r.comment])