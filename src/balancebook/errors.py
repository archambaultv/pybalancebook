from balancebook.i18n import i18n

class BBookException(Exception):
    """Base exception class for PyBalanceBook."""
    pass

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