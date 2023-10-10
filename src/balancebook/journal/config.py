import logging
import os
from yaml import safe_load
from balancebook.csv import CsvFile, CsvConfig, read_int, SourcePosition

logger = logging.getLogger(__name__)

class ExportConfig():
    def __init__(self, export_folder: str,
                 csv_config: CsvConfig,
                 i18n: dict[str,str] = None) -> None:
        self.export_folder = export_folder
        self.csv_config = csv_config
        if i18n:
            self.i18n = i18n
        else:
            self.i18n = {}

class JournalConfig():
    def __init__(self, 
                 account_file: CsvFile, txn_file: CsvFile, 
                 classification_rule_file: CsvFile,
                 balance_file: CsvFile,
                 budget_txns: CsvFile, budget_accounts: list[str],
                 export_config: ExportConfig,
                 first_fiscal_month: int = 1) -> None:
        self.account_file = account_file
        self.txn_file = txn_file
        self.classification_rule_file = classification_rule_file
        self.balance_file = balance_file
        self.budget_txn_file = budget_txns
        self.budget_accounts = budget_accounts
        self.export_config = export_config
        self.first_fiscal_month = first_fiscal_month

def load_config(path: str) -> JournalConfig:
    """Load the journal configuration from a YAML file.
    
    The structure of the journal folder is fixed for now."""
    journal_config = JournalConfig(CsvFile("journal/data/accounts.csv"), 
                                   CsvFile("journal/data/transactions.csv"),
                                   CsvFile("journal/data/classification rules.csv"),
                                   CsvFile("journal/data/balances.csv"),
                                   CsvFile("journal/data/budget txns rules.csv"),
                                   [],
                                   ExportConfig("journal/export", CsvConfig()),
                                   1)
    csv_config = CsvConfig()
    source = SourcePosition(path, None, None)
    with open(path, 'r') as f:
        data = safe_load(f)

        if "root folder" in data:
            if not os.path.isabs(data["root folder"]):
                root_folder = os.path.join(os.path.dirname(path), data["root folder"])
            else:
                root_folder = data["root folder"]
            journal_config.account_file.path = os.path.normpath(os.path.join(root_folder, "data", "accounts.csv"))
            journal_config.txn_file.path = os.path.normpath(os.path.join(root_folder, "data", "transactions.csv"))
            journal_config.classification_rule_file.path = os.path.normpath(os.path.join(root_folder, "data", "classification rules.csv"))
            journal_config.balance_file.path = os.path.normpath(os.path.join(root_folder, "data", "balances.csv"))
            journal_config.budget_txn_file.path = os.path.normpath(os.path.join(root_folder, "data", "budget txn rules.csv"))
            journal_config.export_config.export_folder = os.path.normpath(os.path.join(root_folder, "export"))

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
            journal_config.export_config.csv_config = csv_config  
        
        if "first fiscal month" in data:
            journal_config.first_fiscal_month = read_int(data["first fiscal month"], source)

        if "budget accounts" in data:
            journal_config.budget_accounts = data["budget accounts"]

        if "export" in data:
            journal_config.export_config.export_folder = data["export"].get("folder", journal_config.export_config.export_folder)
        
        if "i18n" in data:
            journal_config.export_config.i18n = data["i18n"]

    return journal_config