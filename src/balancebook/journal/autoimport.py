import logging
import re
import os
from yaml import safe_load

from datetime import date
from balancebook.csv import CsvFile, load_csv, write_csv,SourcePosition, CsvConfig, load_config_from_yaml
import balancebook.errors as bberr
from balancebook.amount import amount_to_str
from balancebook.account import Account
from balancebook.transaction import Posting, Txn
from balancebook.i18n import I18n, translate_json_dict_to_en

logger = logging.getLogger(__name__)

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


class AmountType():
    """How to read the amount from the CSV file."""
    def __init__(self, single_amount_column: bool, 
                 column_inflow: str, 
                 column_outflow: str = None) -> None:
        self.single_amount_column = single_amount_column
        self.column_inflow = column_inflow
        self.column_outflow = column_outflow

    def is_inflow_outflow(self) -> bool:
        return not self.single_amount_column
    
    def is_single_amount_column(self) -> bool:
        return self.single_amount_column
    
    def inflow_column(self) -> str:
        return self.column_inflow
    
    def outflow_column(self) -> str:
        return self.column_outflow
    
    def amount_column(self) -> str:
        return self.column_inflow

class CsvImportHeader():
    """Header of a bank CSV file."""
    def __init__(self, date: str, amount_type: AmountType, statement_date: str = None, 
                 statement_description: list[str] = None, statement_desc_join_sep: str = " ~ "):
        self.date = date
        self.statement_date = statement_date
        self.amount_type = amount_type
        self.statement_description = statement_description
        self.statement_desc_join_sep = statement_desc_join_sep

class CsvImportConfig():
    def __init__(self, 
                 account: Account,
                 csv_config: CsvConfig, 
                 csv_header: CsvImportHeader, 
                 default_snd_account: Account, 
                 import_zero_amount: bool = True):
        self.account = account
        self.csv_config = csv_config
        self.csv_header = csv_header
        self.default_snd_account = default_snd_account
        self.import_zero_amount = import_zero_amount

def load_import_config(file: str, accounts_by_name: dict[str, Account], i18n: I18n = None) -> CsvImportConfig:
    source = SourcePosition(file, None, None)
    with open(file, 'r') as f:
        data = safe_load(f)
        if i18n and not i18n.is_default():
            data = translate_json_dict_to_en(data, i18n)

        if "account" not in data:
            raise bberr.MissingRequiredKey("account", source)
        account = data["account"]
        if account not in accounts_by_name:
            raise bberr.UnknownAccount(account, source)
        account = accounts_by_name[account]

        if "csv config" in data:
            csv_config = load_config_from_yaml(data["csv config"], source)
        else:
            csv_config = CsvConfig()
        
        if "header" not in data:
            raise bberr.MissingRequiredKey("header", source)
        
        if "date" not in data["header"]:
            raise bberr.MissingRequiredKey("header:date", source)
        date = data["header"]["date"]
    
        if "amount" not in data["header"]:
            raise bberr.MissingRequiredKey("header:amount", source)
        if "type" not in data["header"]["amount"]:
            raise bberr.MissingRequiredKey("header:amount:type", source)
        
        amount_type = data["header"]["amount"]["type"]
        if amount_type == i18n["Single column"]:
            if "column" not in data["header"]["amount"]:
                raise bberr.MissingRequiredKey("header:amount:column", source)
            amount_type = AmountType(True, data["header"]["amount"]["column"])
        elif amount_type == i18n["Inflow outflow"]:
            if "inflow" not in data["header"]["amount"]:
                raise bberr.MissingRequiredKey("header:amount:inflow", source)
            if "outflow" not in data["header"]["amount"]:
                raise bberr.MissingRequiredKey("header:amount:outflow", source)
            amount_type = AmountType(False, data["header"]["amount"]["inflow"], data["header"]["amount"]["outflow"])
        else:
            raise bberr.UnknownAccountType(amount_type,source)
        st_date = data["header"].get("statement date", None)
        st_desc = data["header"].get("statement description", None)
        h = CsvImportHeader(date, amount_type, st_date, st_desc)

        if "default second account" not in data:
            raise bberr.MissingRequiredKey("default second account", source)
        default_snd_account = data["default second account"]
        if default_snd_account not in accounts_by_name:
            raise bberr.UnknownAccount(default_snd_account, source)
        default_snd_account = accounts_by_name[default_snd_account]

        if "import zero amount" in data:
            import_zero_amount = data["import zero amount"]
        else:
            import_zero_amount = True

        return CsvImportConfig(account, csv_config, h, default_snd_account, import_zero_amount)

def load_classification_rules(csvFile: CsvFile, 
                              accounts_by_number: dict[str,Account], 
                              filter_drop_all: bool = True,
                              i18n: I18n = None) -> list[ClassificationRule]:
    """Load classification rules from the csv file
    
    By defaut does not load drop all rules to avoid discarding all transactions by mistake."""

    if i18n is None:
        i18n = I18n()

    csv_rows = load_csv(csvFile, [(i18n["Date from"], "date", True, False), 
                                  (i18n["Date to"], "date", True, False), 
                                  (i18n["Amount from"], "amount", True, False), 
                                  (i18n["Amount to"], "amount", True, False), 
                                  (i18n["Account"], "str", True, False), 
                                  (i18n["Statement description"], "str", True, False), 
                                  (i18n["Second account"], "str", True, False),
                                  (i18n["Comment"], "str", True, False)])
    rules = []
    for row in csv_rows:
        source = row[8]
        if row[6] is None:
            acc2 = None
        elif row[6] not in accounts_by_number:
            raise bberr.UnknownAccount(row[6], source)
        else:
            acc2 = accounts_by_number[row[6]]
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

