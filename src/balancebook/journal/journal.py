import os
import logging
from datetime import date, datetime, timedelta

import balancebook.errors as bberr
from balancebook.account import Account, load_accounts, write_accounts, write_accounts_to_list
from balancebook.transaction import (Txn, Posting, load_txns, write_txns, postings_by_number_by_date, compute_account_balance,
                                     balance, reclassify, subset_sum, ClassificationRule, load_classification_rules,
                                     write_classification_rules, write_txns_to_list, write_classification_rules_to_list)
from balancebook.balance import Balance, load_balances, write_balances, balance_by_number, write_balances_to_list
from balancebook.csv import CsvFile, write_csv
from balancebook.utils import fiscal_month, fiscal_year, no_accent
from balancebook.journal.autoimport import import_bank_postings, CsvImportHeader
from balancebook.journal.config import JournalConfig
from balancebook.budget import BudgetTxnRule, load_budget_txn_rules, write_budget_txn_rules

logger = logging.getLogger(__name__)

class Journal():
    def __init__(self, config: JournalConfig) -> None:
        self.config = config
        self.accounts: list[Account] = None
        self.txns: list[Txn] = None
        self.class_rules: list[ClassificationRule] = None
        self.balance_assertions: list[Balance] = None
        self.budget_txn_rules: list[BudgetTxnRule] = None

        # Cache of various dictionaries
        self.txns_by_id: dict[int,Txn] = None
        self.assertion_by_number: dict[int,list[Balance]] = None
        self.accounts_by_name: dict[str,Account] = None
        self.accounts_by_id: dict[str,Account] = None
        self.postings_by_number_by_date: dict[int,list[tuple[date,list[Posting]]]] = None
        self.balance_by_number_by_date: dict[int,list[tuple[date,int]]] = None

    def __reset_cache__(self) -> None:
        self.accounts_by_id = None
        self.accounts_by_name = None
        self.txns_by_id = None
        self.postings_by_number_by_date = None
        self.balance_by_number_by_date = None
        self.assertion_by_number = None

    def __init_account_cache__(self) -> None:
        self.accounts_by_name = dict([(a.identifier, a) for a in self.accounts])
        self.accounts_by_id = dict([(a.number, a) for a in self.accounts])

    def __init_txns_cache__(self) -> None:
        self.txns_by_id = dict([(t.id, t) for t in self.txns])
        self.postings_by_number_by_date = postings_by_number_by_date(self.txns, False)
        self.balance_by_number_by_date = compute_account_balance(self.postings_by_number_by_date)
        self.assertion_by_number = balance_by_number(self.balance_assertions)

    def sort_data(self) -> None:
        """Sort the data in the journal"""
        self.accounts.sort(key=lambda x: x.number)
        self.txns.sort(key=lambda x: (x.date,x.postings[0].account.number, x.id))
        self.balance_assertions.sort(key=lambda x: (x.date, x.account.number))
        self.class_rules.sort(key=lambda x: 
                              (no_accent(x.second_account.identifier) if x.second_account else "", 
                               no_accent(x.match_statement_description) if x.match_statement_description else "", 
                               no_accent(x.match_account) if x.match_account else ""))
        self.budget_txn_rules.sort(key=lambda x: 
                                   (x.start, 
                                    no_accent(x.account.identifier), 
                                    x.recurrence.rec_type,
                                    x.recurrence.end_date, 
                                    x.recurrence.end_nb_of_times))

    def get_account_by_id(self) -> dict[str,Account]:
        if self.accounts_by_id is None:
            self.__init_account_cache__()
        return self.accounts_by_id

    def get_account_by_name(self) -> dict[str,Account]:
        if self.accounts_by_name is None:
            self.__init_account_cache__()
        return self.accounts_by_name

    def get_txns_by_id(self) -> dict[int,Txn]:
        if self.txns_by_id is None:
            self.__init_txns_cache__()
        return self.txns_by_id
    
    def get_postings_by_number_by_date(self) -> dict[int,dict[date,list[Posting]]]:
        if self.postings_by_number_by_date is None:
            self.__init_txns_cache__()
        return self.postings_by_number_by_date

    def get_balance_by_number_by_date(self) -> dict[int,list[tuple[date,int]]]:
        if self.balance_by_number_by_date is None:
            self.__init_txns_cache__()
        return self.balance_by_number_by_date
    
    def get_assertion_by_number(self) -> dict[int,list[Balance]]:
        if self.assertion_by_number is None:
            self.__init_txns_cache__()
        return self.assertion_by_number

    def is_budget_account(self, account: Account) -> bool:
        """Return True if the account is a budget account"""
        return account.identifier in self.config.budget_accounts

    def load(self) -> None:
        """Load the journal from files
    
        Normalize the journal data"""
        self.__reset_cache__()

        self.accounts = load_accounts(self.config.account_file)
        self.accounts_by_name = self.get_account_by_name()
        self.txns = load_txns(self.config.txn_file, self.accounts_by_name)
        self.class_rules = load_classification_rules(self.config.classification_rule_file, 
                                                     self.accounts_by_name,
                                                     filter_drop_all=True)
        self.balance_assertions = load_balances(self.config.balance_file, self.accounts_by_name)
        self.budget_txn_rules = load_budget_txn_rules(self.config.budget_txn_file, self.accounts_by_name)

    def write(self, what: list[str] = None, 
              sort = False,
              backup_dir = None) -> None:
        """Write the journal to files
        
        what: list of what to write. If None, write everything.
        Valid values are: "accounts", "balances", "transactions", "classification_rules", "budget"
        sort: if True
            - sort the accounts by number
            - sort the balance assertions by date and account number
        """
        if isinstance(what, str):
            what = [what]

        if backup_dir is None:
            backup_dir = self.config.backup_folder

        dt = datetime.now()
        dt_str = dt.strftime("%Y-%m-%d %Hh%Mm%Ss")

        def backup_file(file: CsvFile) -> None:
            if os.path.isfile(file.path):
                name = os.path.splitext(os.path.basename(file.path))[0]
                # Test if backup folder exists
                if not os.path.isdir(backup_dir):
                    os.mkdir(backup_dir)
                backup = os.path.join(backup_dir, f"{name} {dt_str}.csv")
                os.rename(file.path, backup)

        if sort:
            self.sort_data()

        if not what or "accounts" in what:
            backup_file(self.config.account_file)
            write_accounts(self.accounts, self.config.account_file)
        if not what or "balances" in what:
            backup_file(self.config.balance_file)
            write_balances(self.balance_assertions, self.config.balance_file)
        if not what or "transactions" in what:
            backup_file(self.config.txn_file)
            write_txns(self.txns, self.config.txn_file)
        if not what or "classification_rules" in what:
            backup_file(self.config.classification_rule_file)
            write_classification_rules(self.class_rules, self.config.classification_rule_file)
        if not what or "budget" in what:
            backup_file(self.config.budget_txn_file)
            write_budget_txn_rules(self.budget_txn_rules, self.config.budget_txn_file)

    def export(self):
        """Export the journal to csv files"""
        self.sort_data()
        i18n = self.config.export_config.i18n
        if i18n is None:
            i18n = {}

        accs = write_accounts_to_list(self.accounts)
        accs[0] = [i18n.get(x, x) for x in accs[0]]
        for i in range(1, len(accs)):
            accs[i][3] = i18n.get(accs[i][3], accs[i][3])
        write_csv(accs, self.config.export_config.account_file)

        txns = write_txns_to_list(self.txns, 
                                  decimal_separator=self.config.export_config.txn_file.config.decimal_separator, 
                                  posting_id=True)
        extra_header = ["Account name", "Account number", "Account type", "Account group", "Account subgroup", "Budget account",
                        "Fiscal year", "Fiscal month", "Other accounts","Budgetable"]
        txns[0] = txns[0] + extra_header
        txns[0] = [i18n.get(x, x) for x in txns[0]]
        for i in range(1, len(txns)):
            account = self.get_account_by_name()[txns[i][2]]
            txn = self.get_txns_by_id()[txns[i][0]]
            acc_type = i18n.get(str(account.type), str(account.type))
            ps_id = int(txns[i][7])
            budget_txn = "Not budgetable"
            for p in txn.postings:
                if self.is_budget_account(p.account):
                    budget_txn = "Budgetable"
                    break
            txns[i].extend([account.name, 
                            account.number,
                            acc_type,
                            account.group,
                            account.subgroup,
                            i18n.get("True", "True") if self.is_budget_account(account) else i18n.get("False", "False"),
                            self.fiscal_year(txn.date),
                            self.fiscal_month(txn.date),
                            " | ".join([x.account.name for x in txn.postings if x.id != ps_id]),
                            i18n.get(budget_txn, budget_txn)])
        write_csv(txns, self.config.export_config.txn_file)

        balances = write_balances_to_list(self.balance_assertions, self.config.export_config.balance_file.config.decimal_separator)
        balances[0] = [i18n.get(x, x) for x in balances[0]]
        write_csv(balances, self.config.export_config.balance_file)

        rules = write_classification_rules_to_list(self.class_rules, self.config.export_config.classification_rule_file.config.decimal_separator)
        rules[0] = [i18n.get(x, x) for x in rules[0]]
        write_csv(rules, self.config.export_config.classification_rule_file)      

    def fiscal_month(self, dt: date) -> int:
        return fiscal_month(dt, self.config.first_fiscal_month)
    
    def fiscal_year(self, dt: date) -> int:
        return fiscal_year(dt, self.config.first_fiscal_month)

    def get_newest_balance_assertions(self, account: Account) -> Balance:
        """Get the newer balance assertions for the given account"""
        d = self.get_balance_by_number_by_date()
        if account.number in d:
            return d[account.number][-1]
        else:
            return None

    def set_txns(self, txns: list[Txn]) -> None:
        """Set the transactions"""
        self.txns = txns
        self.__reset_cache__()

    def update_txns(self, txns: list[Txn]) -> None:
        """Update the transactions"""
        d = self.get_txns_by_id()
        for t in txns:
            if t.id in d:
                d[t.id] = t
            else:
                raise bberr.JournalUnknownTxn(t.id)
        
        self.txns = list(d.values())
        self.__reset_cache__()

    def new_txns(self, txns: list[Txn]) -> None:
        """Add new transactions
        
        The transactions numbers are set automatically"""
        next_id = max([t.id for t in self.txns]) + 1
        for t in txns:
            t.id = next_id
            next_id += 1
        self.txns.extend(txns)
        self.__reset_cache__()

    def account_balance(self, account: Account, dt: date) -> int:
        """Get the account balance at the given date"""
        d = self.get_balance_by_number_by_date()
        return balance(account, dt, d)

    def verify_balances(self) -> None:
        """ Verify that the balances are consistent with the transactions"""
        bals = sorted(self.balance_assertions, key=lambda x: (x.date, x.account.number))
        ps = postings_by_number_by_date(self.txns, True)
        d = compute_account_balance(ps)
        for b in bals:
            txnAmount = balance(b.account, b.date, d)
            if txnAmount != b.statement_balance:
                raise bberr.BalanceAssertionFailed(b.date, b.account.identifier, b.statement_balance, txnAmount, b.source)

    def reclassify(self, rules: list[ClassificationRule] = None, 
                   allow_delete_rules = False,
                   accounts: list[Account] = None) -> None:
        if rules is None:
            rules = self.class_rules

        if not allow_delete_rules:
            rules = [r for r in rules if r.second_account]

        txns = reclassify(self.txns, rules, accounts)
        self.set_txns(txns)

    def import_from_bank_csv(self, csvFile : CsvFile, csv_header: CsvImportHeader, 
                             account: Account,
                             default_snd_account: Account,
                             rules: list[ClassificationRule],
                             import_zero_amount: bool = True) -> list[Txn]:
        """Import the transactions from the bank csv file
        
        Does not modify the journal.
        """

        # Load posting from file
        csvPs = import_bank_postings(csvFile, csv_header, account, import_zero_amount)

        # Create new transactions with default_snd_account
        #   if the date is after the newest balance assertion
        #   if the posting is not already in a transaction
        txns = []
        newest_balance = self.get_newest_balance_assertions(account)
        newest_date = newest_balance.date if newest_balance else None
        keys = self.posting_keys(account, newest_date)                   
        for (dt, p) in csvPs:
            if newest_date and dt <= newest_date:
                logger.info(f"Skipping posting {p} because it is before the newest balance assertion\n{p.source}")
                continue
            
            if p.key(dt) in keys:
                if keys[p.key(dt)] == 1:
                    del keys[p.key(dt)]
                else:
                    keys[p.key(dt)] -= 1
                logger.info(f"Skipping posting {p} because it is already in a transaction\n{p.source}")
                continue

            t = Txn(None, dt, [])
            p.parent_txn = t
            p.id = 1
            p2 = Posting(2, default_snd_account, - p.amount, t, dt, p.statement_description, p.comment, None)
            t.postings.extend([p, p2])
            txns.append(t)

        # Apply classification rules
        return reclassify(txns, rules)
    
    def auto_statement_date(self, Balance: Balance, dayslimit: int = 7) -> list[Txn]:
        """Try to adjust the statement date of the transactions to match the given balance assertion
        
        Returns the list of transactions to update. Use update_txns to update the transactions afterwards.
        Returns None if no transactions can be updated and the balance assertion is not met.
        """
        d = self.get_account_balance_dict(True)
        txnAmount = balance(Balance.account, Balance.date, d)
        if txnAmount == Balance.statement_balance:
            return []

        ps = []
        # Select the postings from psdict that matches the account and the date range
        check = lambda x: (x[0] <= Balance.date and x[0] >= Balance.date - timedelta(days=dayslimit))
        postings_by_date = filter(check, self.get_postings_by_number_by_date()[Balance.account.number])
        ps: list[Posting] = [p for _, postings in postings_by_date for p in postings]
        ps.sort(reverse=True,key=lambda x:x.parent_txn.date)

        subset = subset_sum(ps, txnAmount - Balance.statement_balance)
        if subset:
            # Multiple postings can come from the same transaction
            txns2: dict[int,Txn] = {}
            for p in subset:
                if p.parent_txn.id in txns2:
                    t2 = txns2[p.parent_txn.id]
                else:
                    t2 = p.parent_txn.copy()
                    txns2[t2.id] = t2
                for i in range(len(t2.postings)):
                    if t2.postings[i].id == p.id:
                        t2.postings[i].statement_date = Balance.date + timedelta(days=1)
                        break
            return list(txns2.values())

        else:
            return None

    def auto_balance_with_new_txn(self, b: Balance, snd_account: Account) -> Txn:
        """Balance the account with a new transaction
        
        Returns the transaction to add. Use new_txns to add the transaction afterwards.
        Returns None if the balance assertion is already met.
        """
        d = self.get_account_balance_dict(True)
        txnAmount = balance(b.account, b.date, d)
        if txnAmount == b.statement_balance:
            return None

        diff = b.statement_balance - txnAmount
        t = Txn(None, b.date, [])
        p1 = Posting(1, b.account, diff, t, b.date, None, None, None)
        p2 = Posting(2, snd_account, - diff, t, b.date, None, None, None)
        t.postings = [p1, p2]
        return t

    def posting_keys(self, account: Account = None, after: date = None) -> dict[tuple[date,str,int,str], int]:
        keys: dict[tuple[date,str,int,str], int] = {}
        for t in self.txns:
            for p in t.postings:
                if account and p.account.number != account.number:
                    continue
                if after and t.date <= after:
                    continue

                if p.key() in keys:
                    keys[p.key()] += 1
                else:
                    keys[p.key()] = 1
        return keys