import os
import logging
import csv
import shutil
from bisect import bisect_right
from itertools import groupby
from datetime import date, datetime, timedelta

import balancebook.errors as bberr
from balancebook.amount import amount_to_str
from balancebook.account import ChartOfAccounts, max_depth, Account, load_accounts, write_accounts
from balancebook.transaction import Txn, Posting, load_txns, write_txns, subset_sum,  txn_header
from balancebook.balance import Balance, load_balances, write_balances
from balancebook.csv import CsvFile, write_csv, SourcePosition
from balancebook.journal.autoimport import (load_import_config, load_classification_rules,
                                            import_from_bank_csv)
from balancebook.journal.config import JournalConfig

logger = logging.getLogger(__name__)

def assert_loaded(func):
    def wrapper(*args, **kwargs):
        if args[0].chart_of_accounts is None:
            raise bberr.JournalNotLoaded()
        return func(*args, **kwargs)
    
    return wrapper

class Journal():
    def __init__(self, config: JournalConfig) -> None:
        self.config = config
        self.chart_of_accounts: ChartOfAccounts = None
        self.txns: list[Txn] = None
        self.balance_assertions: list[Balance] = None

        # Cache of various data
        self._accounts_by_name: dict[str,Account] = None
        self._accounts_by_number: dict[int,Account] = None

        self._txns_by_id: dict[int,Txn] = None
        # The list is ordered by date
        self._postings_by_account: dict[int, list[Posting]] = None
        
        # The list is ordered by date
        self._assertion_by_account: dict[int,list[Balance]] = None
        
        # Includes the balance of the subaccounts.
        # The list is ordered by date
        self._account_balance: dict[int,list[tuple[date,int]]] = None
        self._account_st_balance: dict[int,list[tuple[date,int]]] = None

    def _reset_cache(self) -> None:
        self._accounts_by_number = None
        self._accounts_by_name = None
        self._txns_by_id = None
        self._postings_by_account = None
        self._account_balance = None
        self._account_st_balance = None
        self._assertion_by_account = None

    @assert_loaded
    def _init_account_cache(self) -> None:
        accounts = [x for a in self.chart_of_accounts for x in a.get_account_and_descendants()]
        self._accounts_by_name = dict([(a.identifier, a) for a in accounts])
        self._accounts_by_number = dict([(a.number, a) for a in accounts])

    @assert_loaded
    def _init_txns_cache(self) -> None:
        self._txns_by_id = dict([(t.id, t) for t in self.txns])
        
        ps = [p for t in self.txns for p in t.postings]
        ps.sort(key=lambda x: (x.account.number, x.date))
        self._postings_by_account = {}
        for n, ps in groupby(ps, key=lambda x: x.account.number):
            self._postings_by_account[n] = list(ps)
                
        self._account_balance = {}
        for acc, value in self._postings_by_account.items():
            self._account_balance[acc] = []
            total = 0
            for dt, ps in groupby(value, key=lambda x: x.date):
                total += sum([p.amount for p in ps])
                self._account_balance[acc].append((dt, total))

        self._account_st_balance = {}
        for acc, value in self._postings_by_account.items():
            self._account_st_balance[acc] = []
            value2 = sorted(value, key=lambda x: x.statement_date)
            total = 0
            for dt, ps in groupby(value2, key=lambda x: x.statement_date):
                total += sum([p.amount for p in ps])
                self._account_st_balance[acc].append((dt, total))

        assertions = sorted(self.balance_assertions, key=lambda x: (x.account.number, x.date))
        self._assertion_by_account = {}
        for n, assertion in groupby(assertions, key=lambda x: x.account.number):
            self._assertion_by_account[n] = list(assertion)
    
    def load(self) -> None:
        """Load the journal from files"""

        self.chart_of_accounts: ChartOfAccounts = load_accounts(self.config.data.account_file, self.config.i18n)
        self._init_account_cache()
        self.txns = load_txns(self.config.data.txn_file, self._accounts_by_name, self.config.i18n)
        self.balance_assertions = load_balances(self.config.data.balance_file, self._accounts_by_name, self.config.i18n)
        self._init_txns_cache()

        # Convert auto balance accounts to Account
        accounts2 = {}
        for acc, acc2 in self.config.auto_balance.accounts.items():
            source = SourcePosition(self.config.config_path, 0, 0)
            try:
                new_acc = self._accounts_by_name[acc]
            except KeyError:
                raise bberr.UnknownAccount(acc, source)
            try:
                new_acc2 = self._accounts_by_name[acc2]
            except KeyError:
                raise bberr.UnknownAccount(acc2, source)
            accounts2[new_acc] = new_acc2
        self.config.auto_balance.accounts = accounts2

        # Convert auto statement dates accounts to accounts
        accounts2 = []
        for acc in self.config.auto_statement_date.accounts:
            source = SourcePosition(self.config.config_path, 0, 0)
            try:
                new_acc = self._accounts_by_name[acc]
            except KeyError:
                raise bberr.UnknownAccount(acc, source)
            accounts2.append(new_acc)
        self.config.auto_statement_date.accounts = accounts2

        # Convert budget accounts to accounts
        accounts2 = []
        for acc in self.config.data.budget_accounts:
            source = SourcePosition(self.config.config_path, 0, 0)
            try:
                new_acc = self._accounts_by_name[acc]
            except KeyError:
                raise bberr.UnknownAccount(acc, source)
            accounts2.append(new_acc)
        self.config.data.budget_accounts = accounts2
    
    @assert_loaded
    def sort_data(self) -> None:
        """Sort the data in the journal
        
        This will affect how the data is written to files"""
        for t in self.chart_of_accounts:
            t.sort_children()
        for t in self.txns:
            t.postings.sort(key=lambda x: (x.date,x.account.number))
        self.txns.sort(key=lambda x: (x.postings[0].date,x.postings[0].account.number, x.id))
        self.balance_assertions.sort(key=lambda x: (x.date, x.account.number))

    @assert_loaded
    def accounts(self) -> list[Account]:
        """Return the list of accounts"""
        return [x for a in self.chart_of_accounts for x in a.get_account_and_descendants()]

    @assert_loaded
    def get_account_by_ident(self, name: str = None) -> Account:
        """Return the account with the given name"""
        return self._accounts_by_name[name]

    @assert_loaded
    def is_budget_account(self, account: Account) -> bool:
        """Return True if the account is a budget account"""
        return account in self.config.data.budget_accounts
   
    @assert_loaded
    def write(self, what: list[str] = None, 
              sort = False,
              backup_dir = None,
              output_dir = None) -> None:
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
                # copy file
                shutil.copyfile(file.path, backup)

        def change_output_dir(file: CsvFile) -> CsvFile:
            if output_dir is not None:
                file.path = os.path.join(output_dir, os.path.basename(file.path))
            return file

        if sort:
            self.sort_data()

        if not what or "accounts" in what:
            backup_file(self.config.data.account_file)
            write_accounts(self.accounts(), change_output_dir(self.config.data.account_file), self.config.i18n)
        if not what or "balances" in what:
            backup_file(self.config.data.balance_file)
            write_balances(self.balance_assertions, change_output_dir(self.config.data.balance_file), self.config.i18n)
        if not what or "transactions" in what:
            backup_file(self.config.data.txn_file)
            write_txns(self.txns, change_output_dir(self.config.data.txn_file), self.config.i18n)

    @assert_loaded
    def export(self, today = None, output_dir = None) -> None:
        """Export the journal to csv files with extra precomputed columns
        
        If output_dir is None, use the files in config.export"""
        logger.debug("Exporting journal")
        if today is None:
            today = date.today()
        
        # FIXME we should not sort the journal data, but a copy of it
        self.sort_data()

        i18n = self.config.i18n

        def change_output_dir(file: CsvFile) -> CsvFile:
            if output_dir is not None:
                file.path = os.path.join(output_dir, os.path.basename(file.path))
            return file
        
        # Accounts
        write_accounts(self.accounts(), change_output_dir(self.config.export.account_file), self.config.i18n)

        # Transactions
        conf = self.config.export.txn_file.config
        header = [i18n[x] for x in txn_header]
        header.append(i18n["Posting id"])
        # Accounts related columns
        header.extend([i18n[x] for x in ["Account name", "Account number"]])
        max_level = max_depth(self.chart_of_accounts)
        for i in range(max_level):
            header.append(i18n.t("Account level ${level}", level=i+1))
        # Budget related columns
        header.extend([i18n[x] for x in ["Budget account", "Budgetable txn"]])
        # Datetime related columns
        header.extend([i18n [x] for x in ["Year", "Month","Year-Month","Relative year","Relative month","Fiscal year", "Fiscal month"]])
        # Other
        header.extend([i18n [x] for x in ["Other accounts"]])
        
        ls: list[list[str]] = [header]
        for t in self.txns:
            logger.debug(f"Exporting transaction {t.id}")
            budget_txn = i18n["Not budgetable"]
            for p in t.postings:
                if self.is_budget_account(p.account):
                    budget_txn = i18n["Budgetable"]
                    break

            for i, p in enumerate(t.postings, start=1):
                # Transactions columns
                row = [t.id, p.date, p.account.identifier, amount_to_str(p.amount, conf.decimal_separator), p.payee,
                         p.statement_date, p.statement_description, p.comment]
                row.append(i)

                # Accounts related columns
                row.extend([p.account.name, p.account.number])
                groups = p.account.get_account_and_parents()
                groups.reverse()
                for i in range(max_level):
                    if i < len(groups):
                        row.append(groups[i].name)
                    else:
                        row.append("")

                # Budget related columns
                budget_acc = i18n["True"] if self.is_budget_account(p.account) else i18n["False"]
                row.extend([budget_acc, budget_txn])

                # Datetime related columns
                rel_month = (p.date.year - today.year) * 12 + (p.date.month - today.month)
                year_month = f"{p.date.year}-{p.date.month:02d}"
                row.extend([p.date.year, p.date.month, year_month, p.date.year - today.year, rel_month,
                        self.fiscal_year(p.date), self.fiscal_month(p.date)])

                # Other
                other_accounts = set([x.account.name for x in t.postings if x.account != p.account])
                other_accounts = conf.join_separator.join(other_accounts)
                row.append(other_accounts)

                ls.append(row)

        write_csv(ls, change_output_dir(self.config.export.txn_file))

        # Balances
        write_balances(self.balance_assertions, change_output_dir(self.config.export.balance_file), self.config.i18n)

    def fiscal_month(self, dt: date) -> int:
        """Compute the fiscal month number
        """
        month = dt.month
        ffm = self.config.data.first_fiscal_month
        if month >= ffm:
            return month - ffm + 1
        else:
            return (12 - ffm + 1) + dt.month
    
    def fiscal_year(self, dt: date) -> int:
        """Compute the fiscal year
        """
        year = dt.year
        month = dt.month
        ffm = self.config.data.first_fiscal_month
        if ffm == 1 or month < ffm:
            return year
        else:
            return year + 1
    
    @assert_loaded
    def get_latest_balance_assertions(self, account: Account) -> Balance:
        """Get the newer balance assertions for the given account"""
        if account.number in self._assertion_by_account:
            return self._assertion_by_account[account.number][-1]
        else:
            return None

    @assert_loaded
    def add_txns(self, txns: list[Txn]) -> None:
        """Add new transactions
        
        The transactions numbers are set automatically"""
        next_id = max([t.id for t in self.txns]) + 1
        for t in txns:
            t.id = next_id
            next_id += 1
        self.txns.extend(txns)
        # FIXME this could be more fine grained. 
        # We should update it only for the accounts that are affected by the new transactions
        self._reset_cache()
        self._init_account_cache()
        self._init_txns_cache()

    @assert_loaded
    def add_balances(self, bals: list[Balance]) -> None:
        """Add new balance assertions"""
        self.balance_assertions.extend(bals)
        # FIXME this could be more fine grained. 
        # We should update it only for the accounts that are affected by the new transactions
        self._reset_cache()
        self._init_account_cache()
        self._init_txns_cache()

    @assert_loaded
    def account_balance(self, account: Account, dt: date, 
                        use_statement_date: bool = False,
                        include_subaccounts: bool = False) -> int:
        """Get the account balance at the given date"""
        d = self._account_st_balance if use_statement_date else self._account_balance
        accs = [account] if not include_subaccounts else account.get_account_and_descendants()
        total = 0
        for a in accs:
            if a.number not in d:
                continue
            idx = bisect_right(d[a.number], dt, key=lambda x: x[0])
            if idx:
                total += d[a.number][idx-1][1]

        return total

    @assert_loaded
    def verify_balances(self) -> None:
        """ Verify that the balances are consistent with the transactions"""
        bals = sorted(self.balance_assertions, key=lambda x: (x.date, x.account.number))
        for b in bals:
            txnAmount = self.account_balance(b.account, b.date, use_statement_date=True, include_subaccounts=True)

            if txnAmount != b.statement_balance:
                raise bberr.BalanceAssertionFailed(b.date, b.account.identifier, b.statement_balance, txnAmount, b.source)

    @assert_loaded
    def auto_import(self) -> list[Txn]:
        """Import new transactions from bank csv files
        
        Does not modify the journal. 
        Returns the list of new transactions. Use add_txns to add the transactions to the journal afterwards.
        Also writes the new transactions to a file and the unmatched statement description to another file.
        """ 
        # Check balances because autoimport will use the last balance
        self.verify_balances()
        rules =  load_classification_rules(self.config.import_.classification_rule_file, 
                                           self._accounts_by_name,
                                           filter_drop_all=True, i18n=self.config.i18n)
        # For each csv file in each import folder, import it
        txns: list[Txn] = []
        unmatched: dict[str, list[Posting]] = {}
        i18n = self.config.i18n
        for folder in self.config.import_.account_folders:
            import_conf_file = os.path.join(folder, i18n["import"] + ".yaml")
            import_config = load_import_config(import_conf_file, self._accounts_by_name, i18n)
            keys = self.posting_dedup_keys(import_config.account)
            fromDate = self.get_latest_balance_assertions(import_config.account)
            if fromDate:
                fromDate = fromDate.date + timedelta(days=1)
            for filename in os.listdir(folder):
                if filename.endswith(".csv"):
                    path = os.path.join(folder, filename)
                    csv_file = CsvFile(path, import_config.csv_config)
                    xs = import_from_bank_csv(csv_file, 
                                              import_config, 
                                              rules,
                                              from_date=fromDate,
                                              known_postings=keys)
                    txns.extend(xs)
                    # FIXME : There could be a match that sets the account to the default_snd_account
                    for t in xs:
                        if t.postings[1].account == import_config.default_snd_account:
                            p = t.postings[0]
                            desc = p.statement_description
                            if desc in unmatched:
                                unmatched[desc].append(p)
                            else:
                                unmatched[desc] = [p]           

        # Write new transactions to file
        for t in txns:
            t.postings.sort(key=lambda x: (x.date, x.account.number))
        txns.sort(key=lambda x: (x.postings[0].date, x.postings[0].account.number))

        next_id = max([t.id for t in self.txns]) + 1
        for txn in txns:
            txn.id = next_id
            next_id += 1
        write_txns(txns, self.config.import_.new_txns_file, i18n=self.config.i18n)
        
        # Write unmatched statement description to file
        ls: list[list[Posting]] = list(unmatched.values())
        ls.sort(key=lambda x: len(x), reverse=True)

        conf = self.config.import_.unmatched_payee_file.config
        with open(self.config.import_.unmatched_payee_file.path, "w", encoding=conf.encoding) as f:
            writer = csv.writer(f, delimiter=conf.column_separator,
                            quotechar=conf.quotechar, quoting=csv.QUOTE_MINIMAL)
            writer.writerow([self.config.i18n["Payee"], 
                             self.config.i18n["Count"],
                             self.config.i18n["Amount"],
                             self.config.i18n["Accounts"],
                             self.config.i18n["Min date"],
                             self.config.i18n["Max date"]])     
            for ps in ls:
                desc = ps[0].payee
                count = len(ps)
                amount = amount_to_str(sum([p.amount for p in ps]), conf.decimal_separator)
                accounts = conf.join_separator.join(set([p.account.name for p in ps]))
                mindate = min([p.date for p in ps])
                maxdate = max([p.date for p in ps])
                writer.writerow([desc, count, amount, accounts, mindate, maxdate])

        return txns

    @assert_loaded
    def auto_statement_date(self) -> list[Posting]:
        """Try to adjust the statement date of the postings to match the given balance assertion.
        Modify the journal.

        Returns the modified postings.
        """

        ps: list[Posting] = []
        self.sort_data() # Sort the data to sort the balance assertions
        for b in self.balance_assertions:
            if b.account in self.config.auto_statement_date.accounts:
                update_ps = self.auto_statement_date_find_ps(b, self.config.auto_statement_date.dayslimit)
                if update_ps:
                    for p in update_ps:
                        logger.info(f"Auto statement date ({b.date}): {p}")
                        p.statement_date = b.date + timedelta(days=1)
                    ps.extend(update_ps)
        # We must recompute the cache because the statement date has changed
        # FIXME this could be more fine grained.
        self._reset_cache()
        self._init_account_cache()
        self._init_txns_cache()
        return ps
    
    @assert_loaded
    def auto_statement_date_find_ps(self, Balance: Balance, dayslimit: int = 7) -> list[Posting]:
        """Try to adjust the statement date of the postings to match the given balance assertion
        
        Returns the list of postings to update. Use update_postings to update them afterwards.
        Returns None if no postings can be updated and the balance assertion is not met.
        """
        txnAmount = self.account_balance(Balance.account, Balance.date, use_statement_date=True, include_subaccounts=True)
        if txnAmount == Balance.statement_balance:
            return []

        ps: list[Posting] = []
        for a in Balance.account.get_account_and_descendants():
            if a.number in self._postings_by_account:
                ps.extend(self._postings_by_account[a.number])

        # Select the postings from psdict that matches the date range
        check = lambda x: (x.date <= Balance.date and
                           x.statement_date <= Balance.date and
                           x.date >= Balance.date - timedelta(days=dayslimit))
        ps = list(filter(check, ps))
        ps.sort(reverse=True,key=lambda x:x.date)

        update_pos = subset_sum(ps, txnAmount - Balance.statement_balance)

        return update_pos

    @assert_loaded
    def auto_balance(self) -> list[Txn]:
        """Balance the accounts with new transactions.
        Modify the journal.
        
        Returns the list of transactions to add.
        """

        txns: list[Txn] = []
        bals = sorted(self.balance_assertions, key=lambda x: (x.date, x.account.number))
        for b in bals:
            if b.account in self.config.auto_balance.accounts:
                snd_acc = self.config.auto_balance.accounts[b.account]
                t = self.auto_balance_with_new_txn(b, snd_acc)
                if t:
                    logger.info(f"Auto balance {b.account.identifier} {b.date}: {t}")
                    self.add_txns([t])
                    txns.append(t)
        return txns

    @assert_loaded
    def auto_balance_with_new_txn(self, b: Balance, snd_account: Account) -> Txn:
        """Balance the account with a new transaction
        
        Returns the transaction to add. Use add_txns to add the transaction afterwards.
        Returns None if the balance assertion is already met.
        """
        txnAmount = self.account_balance(b.account, b.date, use_statement_date=True, include_subaccounts=True)
        if txnAmount == b.statement_balance:
            return None

        diff = b.statement_balance - txnAmount
        t = Txn(None, [])
        p1 = Posting(b.date, b.account, diff, None, b.date, None, None, None)
        p2 = Posting(b.date, snd_account, - diff, None, b.date, None, None, None)
        t.postings = [p1, p2]
        return t

    @assert_loaded
    def posting_dedup_keys(self, account: Account = None, after: date = None) -> dict[tuple[date,str,int,str], int]:
        keys: dict[tuple[date,str,int,str], int] = {}
        for t in self.txns:
            for p in t.postings:
                if account and p.account != account:
                    continue
                if after and p.date <= after:
                    continue

                if p.dedup_key() in keys:
                    keys[p.dedup_key()] += 1
                else:
                    keys[p.dedup_key()] = 1
        return keys