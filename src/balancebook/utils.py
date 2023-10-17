from datetime import date
import unicodedata

def fiscal_month(dt: date, first_fiscal_month = 1) -> int:
    """Compute the fiscal month number
    """
    month = dt.month
    if month >= first_fiscal_month:
        return month - first_fiscal_month + 1
    else:
        return (12 - first_fiscal_month + 1) + dt.month
    
def fiscal_year(dt: date, first_fiscal_month = 1) -> int:
    """Compute the fiscal year
    """
    year = dt.year
    month = dt.month
    if first_fiscal_month == 1 or month < first_fiscal_month:
        return year
    else:
        return year + 1
    
def no_accent(string: str) -> str:
    """Removes accents from a string."""
    return ''.join((c for c in unicodedata.normalize('NFD', string) if unicodedata.category(c) != 'Mn'))

def are_files_identical(file1, file2):
    with open(file1, 'rb') as file1, open(file2, 'rb') as file2:
        # Read the contents of both files
        content1 = file1.read()
        content2 = file2.read()

        # Compare the contents
        if content1 == content2:
            return True
        else:
            return False