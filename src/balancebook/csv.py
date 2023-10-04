
import os
import logging
import csv
from datetime import date

import balancebook.errors as bberr
from balancebook.errors import SourcePosition
from balancebook.amount import any_to_amount

logger = logging.getLogger(__name__)

class CsvConfig:
    """Configuration for CSV files."""
    def __init__(self, encoding = "utf-8", column_separator = ",", quotechar = "\"", decimal_separator = ".",
                 skip_X_lines = 0, join_separator = " | ", thousands_separator = " ", currency_sign = "$"):
        self.encoding = encoding
        self.column_separator = column_separator
        self.quotechar = quotechar
        self.decimal_separator = decimal_separator
        self.skip_X_lines = skip_X_lines
        self.join_separator = join_separator
        self.thousands_separator = thousands_separator
        self.currency_sign = currency_sign

class CsvFile:
    """CSV file to be read."""
    def __init__(self, path, csv_config = None):
        self.path = path
        if csv_config:
            self.config = csv_config
        else:
            self.config = CsvConfig()

def read_date(s: str, source: SourcePosition = None) -> date:
    """Read a date from a string in the format YYYY-MM-DD."""
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise bberr.InvalidDateFormat(s, source) from e

def read_int(s: str, source: SourcePosition = None) -> int:
    """Read an integer from a string."""
    try:
        return int(s)
    except ValueError as e:
        raise bberr.InvalidInt(s, source) from e

def read_value(s: str, type: str, csv_conf: CsvConfig, source: SourcePosition = None) -> any:
    """Read a value from a string."""
    if type == "str":
        return s
    elif type == "int":
        return read_int(s, source)
    elif type == "date":
        return read_date(s, source)
    elif type == "amount":
        return any_to_amount(s, csv_conf.decimal_separator, csv_conf.currency_sign, csv_conf.thousands_separator, source)
    else:
        raise bberr.InvalidCsvType(type, source)

def load_csv(csv_file: CsvFile, header: list[tuple[str,str,bool]]) -> list[tuple]:
    """Load a CSV file and return a list of tuples.

    The header is a list of tuples (column name, type, required).
    The type can be one of: str, int, date, amount.
    The returned list contains one tuple per row. 
    Its length is the same as the header plus one for the SourcePosition.
    """
    # if file does not exist, return an empty list
    if not os.path.exists(csv_file.path):
        logger.warn(f"Csv file ${csv_file.path} does not exist")
        return []
    
    csv_conf = csv_file.config
    line = 1
    with open(csv_file.path, encoding=csv_conf.encoding) as f:
        for _ in range(csv_conf.skip_X_lines):
            next(f)
            line += 1

        rows = csv.DictReader(f, delimiter=csv_conf.column_separator,
                              quotechar=csv_conf.quotechar)
        
        # Check that the required columns are present
        for h in header:
            if h[2] and h[0] not in rows.fieldnames:
                raise bberr.MissingHeader(h[0], SourcePosition(csv_file.path, line, None))
            
        # Build the list of present columns
        present_columns = [True if h[0] in rows.fieldnames else False for h in header]

        line += 1 # header line
        ls = []
        for r in rows:
            rowdata = []
            source = SourcePosition(csv_file.path, line, None)
            for i, h in enumerate(header):
                if not present_columns[i]:
                    rowdata.append(None)
                    continue

                if r[h[0]] is None:
                    if h[2]:
                        raise bberr.RequiredColumnEmpty(h[0], source)
                    else:
                        rowdata.append(None)
                        continue

                value = r[h[0]].strip()
                if not value:
                    if h[2]:
                        raise bberr.RequiredColumnEmpty(h[0], source)
                    else:
                        rowdata.append(None)
                        continue

                value = read_value(value, h[1], csv_conf, source)
                rowdata.append(value)

            rowdata.append(source)
            ls.append(tuple(rowdata))
            line += 1
            
        return ls