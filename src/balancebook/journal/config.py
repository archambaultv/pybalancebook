import logging
import os
from yaml import safe_load
from balancebook.csv import CsvFile, CsvConfig, read_int, SourcePosition

logger = logging.getLogger(__name__)

class ExportConfig():
    def __init__(self, 
                 account_file: CsvFile,
                 txn_file: CsvFile,
                 classification_rule_file: CsvFile,
                 balance_file: CsvFile ,
                 budget_txn_file: CsvFile,
                 i18n: dict[str,str] = None) -> None:
        self.account_file = account_file
        self.txn_file = txn_file
        self.classification_rule_file = classification_rule_file
        self.balance_file = balance_file
        self.budget_txn_file = budget_txn_file
        if i18n:
            self.i18n = i18n
        else:
            self.i18n = {}

class JournalConfig():
    def __init__(self, 
                 account_file: CsvFile, 
                 txn_file: CsvFile, 
                 classification_rule_file: CsvFile,
                 balance_file: CsvFile,
                 budget_txns: CsvFile, 
                 budget_accounts: list[str],
                 export_config: ExportConfig,
                 backup_folder: str,
                 first_fiscal_month: int = 1) -> None:
        self.account_file = account_file
        self.txn_file = txn_file
        self.classification_rule_file = classification_rule_file
        self.balance_file = balance_file
        self.budget_txn_file = budget_txns
        self.budget_accounts = budget_accounts
        self.export_config = export_config
        self.backup_folder = backup_folder
        self.first_fiscal_month = first_fiscal_month

def load_config(path: str) -> JournalConfig:
    """Load the journal configuration from a YAML file.
    
    The structure of the journal folder is fixed for now."""
    export_config = ExportConfig(CsvFile("journal/export/accounts.csv"),
                                    CsvFile("journal/export/transactions.csv"),
                                    CsvFile("journal/export/classification rules.csv"),
                                    CsvFile("journal/export/balances.csv"),
                                    CsvFile("journal/export/budget txn rules.csv"),
                                    {})

    journal_config = JournalConfig(CsvFile("journal/data/accounts.csv"), 
                                   CsvFile("journal/data/transactions.csv"),
                                   CsvFile("journal/data/classification rules.csv"),
                                   CsvFile("journal/data/balances.csv"),
                                   CsvFile("journal/data/budget txns rules.csv"),
                                   [],
                                   export_config,
                                   "journal/data/backup",
                                   1)
    csv_config = CsvConfig()
    source = SourcePosition(path, None, None)
    root_folder = "journal"
    with open(path, 'r') as f:
        data = safe_load(f)

        if "root folder" in data:
            root_folder = data["root folder"]
            if not os.path.isabs(data["root folder"]):
                root_folder = os.path.join(os.path.dirname(path), root_folder)

            journal_config.backup_folder = os.path.normpath(os.path.join(root_folder, "data", "backup"))
                
            journal_config.account_file.path = os.path.normpath(os.path.join(root_folder, "data", "accounts.csv"))
            journal_config.txn_file.path = os.path.normpath(os.path.join(root_folder, "data", "transactions.csv"))
            journal_config.classification_rule_file.path = os.path.normpath(os.path.join(root_folder, "data", "classification rules.csv"))
            journal_config.balance_file.path = os.path.normpath(os.path.join(root_folder, "data", "balances.csv"))
            journal_config.budget_txn_file.path = os.path.normpath(os.path.join(root_folder, "data", "budget txn rules.csv"))

            journal_config.export_config.account_file.path = os.path.normpath(os.path.join(root_folder, "export", "accounts.csv"))
            journal_config.export_config.txn_file.path = os.path.normpath(os.path.join(root_folder, "export", "transactions.csv"))
            journal_config.export_config.classification_rule_file.path = os.path.normpath(os.path.join(root_folder, "export", "classification rules.csv"))
            journal_config.export_config.balance_file.path = os.path.normpath(os.path.join(root_folder, "export", "balances.csv"))
            journal_config.export_config.budget_txn_file.path = os.path.normpath(os.path.join(root_folder, "export", "budget transactions.csv"))

        if "default csv config" in data:
            csv_config = CsvConfig(data["default csv config"].get("encoding", csv_config.encoding),
                                   data["default csv config"].get("column separator", csv_config.column_separator),
                                   data["default csv config"].get("quotechar", csv_config.quotechar),
                                   data["default csv config"].get("decimal separator", csv_config.decimal_separator),
                                   read_int(data["default csv config"].get("skip X lines", csv_config.skip_X_lines), source),
                                   data["default csv config"].get("join separator", csv_config.join_separator),
                                   data["default csv config"].get("thousands separator", csv_config.thousands_separator),
                                   data["default csv config"].get("currency sign", csv_config.currency_sign))
            journal_config.account_file.config = csv_config
            journal_config.txn_file.config = csv_config
            journal_config.classification_rule_file.config = csv_config
            journal_config.balance_file.config = csv_config
            journal_config.budget_txn_file.config = csv_config

            journal_config.export_config.account_file.config = csv_config
            journal_config.export_config.txn_file.config = csv_config
            journal_config.export_config.classification_rule_file.config = csv_config
            journal_config.export_config.balance_file.config = csv_config
            journal_config.export_config.budget_txn_file.config = csv_config
        
        if "first fiscal month" in data:
            journal_config.first_fiscal_month = read_int(data["first fiscal month"], source)

        if "budget accounts" in data:
            journal_config.budget_accounts = data["budget accounts"]

        if "export" in data:
            if "folder" in data["export"]:
                export_folder = data["export"]["folder"]
                if not os.path.isabs(export_folder):
                    root_folder = os.path.join(root_folder, export_folder)

            if "account file" in data["export"]:
                journal_config.export_config.account_file.path = os.path.normpath(os.path.join(export_folder, data["export"]["account file"]))
            else:
                journal_config.export_config.account_file.path = os.path.normpath(os.path.join(export_folder, "accounts.csv"))

            if "transaction file" in data["export"]:
                journal_config.export_config.txn_file.path = os.path.normpath(os.path.join(export_folder, data["export"]["transaction file"]))
            else:
                journal_config.export_config.txn_file.path = os.path.normpath(os.path.join(export_folder, "transactions.csv"))

            if "classification file" in data["export"]:
                journal_config.export_config.classification_rule_file.path = os.path.normpath(os.path.join(export_folder, data["export"]["classification file"]))
            else:
                journal_config.export_config.classification_rule_file.path = os.path.normpath(os.path.join(export_folder, "classification rules.csv"))            
        
            if "balance file" in data["export"]:
                journal_config.export_config.balance_file.path = os.path.normpath(os.path.join(export_folder, data["export"]["balance file"]))
            else:
                journal_config.export_config.balance_file.path = os.path.normpath(os.path.join(export_folder, "balances.csv"))

            if "budget txn file" in data["export"]:
                journal_config.export_config.budget_txn_file.path = os.path.normpath(os.path.join(export_folder, data["export"]["budget txn file"]))
            else:
                journal_config.export_config.budget_txn_file.path = os.path.normpath(os.path.join(export_folder, "budget transactions.csv"))

        if "i18n" in data:
            journal_config.export_config.i18n = data["i18n"]

    return journal_config