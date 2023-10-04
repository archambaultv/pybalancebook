import csv

from datetime import date
from balancebook.csv import CsvFile, load_csv
from balancebook.account import Account
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

def import_bank_postings(csvFile : CsvFile, csv_header: CsvImportHeader, account: Account) -> list[tuple[date, Posting]]:
    """Import postings from a CSV file.
    
    All fields will be of type str.
    """
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
        source = row[len(header)]
        if csv_header.amount_type.is_single_amount_column():
            amount = row[1]
        else:
            inflow = row[1] if row[1] else 0
            outflow = row[2] if row[2] else 0
            amount = inflow - outflow
        if csv_header.statement_date and row[st_date_idx]:
            st_date = row[st_date_idx]
        else:
            st_date = row[0]
        if csv_header.statement_description:
            ds = [x for x in row[st_desc_idx:-1] if x is not None]
            st_desc = csv_header.statement_desc_join_sep.join(ds)
        p = Posting(account, amount, None, st_date, st_desc, None, source)
        ls.append((row[0], p))

    return ls