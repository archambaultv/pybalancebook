
class CsvConfig:
    """Configuration for CSV files."""
    def __init__(self, encoding = "utf-8", column_separator = ",", quotechar = "\"", decimal_separator = ".",
                 skip_X_lines = 0, join_separator = " | "):
        self.encoding = encoding
        self.column_separator = column_separator
        self.quotechar = quotechar
        self.decimal_separator = decimal_separator
        self.skip_X_lines = skip_X_lines
        self.join_separator = join_separator

class CsvFile:
    """CSV file to be read."""
    def __init__(self, path, csv_config = None):
        self.path = path
        if csv_config:
            self.config = csv_config
        else:
            self.config = CsvConfig()