
import os
import logging
import csv
from datetime import date, datetime

import balancebook.errors as bberr
from balancebook.errors import SourcePosition
from balancebook.amount import any_to_amount

logger = logging.getLogger(__name__)

class CsvConfig:
    """Configuration for CSV files."""
    def __init__(self, encoding = "utf-8", column_separator = ",", quotechar = "\"", decimal_separator = ".",
                 skip_X_lines = 0, join_separator = " ~ ", thousands_separator = " ", currency_sign = "$"):
        # The default join separator is " ~ " because 
        # - it is not a usual CSV column separator like ',' or ';'
        # - it is not a special character for python regex like '|' or '.'
        # - it is a visible character

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

    def __str__(self) -> str:
        return self.path

def load_config_from_yaml(data: dict[str,str], source: SourcePosition = None) -> CsvConfig:
    """Load a YAML config for CSV file."""
    csv_config = CsvConfig()
    csv_config = CsvConfig(data.get("encoding", csv_config.encoding),
                           data.get("column separator", csv_config.column_separator),
                           data.get("quotechar", csv_config.quotechar),
                           data.get("decimal separator", csv_config.decimal_separator),
                           read_int(data.get("skip X lines", csv_config.skip_X_lines), source),
                           data.get("join separator", csv_config.join_separator),
                           data.get("thousands separator", csv_config.thousands_separator),
                           data.get("currency sign", csv_config.currency_sign))
    # Warns about unknown keys
    for k in data.keys():
        if k not in ["encoding", "column separator", "quotechar", 
                     "decimal separator", "skip X lines", 
                     "join separator", "thousands separator", "currency sign"]:
            ifSource = f" in {source.file}" if source else ""
            logger.warning(f"Unknown key '{k}' in CSV config{ifSource}.")
    return csv_config

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
    elif type == "ymdate":
        return read_yyyy_mm_date(s, source)
    else:
        raise bberr.InvalidCsvType(type, source)

def read_yyyy_mm_date(s: str, source: SourcePosition = None) -> date:
    """Reads a month and year from a string."""
    # Thanks to excel, yyyy-mm date can be 
    # YYYY-MM-DD, 
    # mmm-YY 
    # YY-mmm or 
    # YYYY-MM
    dt = s.strip()
    dt_array = dt.split("-")
    if len(dt_array) == 3:
        # YYYY-MM-DD
        dt = date.fromisoformat(dt)
    else:
        len1 = len(dt_array[0])
        len2 = len(dt_array[1])
        d1 = dt_array[0][0].isdigit() # Starts with a digit
        c1 = not d1 # Starts with a character
        d2 = dt_array[1][0].isdigit()
        c2 = not d2
        if c1 and d2 and len2 == 2:
            # mmm-YY
            dt = datetime.strptime(dt, "%b-%y").date()
        elif c1 and d2 and len2 == 4:
            # mmm-YYYY
            dt = datetime.strptime(dt, "%b-%Y").date()
        elif d1 and len1 == 2 and c2:
            # YY-mmm
            dt = datetime.strptime(dt, "%y-%b").date()
        elif d1 and len1 == 4 and c2:
            # YYYY-mmm
            dt = datetime.strptime(dt, "%Y-%b").date()
        elif d1 and len1 == 4 and d2 and len2 == 2:
            # YYYY-MM
            dt = datetime.strptime(dt, "%Y-%m").date()
        else:
            raise bberr.InvalidYearMonthDate(dt, source)

    return dt

def write_csv(data: list[list[str]], csvFile: CsvFile) -> None:
    """Write accounts to file."""
    csv_conf = csvFile.config
    with open(csvFile.path, 'w', encoding=csv_conf.encoding) as xlfile:
        writer = csv.writer(xlfile, delimiter=csv_conf.column_separator,
                          quotechar=csv_conf.quotechar, quoting=csv.QUOTE_MINIMAL)
        for row in data:
            writer.writerow(row)

class CsvColumn:
    def __init__(self, name: str, type: str, required: bool, required_value: bool):
        """A column in a CSV file.
        
        name: name of the column
        type: type of the column (str, int, date, amount, ymdate)
        required: True if the column is required
        required_value: True if the column must have a non-empty value"""
        self.name = name
        self.type = type
        self.required = required
        self.required_value = required_value

def load_csv(csv_file: CsvFile, header: list[CsvColumn]) -> list[tuple[dict[str,any], SourcePosition]]:
    """Load a CSV file and return a list of dict with the proper type for each column and the source position.

    A field source is added to each row object.
    """
    # if file does not exist, return an empty list
    if not os.path.exists(csv_file.path):
        # Select basename to avoid displaying the full path
        basename = os.path.basename(csv_file.path)
        logger.warning(f"Cannot open csv file.\nFile '{basename}' does not exist.\nFullpath: {csv_file.path}")
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
            if h.required and h.name not in rows.fieldnames:
                raise bberr.MissingRequiredColumn(h.name, SourcePosition(csv_file.path, line, None))
            
        # Build the list of present columns
        present_columns = [True if h.name in rows.fieldnames else False for h in header]

        line += 1 # header line
        ls = []
        for r in rows:
            rowdata = dict()
            source = SourcePosition(csv_file.path, line, None)
            for i, h in enumerate(header):
                if not present_columns[i]:
                    rowdata[h.name] = None
                    continue

                value = r[h.name].strip() if r[h.name] else None
                if not value:
                    if h.required_value:
                        raise bberr.RequiredValueEmpty(h.name, source)
                    else:
                        rowdata[h.name] = None
                        continue

                value = read_value(value, h.type, csv_conf, source)
                rowdata[h.name] = value

            ls.append((rowdata, source))
            line += 1
            
        return ls