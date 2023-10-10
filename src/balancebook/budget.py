import csv
from enum import Enum
from dateutil.relativedelta import relativedelta
from datetime import date, timedelta
from balancebook.csv import load_csv, CsvFile, write_csv
from balancebook.amount import amount_to_str
import balancebook.errors as bberr
from balancebook.errors import SourcePosition
from balancebook.transaction import Txn, Posting
from balancebook.account import Account

class RecurrenceType(Enum):
    """Recurrence of a budget row."""
    ONCE = 0
    DAILY = 1
    WEEKLY = 2
    MONTHLY = 3
    YEARLY = 4

    def __str__(self):
        # Capitalize the first letter
        return self.name[0] + self.name[1:].lower()

class Recurrence():
    def __init__(self, rec_type: RecurrenceType, interval: int = 1, 
                 end_date: date = None, end_nb_of_times: int = None) -> None:
        """Create a recurrence.
        interval is the number of weeks/months/years between each recurrence.
        end_nb_of_times is the number of times the recurrence should happen. 
        end_nb_of_times = 1 actually means only once, so in effect no recurrence.
        end_date is the last date of the recurrence included."""
        self.rec_type = rec_type
        self.interval = interval
        self.end_date = end_date
        self.end_nb_of_times = end_nb_of_times

def next_date(d: date, r: Recurrence) -> date:
    """Returns the next date of the recurrence."""
    if r.rec_type == RecurrenceType.ONCE:
        return None
    elif r.rec_type == RecurrenceType.DAILY:
        return d + timedelta(days=r.interval)
    elif r.rec_type == RecurrenceType.WEEKLY:
        return d + timedelta(weeks=r.interval)
    elif r.rec_type == RecurrenceType.MONTHLY:
        return d + relativedelta(months=r.interval)
    elif r.rec_type == RecurrenceType.YEARLY:
        return d + relativedelta(years=r.interval)
    else:
        raise ValueError(f"Unknown recurrence {r}")

class BudgetTxnRule():
    def __init__(self, name: str, start: date, amount: int, 
                 recurrence: Recurrence,
                 account: Account,
                 comment: str = None,
                 source: SourcePosition = None):
        self.name = name
        self.start = start
        self.amount = amount
        self.recurrence = recurrence
        self.account = account
        self.comment = comment
        self.source = source
        self.__normalize_end__()

    def __str__(self):
        return f"BudgetTxnRule({self.name})"
    
    def __normalize_end__(self):
        """Set the end date or number of times to the minimum of the two."""
        if self.recurrence.rec_type == RecurrenceType.ONCE:
            self.recurrence.end_date = self.start
            self.recurrence.interval = 1
            self.recurrence.end_nb_of_times = 1
            return

        if self.recurrence.end_date:
            count = len(self.date_list(self.recurrence.end_date))
            if self.recurrence.end_nb_of_times is None or self.recurrence.end_nb_of_times >= count:
                self.recurrence.end_nb_of_times = count
                return
        
        if self.recurrence.end_nb_of_times:
            d = self.start
            for _ in range(self.recurrence.end_nb_of_times - 1):
                d = next_date(d, self.recurrence, self.recurrence.interval)
            if self.recurrence.end_date is None or self.recurrence.end_date >= d:
                self.recurrence.end_date = d
                return
        
    def date_list(self, end: date) -> list[date]:
        """Return the list of dates of the budget rule."""
        if self.recurrence.rec_type == RecurrenceType.ONCE:
            return [self.start]
        
        dates = []
        d = self.start
        if self.recurrence.end_date is None:
            end2 = end
        else:
            end2 = min(end, self.recurrence.end_date)
        while d <= end2:
            dates.append(d)
            d = next_date(d, self.recurrence, self.recurrence.interval)
        return dates


