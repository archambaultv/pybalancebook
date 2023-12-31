import logging
import os
from datetime import date

logger = logging.getLogger(__name__)

class SourcePosition:
    """Class to store the source position of an error"""
    def __init__(self,file: str, line: int = None, column: int = None):
        self.file = file
        self.line = line
        self.column = column

    def __str__(self):
        if self.line is None:
            return f"{self.file}"
        if self.column is None:
            return f"{self.file}:{self.line}"
        return f"{self.file}:{self.line}:{self.column}"

def add_source_position(source: SourcePosition):
    def decorator(function):
        def wrapper(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except BBookException as e:
                raise BBookException("Source position", source) from e
        return wrapper
    return decorator

class BBookException(Exception):
    """Base exception class for PyBalanceBook."""
    def __init__(self, message: str, source: SourcePosition = None):
        self.message = message
        self.source = source
        if self.message:
            msg = self.message
        else:
            msg = ""
        if source is not None:
            # Select base name of file
            basename = os.path.basename(source.file)
            msg = msg + f"\nFile: {basename} line: {source.line}\n" + f"Fullpath: {source}"

        super().__init__(msg)

class JournalNotLoaded(BBookException):
    """Exception raised when the journal is not loaded"""
    def __init__(self, source: SourcePosition = None):
        msg = "Journal not loaded"
        super().__init__(msg, source)

class JournalUnknownTxn(BBookException):
    """Exception raised when a transaction is unknown"""
    def __init__(self, txn_id: int, source: SourcePosition = None):
        self.txn_id = txn_id
        msg = f"Unknown transaction: {txn_id}"
        super().__init__(msg, source)

class ReservedAccountId(BBookException):
    """Exception raised when an account id is reserved"""
    def __init__(self, account_id: str, source: SourcePosition = None):
        self.account_id = account_id
        msg = f"Account identifier: {account_id} is reserved for top-level accounts. To redefined it, leave the parent column empty."
        super().__init__(msg, source)

class InvalidYamlType(BBookException):
    """Exception raised when the YAML type is invalid"""
    def __init__(self, expected_type: str, actual_type: str, source: SourcePosition = None):
        self.expected_type = expected_type
        self.actual_type = actual_type
        msg = f"Invalid YAML type. Expected: {expected_type}. Actual: {actual_type}"
        super().__init__(msg, source)

class ParentAccountNotFound(BBookException):
    """Exception raised when a parent account is not found"""
    def __init__(self, parent_account_id: str, source: SourcePosition = None):
        self.parent_account_id = parent_account_id
        msg = f"Parent account not found: {parent_account_id}"
        super().__init__(msg, source)

class InvalidLanguage(BBookException):
    """Exception raised when the language is invalid"""
    def __init__(self, lang: str, source: SourcePosition = None):
        self.lang = lang
        msg = f"Invalid language: {lang}"
        super().__init__(msg, source)

class AccountNumberReserved(BBookException):
    """Exception raised when an account number is reserved"""
    def __init__(self, account_number: int, source: SourcePosition = None):
        self.account_number = account_number
        msg = f"Account number: {account_number} is reserved for top-level accounts."
        super().__init__(msg, source)

class ParentAccountNotSpecified(BBookException):
    """Exception raised when a parent account is not specified"""
    def __init__(self, account_id: str, source: SourcePosition = None):
        self.account_id = account_id
        msg = f"Parent account not specified for: {account_id}"
        super().__init__(msg, source)

class AccountCycle(BBookException):
    """Exception raised when an account cycle is detected"""
    def __init__(self, account_id: str, source: SourcePosition = None):
        self.account_id = account_id
        msg = f"Account cycle detected for: {account_id}"
        super().__init__(msg, source)

class JournalUnknownPosting(BBookException):
    """Exception raised when a posting is unknown"""
    def __init__(self, posting_id: int, source: SourcePosition = None):
        self.posting_id = posting_id
        msg = f"Unknown posting: {posting_id}"
        super().__init__(msg, source)

class InvalidDateFormat(BBookException):
    """Exception raised when the date format is invalid"""
    def __init__(self, date: str, source: SourcePosition = None):
        self.date = date
        msg = f"Invalid date format: {date}. Must be YYYY-MM-DD"
        super().__init__(msg, source)

class InvalidYearMonthDate(BBookException):
    """Exception raised when the date format is invalid"""
    def __init__(self, date: str, source: SourcePosition = None):
        self.date = date
        msg = f"Invalid year and month date format: {date}. Must be YYYY-MM-DD, mmm-YY, mmm-YYYY, YY-mmm, YYYY-mmm or YYYY-MM"
        super().__init__(msg, source)

class InvalidAmount(BBookException):
    """Exception raised when an amount is invalid"""
    def __init__(self, amount: str, source: SourcePosition = None):
        self.amount = amount
        msg = f"Invalid amount: {amount}"
        super().__init__(msg, source)

class TxnNotSingleDay(BBookException):
    """Exception raised when the transaction is not single-day"""
    def __init__(self, txn_id: int, source: SourcePosition = None):
        self.txn_id = txn_id
        msg = f"Transaction {txn_id} is not single-day"
        super().__init__(msg, source)

class RequiredValueEmpty(BBookException):
    """Exception raised when a required column is empty"""
    def __init__(self, column: str, source: SourcePosition = None):
        self.column = column
        msg = f"Required column is empty: {column}"
        super().__init__(msg, source)

class TxnDateMismatch(BBookException):
    """Exception raised when the transaction date does not match"""
    def __init__(self, txn_id: int, date1: date, date2: date, source: SourcePosition = None):
        self.txn_id = txn_id
        self.date1 = date1
        self.date2 = date2
        msg = f"Transaction {txn_id} has two different dates: {date1} and {date2}"
        super().__init__(msg, source)

class UnknownAccountType(BBookException):
    """Exception raised when an account type is unknown"""
    def __init__(self, acc_type: str, source: SourcePosition = None):
        self.acc_type = acc_type
        msg = f"Unknown account type: {acc_type}"
        super().__init__(msg, source)

class UnknownAccount(BBookException):
    """Exception raised when an account is unknown"""
    def __init__(self, identifier: str, source: SourcePosition = None):
        self.identifier = identifier
        msg = f"Unknown account: {identifier}"
        super().__init__(msg, source)

class AssetsNumberInvalid(BBookException):
    """Exception raised when the asset account number is invalid"""
    def __init__(self, number: int, source: SourcePosition = None):
        self.number = number
        msg = f"Invalid account number: {number}. Must be between 1000 and 1999 for asset accounts."
        super().__init__(msg, source)

class LiabilitiesNumberInvalid(BBookException):
    """Exception raised when the liability account number is invalid"""
    def __init__(self, number: int, source: SourcePosition = None):
        self.number = number
        msg = f"Invalid account number: {number}. Must be between 2000 and 2999 for liability accounts."
        super().__init__(msg, source)

class DuplicateBalance(BBookException):
    """Exception raised when a balance is duplicated"""
    def __init__(self, date: date, identifier: str, source: SourcePosition = None):
        self.date = date
        self.identifier = identifier
        msg = f"Duplicate balance: {date} {identifier}"
        super().__init__(msg, source)

class EquityNumberInvalid(BBookException):
    """Exception raised when the equity account number is invalid"""
    def __init__(self, number: int, source: SourcePosition = None):
        self.number = number
        msg = f"Invalid account number: ${number}. Must be between 3000 and 3999 for equity accounts."
        super().__init__(msg, source)

class IncomeNumberInvalid(BBookException):
    """Exception raised when the income account number is invalid"""
    def __init__(self, number: int, source: SourcePosition = None):
        self.number = number
        msg = f"Invalid account number: ${number}. Must be between 4000 and 4999 for income accounts."
        super().__init__(msg, source)

class ExpensesNumberInvalid(BBookException):
    """Exception raised when the expense account number is invalid"""
    def __init__(self, number: int, source: SourcePosition = None):
        self.number = number
        msg = f"Invalid account number: ${number}. Must be between 5000 and 5999 for expense accounts."
        super().__init__(msg, source)

class AccountNumberNotUnique(BBookException):
    """Exception raised when the account number is not unique"""
    def __init__(self, numbers: list[int], source: SourcePosition = None):
        self.numbers = numbers
        msg = f"The account numbers must be unique. The following account numbers are duplicated: {numbers}"
        super().__init__(msg, source)

class AccountIdentifierNotUnique(BBookException):
    """Exception raised when the account identifier is not unique"""
    def __init__(self, identifiers: list[str], source: SourcePosition = None):
        self.identifiers = identifiers
        msg = f"The account identifiers must be unique. The following account identifiers are duplicated: {identifiers}"
        super().__init__(msg, source)

class AccountTypeUnknown(BBookException):
    """Exception raised when the account type is unknown"""
    def __init__(self, acc_type: str, source: SourcePosition = None):
        self.acc_type = acc_type
        msg = f"Unknown account type: {acc_type}"
        super().__init__(msg, source)

class BalanceAssertionFailed(BBookException):
    """Exception raised when the balance assertion failed"""
    def __init__(self, dt: date, identifier: str, statement_balance: int, computed_balance: int, source: SourcePosition = None):
        self.date = dt
        self.account = identifier
        self.statement_balance = statement_balance / 100
        self.computed_balance = computed_balance / 100
        self.difference = round(self.computed_balance - self.statement_balance, 2)
        msg = f"Balance assertion not verified\nAccount: {self.account}\nDate: {dt}\nStatement balance: {self.statement_balance:.2f}\nComputed balance: {self.computed_balance:.2f}\nDifference: {self.difference:.2f}"
        super().__init__(msg, source)

class InvalidCsvType(BBookException):
    """Exception raised when the CSV type is invalid"""
    def __init__(self, type: str, source: SourcePosition = None):
        self.type = type
        msg = f"Invalid CSV column type: {type}"
        super().__init__(msg, source)

class InvalidInt(BBookException):
    """Exception raised when an integer is invalid"""
    def __init__(self, s: str, source: SourcePosition = None):
        self.s = s
        msg = f"Invalid integer: {s}"
        super().__init__(msg, source)

class TxnLessThanTwoPostings(BBookException):
    """Exception raised when the transaction has less than two postings"""
    def __init__(self, txn_id: int, source: SourcePosition = None):
        self.txn_id = txn_id
        msg = f"Transaction {txn_id} has less than two postings"
        super().__init__(msg, source)

class TxnNotBalanced(BBookException):
    """Exception raised when the transaction is not balanced"""
    def __init__(self, txn_id: int, source: SourcePosition = None):
        self.txn_id = txn_id
        msg = f"Transaction {txn_id} is not balanced"
        super().__init__(msg, source)

class MissingRequiredColumn(BBookException):
    """Exception raised when a header is missing"""
    def __init__(self, header: str, source: SourcePosition = None):
        self.header = header
        msg = f"Missing header: {header}"
        super().__init__(msg, source)

class MissingRequiredKey(BBookException):
    """Exception raised when a key is missing"""
    def __init__(self, key: str, source: SourcePosition = None):
        self.dedup_key = key
        msg = f"Missing key: {key}"
        super().__init__(msg, source)