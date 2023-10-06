from datetime import date

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