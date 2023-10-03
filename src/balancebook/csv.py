
from datetime import date
import balancebook.errors as bberr
from balancebook.amount import any_to_amount

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

def read_date(s: str) -> date:
    """Read a date from a string in the format YYYY-MM-DD."""
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise bberr.InvalidDateFormat(s) from e