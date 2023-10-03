import csv

from datetime import date
from balancebook.csv import CsvFile, read_date
from balancebook.errors import SourcePosition
from balancebook.account import Account
from balancebook.amount import any_to_amount
from balancebook.transaction import Posting

class AmountType():
    """How to read the amount from the CSV file."""
    def __init__(self, single_amount_column: bool, column1: str, column2: str = None) -> None:
        self.single_amount_column = single_amount_column
        self.column1 = column1
        self.column2 = column2

    def is_inflow_outflow(self) -> bool:
        return not self.single_amount_column
    
    def is_single_amount_column(self) -> bool:
        return self.single_amount_column
    
    def inflow_column(self) -> str:
        return self.column1
    
    def outflow_column(self) -> str:
        return self.column2
    
    def amount_column(self) -> str:
        return self.column1

class CsvImportHeader():
    """Header of a bank CSV file."""
    def __init__(self, date: str, amount_type: AmountType, statement_date: str = None, 
                 statement_description: list[str] = None, statement_desc_join_sep: str = " | "):
        self.date = date
        self.statement_date = statement_date
        self.amount_type = amount_type
        self.statement_description = statement_description
        self.statement_desc_join_sep = statement_desc_join_sep

def import_bank_postings(csvFile : CsvFile, csv_header: CsvImportHeader, account: Account) -> list[tuple(str, Posting)]:
    """Import postings from a CSV file.
    
    All fields will be of type str.
    """
    csv_conf = csvFile.config
    line = 1
    with open(csvFile.path, encoding=csv_conf.encoding) as import_file:
        for _ in range(csv_conf.skip_X_lines):
            line += 1
            next(import_file)
        
        rows = csv.DictReader(import_file,
                        delimiter=csvFile.config.column_separator,
                        quotechar=csvFile.config.quotechar)
        
        rawtxns = []
        stdateHeader = csv_header.statement_date if csv_header.statement_date else csv_header.date
        for r in rows:
            dt = r[csv_header.date]
            if csv_header.amount_type.is_inflow_outflow():
                inflowHeader = csv_header.amount_type.inflow_column()
                outflowHeader = csv_header.amount_type.outflow_column()
                amount = (r[inflowHeader], r[outflowHeader])
            else:
                amntHeader = csv_header.amount_type.amount_column()
                amount = (r[amntHeader],)
            stdt = r[stdateHeader]
            desc = []
            for x in csv_header.statement_description:
                d = r[x].strip()
                if d:
                    desc.append(d)
            description = csv_header.statement_desc_join_sep.join(desc)
            p = Posting(None, account,amount,stdt,description,None,SourcePosition(csvFile.path, line, None))

            rawtxns.append((dt, p))
            line += 1

        return rawtxns
    
def normalize_bank_postings(bankps: list[tuple[str,Posting]],
                           decimal_sep: str = ".", currency_sign: str = "$", thousands_sep: str = " ") -> list[tuple[date, Posting]]:
    """Normalize the bank postings."""
    ps = []
    for dtstr, pstr in bankps:
        dt = read_date(dtstr)
        stdt = read_date(pstr.statement_date)
        if len(pstr.amount) == 1:
            s = pstr.amount[0] if pstr.amount[0] else "0"
            amount = any_to_amount(s, decimal_sep, currency_sign, thousands_sep, pstr.source)
        else:
            inflowS =  pstr.amount[0] if pstr.amount[0] else "0"
            inflow = any_to_amount(inflowS, decimal_sep, currency_sign, thousands_sep, pstr.source)
            outflowS = pstr.amount[1] if pstr.amount[1] else "0"
            outflow = any_to_amount(outflowS, decimal_sep, currency_sign, thousands_sep, pstr.source)
            amount = inflow - outflow
        p = Posting(pstr.account, amount, None,
                    stdt, pstr.statement_description, pstr.comment, pstr.source)
        ps.append((dt, p))
    return ps

# def first_match(raw_dt: date, raw_amnt: int, row: dict[str,str], rules: list[CsvRowRule]) -> CsvRowRule:
#     """Return the first rule that matches the row, or None if no rule matches."""
#     for rule in rules:
#         if rule.match_date[0] and raw_dt < rule.match_date[0]:
#             continue
#         if rule.match_date[1] and raw_dt > rule.match_date[1]:
#             continue

#         if rule.match_amnt[0] and raw_amnt < rule.match_amnt[0]:
#             continue
#         if rule.match_amnt[1] and raw_amnt > rule.match_amnt[1]:
#             continue

