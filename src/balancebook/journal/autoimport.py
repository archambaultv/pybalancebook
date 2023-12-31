import logging
import re
import os
from yaml import safe_load

from datetime import date
from balancebook.csv import CsvFile, load_csv, write_csv,SourcePosition, CsvConfig, CsvColumn
import balancebook.errors as bberr
from balancebook.errors import add_source_position
from balancebook.amount import amount_to_str
from balancebook.account import Account
from balancebook.transaction import Posting, Txn
from balancebook.i18n import I18n
from balancebook.yaml import YamlElement, decode_yaml, csv_config_spec, space_to_underscore

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
                       match_payee: str,
                       second_account: Account,
                       payee: str = None,
                       comment: str = None,
                       source: SourcePosition = None) -> None:
        self.match_date = match_date
        self.match_amnt = match_amnt
        self.match_account = match_account
        self.match_statement_description = match_statement_description
        self.match_payee = match_payee
        self.second_account = second_account
        self.payee = payee
        self.comment = comment
        self.source = source

    def is_drop_all_rule(self) -> bool:
        """Return True if the rule is a drop all rule"""
        return all([True if x is None else False for x in 
                    [self.match_date[0], self.match_date[1], 
                     self.match_amnt[0], self.match_amnt[1], 
                     self.match_account, self.match_statement_description,
                     self.match_payee,
                     self.second_account]])
    
    def __str__(self):
        return f"ClassificationRule({self.match_date}, {self.match_amnt}, {self.match_account}, {self.match_statement_description}, {self.match_payee}, {self.second_account})"

class AmountType():
    """How to read the amount from the CSV file."""
    def __init__(self, single_amount_column: bool, 
                 column_amount_or_inflow: str, 
                 column_outflow: str = None) -> None:
        self.single_amount_column = single_amount_column
        self.column_amount_or_inflow = column_amount_or_inflow
        self.column_outflow = column_outflow

    def is_inflow_outflow(self) -> bool:
        return not self.single_amount_column
    
    def is_single_amount_column(self) -> bool:
        return self.single_amount_column
    
    def inflow_column(self) -> str:
        return self.column_amount_or_inflow
    
    def outflow_column(self) -> str:
        return self.column_outflow
    
    def amount_column(self) -> str:
        return self.column_amount_or_inflow

class CsvImportHeader():
    """Header of a bank CSV file."""
    def __init__(self, date: str, amount_type: AmountType, payee: list[str] = None,
                 statement_date: str = None, 
                 statement_description: list[str] = None, join_sep: str = " ~ "):
        self.date = date
        self.amount_type = amount_type
        self.payee = payee
        self.statement_date = statement_date
        self.statement_description = statement_description
        self.join_sep = join_sep

class CsvImportConfig():
    def __init__(self, 
                 account: Account,
                 csv_config: CsvConfig, 
                 csv_header: CsvImportHeader, 
                 default_snd_account: Account, 
                 classification_rule_file: CsvFile = None,
                 import_zero_amount: bool = True):
        self.account = account
        self.csv_config = csv_config
        self.csv_header = csv_header
        self.default_snd_account = default_snd_account
        self.classification_rule_file = classification_rule_file
        self.import_zero_amount = import_zero_amount