def write_classification_rules(rules: list[ClassificationRule], csvFile: CsvFile, ) -> None:
    """Write classification rules to file."""
    data = write_classification_rules_to_list(rules, csvFile.config.decimal_separator)
    write_csv(data, csvFile)

def write_classification_rules_to_list(rules: list[ClassificationRule], decimal_separator = ".") -> list[list[str]]:
    rows = [["Date from","Date to","Amount from","Amount to","Account","Statement description","Second account","Comment"]]
    for r in rules:
        ident = r.second_account.identifier if r.second_account else None
        amnt_from = amount_to_str(r.match_amnt[0],decimal_separator) if r.match_amnt[0] is not None else None
        amnt_to = amount_to_str(r.match_amnt[1],decimal_separator) if r.match_amnt[1] is not None else None
        rows.append([r.match_date[0], 
                            r.match_date[1], 
                            amnt_from, 
                            amnt_to, 
                            r.match_account, r.match_statement_description, ident, r.comment])
    return rows

def import_bank_postings(csvFile : CsvFile, csv_header: CsvImportHeader, account: Account,
                         import_zero_amount: bool = True) -> list[Posting]:
    """Import postings from a CSV file."""

    # Build the csv header according to csv_header
    if csv_header.amount_type.is_single_amount_column():
        header = [(csv_header.date, "date", True, True), 
                  (csv_header.amount_type.amount_column(), "amount", True, True)]
        st_date_idx = 2
    else:
        header = [(csv_header.date, "date", True), 
                  (csv_header.amount_type.inflow_column(), "amount", True, False),
                  (csv_header.amount_type.outflow_column(), "amount", True, False)]
        st_date_idx = 3

    if csv_header.statement_date:
        header.append((csv_header.statement_date, "date", True, False))
        st_desc_idx = st_date_idx + 1
    else:
        st_desc_idx = st_date_idx

    if csv_header.statement_description:
        for x in csv_header.statement_description:
            header.append((x, "str", True, False))

    csv_rows = load_csv(csvFile, header)
    ls = []
    for row in csv_rows:
        dt = row[0]
        source = row[-1]
        if csv_header.amount_type.is_single_amount_column():
            amount = row[1]
        else:
            inflow = row[1] if row[1] else 0
            outflow = row[2] if row[2] else 0
            amount = inflow - outflow

        if csv_header.statement_date and row[st_date_idx]:
            st_date = row[st_date_idx]
        else:
            st_date = dt

        if csv_header.statement_description:
            # Join all the statement description columns
            ds = [x for x in row[st_desc_idx:-1] if x is not None]
            st_desc = csv_header.statement_desc_join_sep.join(ds)
        else:
            st_desc = None

        p = Posting(dt, account, amount, st_date, st_desc, None, source)
        if not import_zero_amount and p.amount == 0:
            continue
        ls.append(p)

    return ls

def import_from_bank_csv(csvFile : CsvFile, 
                         import_config: CsvImportConfig,
                         rules: list[ClassificationRule],
                         from_date: date = None,
                         known_postings: dict[tuple[date,str,int,str], int] = None) -> list[Txn]:
    """Import the transactions from the bank csv file
    
    Does not modify the journal.
    """

    # Load posting from file
    csvPs = import_bank_postings(csvFile, import_config.csv_header, 
                                 import_config.account, import_config.import_zero_amount)

    # Filter postings if:
    #   the before from_date
    #   the posting is in known_postings
    unknownPs = []
    keys = known_postings if known_postings else {}               
    for p in csvPs:
        if from_date and p.date < from_date:
            logger.info(f"Skipping posting {p} because its date is before the from_date {from_date}\n{p.source}")
            continue
        
        k = p.dedup_key()
        if k in keys:
            if keys[k] == 1:
                del keys[k]
            else:
                keys[k] -= 1
            logger.info(f"Skipping posting {p} because it is already in a transaction\n{p.source}")
            continue

        unknownPs.append(p)

    # Apply classification rules
    return classify(unknownPs, rules, import_config.default_snd_account)

def classify(ps: list[Posting], rules: list[ClassificationRule],
             default_snd_account: Account) -> list[Txn]:
    """Classify the transactions according to the rules.
    
    The rules are applied in the order they are provided.
    If no rule matches, we use the default_snd_account.
    """
            
    ls = []
    for p in ps:
        # Find the first rule that matches
        r = None
        for rule in rules:
            if rule.match_date[0] and p.date < rule.match_date[0]:
                continue
            if rule.match_date[1] and p.date > rule.match_date[1]:
                continue

            if rule.match_amnt[0] and p.amount < rule.match_amnt[0]:
                continue
            if rule.match_amnt[1] and p.amount > rule.match_amnt[1]:
                continue

            # Match account identifier with a full regex
            if rule.match_account and not re.match(rule.match_account, p.account.identifier):
                continue

            # Match statement description with a full regex
            if rule.match_statement_description and (p.statement_description is None or 
                                                        not re.match(rule.match_statement_description, 
                                                                    p.statement_description)):
                continue

            # We have a match
            r = rule
            break

        acc2 = default_snd_account
        comment = None
        if r:
            if not r.second_account:
                logger.info(f"Discarding posting {p} because no second account is provided by the rule")
                continue
            else:
                acc2 = r.second_account
            if r.comment:
                comment = r.comment
            else:
                comment = None
        t = Txn(None, [])
        p1 = Posting(p.date, p.account, p.amount,  p.statement_date, p.statement_description, comment, p.source)
        p2 = Posting(p.date, acc2, - p.amount, p.statement_date, p.statement_description, comment, None)
        t.postings = [p1, p2]
        ls.append(t)

    return ls