#         for k,regex in rule.match_columns.items():
#             # If the column value doesn't matches the regex, continue
#             s = row[k].strip()
#             if not re.fullmatch(regex, s):
#                 continue
        
#         return rule
    
#     return None

# def load_CsvRowRule(csvFile: CsvFile, match_prefix: str = None) -> list[CsvRowRule]:
#     """Load rules from a CSV file.

#     All fields will be of type str.
    
#     The CSV file must have the following columns:
#     - match_date: the date to match 
#     and/or
#         - match_date_from: the start date of the match period (included)
#         - match_date_to: the end date of the match period (included)
#     - match_amnt: the amount to match OR
#     and/or
#         - match_amnt_from: the start amount of the match period (included)
#         - match_amnt_to: the end amount of the match period (included)
#     - match_*: any other column is a column to match with a regex
#     - account1: the account to use for the first posting
#     - account2: the account to use for the second posting
#     - account1_comment: the comment to use for the first posting
#     - account2_comment: the comment to use for the second posting
#     - account1_use_csv_statement_date: if True, use the statement date from the CSV file for the first posting
#     - account2_use_csv_statement_date: if True, use the statement date from the CSV file for the second posting"""
#     csv_conf = csvFile.config
#     with open(csvFile.path, encoding=csv_conf.encoding) as import_file:
#         for _ in range(csv_conf.skip_X_lines):
#             next(import_file)
        
#         rows = csv.DictReader(import_file,
#                         delimiter=csvFile.config.column_separator,
#                         quotechar=csvFile.config.quotechar)
        
#         rules = []
#         match_date = (None, None)
#         match_amnt = (None, None)
#         if not match_prefix:
#             match_prefix = i18n["Match "]
#         dateCol = match_prefix + i18n["date"]
#         dateFromCol = match_prefix + i18n["date from"]
#         dateToCol = match_prefix + i18n["date to"]
#         amntCol = match_prefix + i18n["amount"]
#         amntFromCol = match_prefix + i18n["amount from"]
#         amntToCol = match_prefix + i18n["amount to"]
#         account1_comment_col = i18n["Account 1 comment"]
#         account2_comment_col = i18n["Account 2 comment"]
#         account1_stdt_col = i18n["Account 1 use csv statement date"]
#         account2_stdt_col = i18n["Account 2 use csv statement date"]
#         for r in rows:
#             if dateCol in r and r[dateCol].strip() :
#                 match_date = (r[dateCol].strip(), r[dateCol].strip())
#             else:
#                 if dateFromCol in r and r[dateFromCol].strip() :
#                     match_date = (r[dateFromCol].strip(), None)
#                 if dateToCol in r and r[dateToCol].strip() :
#                     match_date = (match_date[0], r[dateToCol].strip())
            
#             if amntCol in r and r[amntCol].strip() :
#                 match_amnt = (r[amntCol].strip(), r[amntCol].strip())
#             else:
#                 if amntFromCol in r and r[amntFromCol].strip() :
#                     match_amnt = (r[amntFromCol].strip(), None)
#                 if amntToCol in r and r[amntToCol].strip() :
#                     match_amnt = (match_amnt[0], r[amntToCol].strip())
            
#             match_columns = {}
#             for k in r.keys():
#                 if k.startswith(match_prefix):
#                     continue
#                 match_columns[k] = r[k].strip()
#             account1 = r[i18n["Account 1"]].strip()
#             account2 = r[i18n["Account 2"]].strip()
            
#             if account1_comment_col in r and r[account1_comment_col].strip():
#                 account1_comment = r[account1_comment_col].strip()
#             else:
#                 account1_comment = None
            
#             if account2_comment_col in r and r[account2_comment_col].strip():
#                 account2_comment = r[account2_comment_col].strip()
#             else:
#                 account2_comment = None
            
#             if account1_stdt_col in r:
#                 account1_use_csv_statement_date = r[account1_stdt_col].strip() == i18n["True"]
#             else:
#                 account1_use_csv_statement_date = True

#             if account2_stdt_col in r:
#                 account2_use_csv_statement_date = r[account2_stdt_col].strip() == i18n["True"]
#             else:
#                 account2_use_csv_statement_date = False

#             rules.append(CsvRowRule(match_date, match_amnt, match_columns, account1, account2, account1_use_csv_statement_date, account2_use_csv_statement_date, account1_comment, account2_comment))
        
#         return rules
    
# def normalize