def load_import_config(file: str, accounts_by_name: dict[str, Account], 
                       default_csv_config: CsvConfig = None,
                       i18n: I18n = None) -> CsvImportConfig:
    source = SourcePosition(file, None, None)
    dir = os.path.dirname(file)
    if i18n is None:
        i18n = I18n()

    if default_csv_config is None:
        default_csv_config = CsvConfig()

    def mk_path_abs(path: str) -> str:
        """Make a path absolute if it is not already, up to the root folder"""
        if not os.path.isabs(path):
            return os.path.normpath(os.path.join(dir, path))
        else:
            return path
    
    with open(file, 'r') as f:
        data = safe_load(f)

        default_csv_spec = csv_config_spec()
        default_csv_spec.default = default_csv_config
        
        spec = YamlElement("dict", dict_type={
            "account": YamlElement("str", required=True),
            "csv config": default_csv_spec,
            "header": YamlElement("dict", dict_type={
                "date": YamlElement("str", required=True, default="Date"),
                "amount": YamlElement("dict", dict_type={
                    "type": YamlElement("str", required=True),
                    "column": YamlElement("str", required=False),
                    "inflow": YamlElement("str", required=False),
                    "outflow": YamlElement("str", required=False)
                }, required=True),
                "payee": YamlElement("list", required=False, list_type=YamlElement("str", required=True)),
                "statement date": YamlElement("str", required=False),
                "statement description": YamlElement("list", required=False, list_type=YamlElement("str", required=True)),
                "join separator": YamlElement("str", required=False)
            }, required=True),
            "default second account": YamlElement("str", required=True),
            "classification": YamlElement("dict", dict_type={
                "file": YamlElement("str", required=True)
            }, required=False),
            "import zero amount": YamlElement("bool", required=False, default=True)})

        data = add_source_position(source)(decode_yaml)(data, spec, warn_extra_keys=True, i18n=i18n)

        account = data["account"]
        if account not in accounts_by_name:
            raise bberr.UnknownAccount(account, source)
        account = accounts_by_name[account]

        csv_config = CsvConfig(**space_to_underscore(data["csv config"]))

        classification = None
        if "classification" in data:           
            classification = CsvFile(mk_path_abs(data["classification"]["file"]), default_csv_config)
        
        date = data["header"]["date"]
        
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
        payee = data["header"].get("payee", None)
        st_date = data["header"].get("statement date", None)
        st_desc = data["header"].get("statement description", None)
        st_join = data["header"].get("join separator", " ~ ")
        header = CsvImportHeader(date, amount_type, payee, st_date, st_desc, st_join)

        default_snd_account = data["default second account"]
        if default_snd_account not in accounts_by_name:
            raise bberr.UnknownAccount(default_snd_account, source)
        default_snd_account = accounts_by_name[default_snd_account]

        import_zero_amount = data["import zero amount"]

        return CsvImportConfig(account, csv_config, header, default_snd_account, classification, import_zero_amount)

def load_classification_rules(csvFile: CsvFile, 
                              accounts_by_number: dict[str,Account], 
                              filter_drop_all: bool = True,
                              i18n: I18n = None) -> list[ClassificationRule]:
    """Load classification rules from the csv file
    
    By defaut does not load drop all rules to avoid discarding all transactions by mistake."""

    if i18n is None:
        i18n = I18n()

    date_from_i18n = i18n["Date from"]
    date_to_i18n = i18n["Date to"]
    amnt_from_i18n = i18n["Amount from"]
    amnt_to_i18n = i18n["Amount to"]
    account_i18n = i18n["Account"]
    st_desc_i18n = i18n["Statement description"]
    st_payee_i18n = i18n["Statement payee"]
    acc2_i18n = i18n["Second account"]
    comment_i18n = i18n["Comment"]
    payee_i18n = i18n["Payee"]

    csv_rows = load_csv(csvFile, [CsvColumn(date_from_i18n, "date", True, False), 
                                  CsvColumn(date_to_i18n, "date", True, False), 
                                  CsvColumn(amnt_from_i18n, "amount", True, False), 
                                  CsvColumn(amnt_to_i18n, "amount", True, False), 
                                  CsvColumn(account_i18n, "str", True, False), 
                                  CsvColumn(st_desc_i18n, "str", True, False), 
                                  CsvColumn(acc2_i18n, "str", True, False),
                                  CsvColumn(comment_i18n, "str", False, False),
                                  CsvColumn(payee_i18n, "str", False, False),
                                  CsvColumn(st_payee_i18n, "str", True, False)],
                                  warn_extra_columns=True)
    rules = []
    for row, source in csv_rows:
        if row[acc2_i18n] is None:
            acc2 = None
        elif row[acc2_i18n] not in accounts_by_number:
            raise bberr.UnknownAccount(row[acc2_i18n], source)
        else:
            acc2 = accounts_by_number[row[acc2_i18n]]
        mdate = (row[date_from_i18n], row[date_to_i18n])
        mamnt = (row[amnt_from_i18n], row[amnt_to_i18n])
        acc_re = row[account_i18n]
        desc_re = row[st_desc_i18n]
        comment = row[comment_i18n]
        payee = row[payee_i18n]
        st_payee = row[st_payee_i18n]
        r = ClassificationRule(mdate, mamnt, acc_re, desc_re, st_payee, acc2, payee, comment, source)
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
    rows = [["Date from","Date to","Amount from","Amount to","Account","Statement description",
             "Statement payee","Second account","Payee","Comment"]]
    for r in rules:
        ident = r.second_account.identifier if r.second_account else ""
        amnt_from = amount_to_str(r.match_amnt[0],decimal_separator) if r.match_amnt[0] is not None else ""
        amnt_to = amount_to_str(r.match_amnt[1],decimal_separator) if r.match_amnt[1] is not None else ""
        payee = r.payee if r.payee else ""
        comment = r.comment if r.comment else ""
        st_payee = r.match_payee if r.match_payee else ""
        rows.append([r.match_date[0], 
                            r.match_date[1], 
                            amnt_from, 
                            amnt_to, 
                            r.match_account, r.match_statement_description, st_payee, ident,payee, comment])
    return rows