def year_month_date_to_str(d: date, r: Recurrence) -> str:
    """Returns the date of the budget rule as a string.
    
    Weekly recurrence must provide the exact date."""
    if r.rec_type == RecurrenceType.ONCE:
        return d.strftime("%Y-%m")
    elif r.rec_type == RecurrenceType.WEEKLY:
        return d.strftime("%Y-%m-%d")
    elif r.rec_type == RecurrenceType.MONTHLY:
        return d.strftime("%Y-%m")
    elif r.rec_type == RecurrenceType.YEARLY:
        return d.strftime("%Y-%m")
    else:
        raise ValueError(f"Unknown recurrence {r}")


def load_budget_txn_rules(csvFile: CsvFile, accounts_by_number: dict[str,Account]) -> list[BudgetTxnRule]:
    """Load budget rows from the cvs file
    """
    csv_rows = load_csv(csvFile, [("Name", "str", True, True), 
                                  ("Start date", "ymdate", True, True), 
                                  ("Amount", "amount", True, True), 
                                  ("Account", "str", True, True),
                                  ("Recurrence", "str", False, False), 
                                  ("Interval", "int", False, False), 
                                  ("End date", "ymdate", False, False), 
                                  ("Nb of times", "int", False, False)])
    btxns = []
    for row in csv_rows:
        source = row[8]
        if row[3] not in accounts_by_number:
            raise bberr.UnknownAccount(row[3], source)
        account = accounts_by_number[row[3]]
        if row[4]:
            recurrence = Recurrence(RecurrenceType[row[4].upper()], row[5], row[6], row[7])
        else:
            recurrence = Recurrence(RecurrenceType.ONCE)
        r = BudgetTxnRule(row[0], row[1], row[2], recurrence, account, source)
        verify_budget_txn_rules(r)
        btxns.append(r)
    
    return btxns

def verify_budget_txn_rules(br: BudgetTxnRule) -> None:
    """Verify the consistency of the budget rule.
    
    - Interval must be positive
    - End date must be after start date
    - End after X times must be positive
    """
    if not br.recurrence:
        return
    
    if br.recurrence.interval <= 0:
        raise bberr.InvalidBudgetTxnRuleInterval(br.recurrence.interval, br.source)
    if br.recurrence.end_date and br.recurrence.end_date < br.start:
        raise bberr.InvalidBudgetTxnRuleEndDate(br.recurrence.end_date, br.start, br.source)
    if br.recurrence.end_nb_of_times and br.recurrence.end_nb_of_times <= 0:
        raise bberr.InvalidBudgetTxnRuleEndNbOfTimes(br.recurrence.end_nb_of_times, br.source)

def write_budget_txn_rules_to_list(btxns: list[BudgetTxnRule], decimal_separator = ".") -> list[list[str]]:
    rows = [["Name", "Start date", "Amount", "Account", "Recurrence", "Interval", "End date", "Nb of times"]]
    for b in btxns:
        rows.append([b.name, b.start, amount_to_str(b.amount, decimal_separator), b.account.identifier, 
                     b.recurrence.rec_type, b.recurrence.interval, b.recurrence.end_date, b.recurrence.end_nb_of_times])
    return rows

def write_budget_txn_rules(bals: list[BudgetTxnRule], csvFile: CsvFile) -> None:
    """Write balances to file."""
    data = write_budget_txn_rules_to_list(bals, csvFile.config.decimal_separator)
    write_csv(data, csvFile)
        
class BudgetTxn(Txn):
    def __init__(self, txn_id: int, date: date, postings: list[Posting],
                 budget_rule: BudgetTxnRule) -> None:
        super().__init__(txn_id, date, postings)
        self.budget_rule = budget_rule

def budget_txn_rule_to_txns(br: BudgetTxnRule, budget_account: Account, max_end: date) -> list[BudgetTxn]:
    """Unroll a budget rule into a list of transactions."""
    txns = []
    for d in br.date_list(max_end):
        t = BudgetTxn(None, d, [], br)
        p1 = Posting(1, budget_account, br.amount, t, source=br.source)
        p2 = Posting(2, br.account, -br.amount, t, source=br.source)
        t.postings = [p1, p2]
    return txns