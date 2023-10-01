from datetime import date
from balancebook.amount import amount_to_str
from balancebook.i18n import i18n

class BBookException(Exception):
    """Base exception class for PyBalanceBook."""
    pass

class UnknownAccount(BBookException):
    """Exception raised when an account is unknown"""
    def __init__(self, identifier: str):
        self.identifier = identifier
        self.message = i18n.t("Unknown account: ${identifier}", identifier=identifier)
        super().__init__(self.message)

class AccountNameEmpty(BBookException):
    """Exception raised when the account name is empty"""
    def __init__(self):
        self.message = i18n.t("The account name cannot be empty")
        super().__init__(self.message)

class AccountNumberEmpty(BBookException):
    """Exception raised when the account number is empty"""
    def __init__(self):
        self.message = i18n.t("The account number cannot be empty")
        super().__init__(self.message)

class AccountNumberNotInteger(BBookException):
    """Exception raised when the account number is not an integer"""
    def __init__(self):
        self.message = i18n.t("The account number must be an integer")
        super().__init__(self.message)

class AssetsNumberInvalid(BBookException):
    """Exception raised when the asset account number is invalid"""
    def __init__(self, number: int):
        self.number = number
        self.message = i18n.t("Invalid account number: ${number}. Must be between 1000 and 1999 for asset accounts.", number=number)
        super().__init__(self.message)

class LiabilitiesNumberInvalid(BBookException):
    """Exception raised when the liability account number is invalid"""
    def __init__(self, number: int):
        self.number = number
        self.message = i18n.t("Invalid account number: ${number}. Must be between 2000 and 2999 for liability accounts.", number=number)
        super().__init__(self.message)

class EquityNumberInvalid(BBookException):
    """Exception raised when the equity account number is invalid"""
    def __init__(self, number: int):
        self.number = number
        self.message = i18n.t("Invalid account number: ${number}. Must be between 3000 and 3999 for equity accounts.", number=number)
        super().__init__(self.message)

class IncomeNumberInvalid(BBookException):
    """Exception raised when the income account number is invalid"""
    def __init__(self, number: int):
        self.number = number
        self.message = i18n.t("Invalid account number: ${number}. Must be between 4000 and 4999 for income accounts.", number=number)
        super().__init__(self.message)

class ExpensesNumberInvalid(BBookException):
    """Exception raised when the expense account number is invalid"""
    def __init__(self, number: int):
        self.number = number
        self.message = i18n.t("Invalid account number: ${number}. Must be between 5000 and 5999 for expense accounts.", number=number)
        super().__init__(self.message)

class AccountNumberNotUnique(BBookException):
    """Exception raised when the account number is not unique"""
    def __init__(self):
        self.message = i18n.t("The account numbers must be unique")
        super().__init__(self.message)

class AccountIdentifierNotUnique(BBookException):
    """Exception raised when the account identifier is not unique"""
    def __init__(self):
        self.message = i18n.t("The account identifiers must be unique")
        super().__init__(self.message)

class AccountIdentifierEmpty(BBookException):
    """Exception raised when the account identifier is empty"""
    def __init__(self):
        self.message = i18n.t("The account identifier cannot be empty")
        super().__init__(self.message)

class AccountTypeUnknown(BBookException):
    """Exception raised when the account type is unknown"""
    def __init__(self, acc_type: str):
        self.acc_type = acc_type
        self.message = i18n.t("Unknown account type: ${accType}", accType=acc_type)
        super().__init__(self.message)

class BalanceAssertionFailed(BBookException):
    """Exception raised when the balance assertion failed"""
    def __init__(self, dt: date, identifier: str, statement_balance: int, computed_balance: int):
        self.date = dt
        self.account = identifier
        self.statement_balance = statement_balance
        self.computed_balance = computed_balance
        self.message = i18n.t(i18n.t("Balance assertion of ${balAmount} for " 
                                   "${account} on ${date} does not match the balance ${txnAmount} of the transactions. "
                                   "Difference is ${difference}", 
                                   account=self.account, 
                                   date=self.date,
                                   balAmount=amount_to_str(self.statement_balance), 
                                   txnAmount=amount_to_str(self.computed_balance), 
                                   difference=amount_to_str(self.statement_balance - self.computed_balance)))
        super().__init__(self.message)