def import_bank_postings(csvFile : CsvFile, csv_header: CsvImportHeader, account: Account,
                         import_zero_amount: bool = True) -> list[Posting]:
    """Import postings from a CSV file."""

    # Build the csv header according to csv_header
    if csv_header.amount_type.is_single_amount_column():
        header = [CsvColumn(csv_header.date, "date", True, True), 
                  CsvColumn(csv_header.amount_type.amount_column(), "amount", True, True)]
    else:
        header = [CsvColumn(csv_header.date, "date", True, True), 
                  CsvColumn(csv_header.amount_type.inflow_column(), "amount", True, False, default_value=0),
                  CsvColumn(csv_header.amount_type.outflow_column(), "amount", True, False, default_value=0)]

    if csv_header.statement_date:
        header.append(CsvColumn(csv_header.statement_date, "date", True, False))

    if csv_header.statement_description:
        for x in csv_header.statement_description:
            header.append(CsvColumn(x, "str", True, False))

    if csv_header.payee:
        for x in csv_header.payee:
            header.append(CsvColumn(x, "str", False, False))

    csv_rows = load_csv(csvFile, header, warn_extra_columns=False)
    ls = []
    for row, source in csv_rows:
        dt = row[csv_header.date]
        if csv_header.amount_type.is_single_amount_column():
            amount = row[csv_header.amount_type.amount_column()]
        else:
            inflow = row[csv_header.amount_type.inflow_column()]
            outflow = row[csv_header.amount_type.outflow_column()]
            amount = inflow - outflow

        if not import_zero_amount and amount == 0:
            continue

        if csv_header.statement_date and row[csv_header.statement_date]:
            st_date = row[csv_header.statement_date]
        else:
            st_date = dt

        if csv_header.statement_description:
            # Join all the statement description columns
            ds = [row[x] for x in csv_header.statement_description if row[x] is not None]
            st_desc = csv_header.join_sep.join(ds)
        else:
            st_desc = None

        if csv_header.payee:
            # Join all the payee columns
            ds = [row[x] for x in csv_header.payee if row[x] is not None]
            payee = csv_header.join_sep.join(ds)
        else:
            payee = None

        p = Posting(dt, account, amount, payee, st_date, st_desc, None, source)

        ls.append(p)

    return ls

def import_from_bank_csv(csvFile : CsvFile, 
                         import_config: CsvImportConfig,
                         rules: list[ClassificationRule],
                         from_date: date = None,
                         known_postings: dict[tuple[date,str,int,str], int] = None) -> list[tuple[bool, Txn]]:
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
             default_snd_account: Account) -> list[tuple[bool, Txn]]:
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

            # Match payee with a full regex
            if rule.match_payee and (p.payee is None or not re.match(rule.match_payee, p.payee)):
                continue

            # We have a match
            r = rule
            break

        acc2 = default_snd_account
        comment = None
        payee = p.payee
        matched = False
        if r:
            matched = True
            if not r.second_account:
                logger.info(f"Discarding posting {p} because no second account is provided by the rule")
                continue
            else:
                acc2 = r.second_account
            if r.comment:
                comment = r.comment
            if r.payee:
                payee = r.payee

        t = Txn(None, [])
        p1 = Posting(p.date, p.account, p.amount, payee,  p.statement_date, p.statement_description, comment, p.source)
        p2 = Posting(p.date, acc2, - p.amount, payee, p.statement_date, p.statement_description, comment, None)
        t.postings = [p1, p2]
        ls.append((matched, t))

    return ls