# Internal computations are done with integer to avoid rouding errors

import balancebook.errors as bberr

def float_to_amount(n: float):
    """Converts a float to an amount (integer)"""
    return int(round(n * 100))

def amount_to_float(n: int):
    """Converts an amount (integer) to a float"""
    return n / 100

def amount_to_str(n: int, decimal_sep: str = "."):
    """Converts an amount (integer) to a string"""
    f = amount_to_float(n)
    return (f"{f:.2f}").replace('.',decimal_sep)

def any_to_amount(s, decimal_sep: str = ".", currency_sign: str = "$", thousands_sep: str = " "):
    """Converts an excel amount to an amount (integer)
    
    1.03 $ -> 103
    (3.45) -> -345"""
    # If s is an int, convert it to an amount
    if isinstance(s, int):
        return s * 100
    
    # If s is a float, convert it to an amount
    if isinstance(s, float):
        return float_to_amount(s)

    # If s is a string, convert it to an amount
    if isinstance(s, str):
        s = s.strip()
        if currency_sign:
            s = s.replace(currency_sign,"")
        if thousands_sep:
            s = s.replace(thousands_sep,"")
        if decimal_sep:
            s = s.replace(decimal_sep,".")
        if s[0] == '(' and s[-1] == ')':
            s = "-" + s[1:-1]

        return float_to_amount(float(s))
    
    raise bberr.InvalidAmount(s)