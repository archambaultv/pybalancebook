import logging
from datetime import date

logger = logging.getLogger(__name__)

class SourcePosition:
    """Class to store the source position of an error"""
    def __init__(self,file: str, line: int, column: int):
        self.file = file
        self.line = line
        self.column = column

    def __str__(self):
        if self.line is None:
            return f"{self.file}"
        if self.column is None:
            return f"{self.file}:{self.line}"
        return f"{self.file}:{self.line}:{self.column}"

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
            msg = f"{source}\n" + msg

        super().__init__(msg)

def catch_and_log(func):
    """Decorator to catch and log exceptions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BBookException as e:
            logger.fatal(e)
            return None
    
    return wrapper

class InvalidDateFormat(BBookException):
    """Exception raised when the date format is invalid"""
    def __init__(self, date: str, source: SourcePosition = None):
        self.date = date
        msg = f"Invalid date format: {date}. Must be YYYY-MM-DD"
        super().__init__(msg, source)

class InvalidAmount(BBookException):
    """Exception raised when an amount is invalid"""
    def __init__(self, amount: str, source: SourcePosition = None):
        self.amount = amount
        msg = f"Invalid amount: {amount}"
        super().__init__(msg, source)

class UnknownAccount(BBookException):
    """Exception raised when an account is unknown"""
    def __init__(self, identifier: str, source: SourcePosition = None):
        self.identifier = identifier
        msg = f"Unknown account: {identifier}"
        super().__init__(msg, source)

class AccountNameEmpty(BBookException):
    """Exception raised when the account name is empty"""
    def __init__(self, source: SourcePosition = None):
        msg = "The account name cannot be empty"
        super().__init__(msg, source)

class AccountNumberEmpty(BBookException):
    """Exception raised when the account number is empty"""
    def __init__(self, source: SourcePosition = None):
        msg = "The account number cannot be empty"
        super().__init__(msg, source)

class AccountNumberNotInteger(BBookException):
    """Exception raised when the account number is not an integer"""
    def __init__(self, source: SourcePosition = None):
        msg = "The account number must be an integer"
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

class AccountIdentifierEmpty(BBookException):
    """Exception raised when the account identifier is empty"""
    def __init__(self, source: SourcePosition = None):
        msg = "The account identifier cannot be empty"
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
        self.statement_balance = statement_balance
        self.computed_balance = computed_balance
        msg = f"Balance assertion not verified\nAccount: {identifier}\nDate: {dt}\nStatement balance: {statement_balance}\nComputed balance: {computed_balance}\nDifference: {computed_balance - statement_balance}" 

        super().__init__(msg, source)

class TxnIdEmpty(BBookException):
    """Exception raised when the transaction id is empty"""
    def __init__(self, source: SourcePosition = None):
        msg = "The transaction id cannot be empty"
        super().__init__(msg, source)

class TxnIdNotInteger(BBookException):
    """Exception raised when the transaction id is not an integer"""
    def __init__(self,id: str, source: SourcePosition = None):
        self.id = id
        msg = "The transaction id must be an integer. Got: {id}"
        super().__init__(msg, source)

class TxnLessThanTwoPostings(BBookException):
    """Exception raised when the transaction has less than two postings"""
    def __init__(self, txn_id: int, source: SourcePosition = None):
        self.txn_id = txn_id
        msg = f"Transaction {txn_id} has less than two postings"
        super().__init__(msg, source)

class TxnMoreThanTwoPostingsWithNoAmount(BBookException):
    """Exception raised when the transaction has more than two postings with no amount"""
    def __init__(self, txn_id: int, source: SourcePosition = None):
        self.txn_id = txn_id
        msg = f"Transaction {txn_id} has more than two postings with no amount"
        super().__init__(msg, source)

class TxnNotBalanced(BBookException):
    """Exception raised when the transaction is not balanced"""
    def __init__(self, txn_id: int, source: SourcePosition = None):
        self.txn_id = txn_id
        msg = f"Transaction {txn_id} is not balanced"
        super().__init__(msg, source)

class CsvImportNoRuleNoDefault(BBookException):
    """Exception raised when no rule matches and there is no provided default accounts"""
    def __init__(self, source: SourcePosition = None):
        msg = "No rule matches and there is no default accounts"
        super().__init__(msg, source)

class MissingHeader(BBookException):
    """Exception raised when a header is missing"""
    def __init__(self, header: str, source: SourcePosition = None):
        self.header = header
        msg = f"Missing header: {header}"
        super().__init__(msg, source)