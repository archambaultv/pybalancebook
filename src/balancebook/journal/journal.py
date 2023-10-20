import os
import logging
import csv
import shutil
from datetime import date, datetime, timedelta

import balancebook.errors as bberr
from balancebook.amount import amount_to_str
from balancebook.account import ChartOfAccounts, max_depth, Account, load_accounts, write_accounts, write_accounts_to_list
from balancebook.transaction import (Txn, Posting, load_txns, write_txns, postings_by_account_by_date, compute_account_balance,
                                     balance, subset_sum, write_txns_to_list, postings_by_account, txn_header)
from balancebook.balance import Balance, load_balances, write_balances, balance_by_account, write_balances_to_list
from balancebook.csv import CsvFile, write_csv, SourcePosition
from balancebook.utils import fiscal_month, fiscal_year
from balancebook.journal.autoimport import (load_import_config, load_classification_rules,
                                            import_from_bank_csv)
from balancebook.journal.config import JournalConfig

logger = logging.getLogger(__name__)

class Journal():
    def __init__(self, config: JournalConfig) -> None:
        self.config = config
        self.chart_of_accounts: ChartOfAccounts = None
        self.accounts: list[Account] = None
        self.txns: list[Txn] = None
        self.balance_assertions: list[Balance] = None

        # Cache of various dictionaries
        self.accounts_by_name: dict[str,Account] = None
        self.accounts_by_number: dict[int,Account] = None

        self.txns_by_id: dict[int,Txn] = None

        self.postings_by_id: dict[int,Posting] = None
        self.postings_by_account: dict[int, list[Posting]] = None
        self.postings_by_account_by_date: dict[int,list[tuple[date,list[Posting]]]] = None

        self.assertion_by_account: dict[int,list[Balance]] = None
        self.balance_by_account_by_date: dict[int,list[tuple[date,int]]] = None

    def __reset_cache__(self) -> None:
        self.accounts_by_number = None
        self.accounts_by_name = None
        self.txns_by_id = None
        self.postings_by_account = None
        self.postings_by_account_by_date = None
        self.balance_by_account_by_date = None
        self.assertion_by_account = None

    def __init_account_cache__(self) -> None:
        self.accounts_by_name = dict([(a.identifier, a) for a in self.accounts])
        self.accounts_by_number = dict([(a.number, a) for a in self.accounts])

    def __init_txns_cache__(self) -> None:
        self.txns_by_id = dict([(t.id, t) for t in self.txns])
        self.postings_by_account = postings_by_account(self.txns)
        self.postings_by_account_by_date = postings_by_account_by_date(self.txns, False)
        self.balance_by_account_by_date = compute_account_balance(self.postings_by_account_by_date)
        self.assertion_by_account = balance_by_account(self.balance_assertions)

    def sort_data(self) -> None:
        """Sort the data in the journal"""
        self.accounts.sort(key=lambda x: x.number)
        self.txns.sort(key=lambda x: (x.min_date(),x.postings[0].account.number, x.id))
        self.balance_assertions.sort(key=lambda x: (x.date, x.account.number))

    def get_account_by_id(self) -> dict[str,Account]:
        if self.accounts_by_number is None:
            self.__init_account_cache__()
        return self.accounts_by_number

    def get_account_by_name(self) -> dict[str,Account]:
        if self.accounts_by_name is None:
            self.__init_account_cache__()
        return self.accounts_by_name

    def get_txns_by_id(self) -> dict[int,Txn]:
        if self.txns_by_id is None:
            self.__init_txns_cache__()
        return self.txns_by_id
    
    def get_postings_by_id(self) -> dict[int,Posting]:
        if self.postings_by_id is None:
            self.__init_txns_cache__()
        return self.postings_by_id

    def get_postings_by_account(self) -> dict[int,list[Posting]]:
        if self.postings_by_account is None:
            self.__init_txns_cache__()
        return self.postings_by_account

    def get_postings_by_account_by_date(self) -> dict[int,dict[date,list[Posting]]]:
        if self.postings_by_account_by_date is None:
            self.__init_txns_cache__()
        return self.postings_by_account_by_date

    def get_balance_by_account_by_date(self) -> dict[int,list[tuple[date,int]]]:
        if self.balance_by_account_by_date is None:
            self.__init_txns_cache__()
        return self.balance_by_account_by_date
    
    def get_assertion_by_account(self) -> dict[int,list[Balance]]:
        if self.assertion_by_account is None:
            self.__init_txns_cache__()
        return self.assertion_by_account

    def is_budget_account(self, account: Account) -> bool:
        """Return True if the account is a budget account"""
        return account.identifier in self.config.data.budget_accounts

    def load(self) -> None:
        """Load the journal from files
    
        Normalize the journal data"""
        self.__reset_cache__()

        self.chart_of_accounts: ChartOfAccounts = load_accounts(self.config.data.account_file, self.config.i18n)
        self.accounts = [a for t in self.chart_of_accounts for a in t.get_account_and_descendants()]
        self.accounts_by_name = self.get_account_by_name()
        self.txns = load_txns(self.config.data.txn_file, self.accounts_by_name, self.config.i18n)
        self.balance_assertions = load_balances(self.config.data.balance_file, self.accounts_by_name, self.config.i18n)

        # Convert auto balance accounts to Account
        accounts2 = {}
        for acc, acc2 in self.config.auto_balance.accounts.items():
            source = SourcePosition(self.config.config_path, 0, 0)
            try:
                new_acc = self.accounts_by_name[acc]
            except KeyError:
                raise bberr.UnknownAccount(acc, source)
            try:
                new_acc2 = self.accounts_by_name[acc2]
            except KeyError:
                raise bberr.UnknownAccount(acc2, source)
            accounts2[new_acc] = new_acc2
        self.config.auto_balance.accounts = accounts2

        # Convert auto statement dates accounts to accounts
        accounts2 = []
        for acc in self.config.auto_statement_date.accounts:
            source = SourcePosition(self.config.config_path, 0, 0)
            try:
                new_acc = self.accounts_by_name[acc]
            except KeyError:
                raise bberr.UnknownAccount(acc, source)
            accounts2.append(new_acc)
        self.config.auto_statement_date.accounts = accounts2
        

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
            write_accounts(self.accounts, change_output_dir(self.config.data.account_file), self.config.i18n)
        if not what or "balances" in what:
            backup_file(self.config.data.balance_file)
            write_balances(self.balance_assertions, change_output_dir(self.config.data.balance_file), self.config.i18n)
        if not what or "transactions" in what:
            backup_file(self.config.data.txn_file)
            write_txns(self.txns, change_output_dir(self.config.data.txn_file), self.config.i18n)

    def export(self, today = None, output_dir = None) -> None:
        """Export the journal to csv files with extra precomputed columns
        
        If output_dir is None, use the files in config.export"""
        if today is None:
            today = date.today()
        self.sort_data()

        i18n = self.config.i18n

        def change_output_dir(file: CsvFile) -> CsvFile:
            if output_dir is not None:
                file.path = os.path.join(output_dir, os.path.basename(file.path))
            return file
        
        # Accounts
        write_accounts(self.accounts, change_output_dir(self.config.export.account_file), self.config.i18n)

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
            budget_txn = i18n["Not budgetable"]
            for p in t.postings:
                if self.is_budget_account(p.account):
                    budget_txn = i18n["Budgetable"]
                    break

            for i, p in enumerate(t.postings, start=1):
                # Transactions columns
                row = [t.id, p.date, p.account.identifier, amount_to_str(p.amount, conf.decimal_separator), 
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
        return fiscal_month(dt, self.config.data.first_fiscal_month)
    
    def fiscal_year(self, dt: date) -> int:
        return fiscal_year(dt, self.config.data.first_fiscal_month)

    def get_newest_balance_assertions(self, account: Account) -> Balance:
        """Get the newer balance assertions for the given account"""
        d = self.get_assertion_by_account()
        if account.number in d:
            return d[account.number][-1]
        else:
            return None

    def set_txns(self, txns: list[Txn]) -> None:
        """Set the transactions
        
        Makes a copy of the transactions because posting ids are set automatically"""
        self.txns = txns
        self.__reset_cache__()

    def update_txns(self, txns: list[Txn]) -> None:
        """Update the transactions"""
        d = self.get_txns_by_id()
        for t in txns:
            if t.id in d:
                old_t = d[t.id]
                old_t.postings = t.postings
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
        # FIXME this could be more fine grained. 
        # We should update it only for the accounts that are affected by the new transactions
        self.__reset_cache__()

    def new_balances(self, bals: list[Balance]) -> None:
        """Add new balance assertions"""
        self.balance_assertions.extend(bals)
        self.__reset_cache__()

    def account_balance(self, account: Account, dt: date) -> int:
        """Get the account balance at the given date"""
        d = self.get_balance_by_account_by_date()
        return balance(account, dt, d)

    def verify_balances(self) -> None:
        """ Verify that the balances are consistent with the transactions"""
        bals = sorted(self.balance_assertions, key=lambda x: (x.date, x.account.number))
        ps = postings_by_account_by_date(self.txns, True)
        d = compute_account_balance(ps)
        for b in bals:
            txnAmount = 0
            for a in b.account.get_account_and_descendants():
                txnAmount += balance(a, b.date, d)

            if txnAmount != b.statement_balance:
                raise bberr.BalanceAssertionFailed(b.date, b.account.identifier, b.statement_balance, txnAmount, b.source)

    def auto_import(self) -> list[Txn]:
        """Import new transactions from bank csv files
        
        Does not modify the journal. 
        Returns the list of new transactions. Use new_txns to add the transactions to the journal afterwards.
        Also writes the new transactions to a file and the unmatched statement description to another file.
        """ 
        # Check balances because autoimport will use the last balance
        self.verify_balances()
        rules =  load_classification_rules(self.config.import_.classification_rule_file, 
                                           self.get_account_by_name(),
                                           filter_drop_all=True, i18n=self.config.i18n)
        # For each csv file in each import folder, import it
        txns: list[Txn] = []
        unmatched: dict[str, list[Posting]] = {}
        i18n = self.config.i18n
        for folder in self.config.import_.account_folders:
            import_conf_file = os.path.join(folder, i18n["import"] + ".yaml")
            import_config = load_import_config(import_conf_file, self.get_account_by_name(), i18n)
            keys = self.posting_dedup_keys(import_config.account)
            fromDate = self.get_newest_balance_assertions(import_config.account)
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
        txns.sort(key=lambda x: (x.min_date(), x.postings[0].account.number))
        next_id = max([t.id for t in self.txns]) + 1
        for txn in txns:
            txn.id = next_id
            next_id += 1
        write_txns(txns, self.config.import_.new_txns_file, i18n=self.config.i18n)
        
        # Write unmatched statement description to file
        ls: list[list[Posting]] = list(unmatched.values())
        ls.sort(key=lambda x: len(x), reverse=True)

        conf = self.config.import_.unmatched_desc_file.config
        with open(self.config.import_.unmatched_desc_file.path, "w", encoding=conf.encoding) as f:
            writer = csv.writer(f, delimiter=conf.column_separator,
                            quotechar=conf.quotechar, quoting=csv.QUOTE_MINIMAL)
            writer.writerow([self.config.i18n["Description"], 
                             self.config.i18n["Count"],
                             self.config.i18n["Amount"],
                             self.config.i18n["Accounts"],
                             self.config.i18n["Min date"],
                             self.config.i18n["Max date"]])     
            for ps in ls:
                desc = ps[0].statement_description
                count = len(ps)
                amount = amount_to_str(sum([p.amount for p in ps]), conf.decimal_separator)
                accounts = conf.join_separator.join(set([p.account.name for p in ps]))
                mindate = min([p.date for p in ps])
                maxdate = max([p.date for p in ps])
                writer.writerow([desc, count, amount, accounts, mindate, maxdate])

        return txns

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
        return ps
    
    def auto_statement_date_find_ps(self, Balance: Balance, dayslimit: int = 7) -> list[Posting]:
        """Try to adjust the statement date of the postings to match the given balance assertion
        
        Returns the list of postings to update. Use update_postings to update them afterwards.
        Returns None if no postings can be updated and the balance assertion is not met.
        """
        pd = postings_by_account_by_date(self.txns, True)
        d = compute_account_balance(pd)
        txnAmount = balance(Balance.account, Balance.date, d)
        if txnAmount == Balance.statement_balance:
            return []

        ps: list[Posting] = self.get_postings_by_account()[Balance.account.number]
        # Select the postings from psdict that matches the date range
        check = lambda x: (x.date <= Balance.date and
                           x.statement_date <= Balance.date and
                           x.date >= Balance.date - timedelta(days=dayslimit))
        ps = list(filter(check, ps))
        ps.sort(reverse=True,key=lambda x:x.date)

        update_pos = subset_sum(ps, txnAmount - Balance.statement_balance)

        return update_pos

    def auto_balance(self) -> list[Txn]:
        """Balance the accounts with new transactions.
        Modify the journal.
        
        Returns the list of transactions to add.
        """

        txns: list[Txn] = []
        self.sort_data() # Sort the data to sort the balance assertions
        for b in self.balance_assertions:
            if b.account in self.config.auto_balance.accounts:
                snd_acc = self.config.auto_balance.accounts[b.account]
                t = self.auto_balance_with_new_txn(b, snd_acc)
                if t:
                    logger.info(f"Auto balance: {t}")
                    self.new_txns([t])
                    txns.append(t)
        return txns

    def auto_balance_with_new_txn(self, b: Balance, snd_account: Account) -> Txn:
        """Balance the account with a new transaction
        
        Returns the transaction to add. Use new_txns to add the transaction afterwards.
        Returns None if the balance assertion is already met.
        """
        d = self.get_balance_by_account_by_date()
        txnAmount = balance(b.account, b.date, d)
        if txnAmount == b.statement_balance:
            return None

        diff = b.statement_balance - txnAmount
        t = Txn(None, [])
        p1 = Posting(b.date, b.account, diff, b.date, None, None, None)
        p2 = Posting(b.date, snd_account, - diff, b.date, None, None, None)
        t.postings = [p1, p2]
        return t

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