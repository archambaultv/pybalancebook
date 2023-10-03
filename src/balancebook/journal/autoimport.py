import csv

from datetime import date
from balancebook.csv import CsvFile, read_date
from balancebook.errors import SourcePosition
from balancebook.account import Account
from balancebook.amount import any_to_amount
from balancebook.transaction import Posting

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
                 statement_description: list[str] = None, statement_desc_join_sep: str = " | "):
        self.date = date
        self.statement_date = statement_date
        self.amount_type = amount_type
        self.statement_description = statement_description
        self.statement_desc_join_sep = statement_desc_join_sep

def import_bank_postings(csvFile : CsvFile, csv_header: CsvImportHeader, account: Account) -> list[tuple[str, Posting]]:
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
            p = Posting(account,amount,None,stdt,description,None,SourcePosition(csvFile.path, line, None))

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