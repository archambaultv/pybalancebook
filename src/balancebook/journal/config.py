import logging
import os
from yaml import safe_load
from balancebook.account import Account
from balancebook.i18n import I18n, supported_languages, get_default_i18n, translate_json_dict_to_en
from balancebook.csv import CsvFile, CsvConfig, read_int, SourcePosition, load_config_from_yaml

logger = logging.getLogger(__name__)

class DataConfig():
    def __init__(self, 
                 account_file: CsvFile, 
                 txn_file: CsvFile, 
                 balance_file: CsvFile,
                 first_fiscal_month: int = 1):
        self.account_file = account_file
        self.txn_file = txn_file
        self.balance_file = balance_file
        self.first_fiscal_month = first_fiscal_month

class ExportConfig():
    def __init__(self, 
                 account_file: CsvFile,
                 txn_file: CsvFile,
                 balance_file: CsvFile,
                 account_group: dict[str, tuple[str, str, list[Account]]] = None) -> None:
        self.account_file = account_file
        self.txn_file = txn_file
        self.balance_file = balance_file
        if account_group:
            self.account_groups = account_group
        else:
            self.account_groups = {}

class ImportConfig():
    def __init__(self, 
                 classification_rule_file: CsvFile,
                 account_folders: list[str],
                 new_txns_file: CsvFile,
                 unmatched_payee_file: CsvFile) -> None:
        self.classification_rule_file = classification_rule_file
        self.account_folders = account_folders
        self.new_txns_file = new_txns_file
        self.unmatched_payee_file = unmatched_payee_file

class AutoBalance():
    def __init__(self, accounts: dict[Account, Account], comment: str = None):
        """For accounts, the key is the account to auto-balance, the value is the account to balance against"""
        self.accounts = accounts
        self.comment = comment

class AutoStatementDate():
    def __init__(self, accounts: list[Account], dayslimit = 7):
        self.accounts = accounts
        self.dayslimit = dayslimit

class JournalConfig():
    def __init__(self, 
                 config_path: str,
                 data_config: DataConfig,
                 export_config: ExportConfig,
                 import_config: ImportConfig,
                 auto_balance: AutoBalance,
                 auto_statement_date: AutoStatementDate,
                 backup_folder: str,
                 i18n: dict[str,str] = None) -> None:
        self.config_path = config_path
        self.data = data_config
        self.export = export_config
        self.import_ = import_config
        self.auto_balance = auto_balance
        self.auto_statement_date = auto_statement_date
        self.backup_folder = backup_folder
        if i18n:
            self.i18n = I18n(i18n)
        else:
            self.i18n = I18n() # English by default

def default_config(root_folder: str = "journal") -> JournalConfig:
    csv_config = CsvConfig()
    data_folder = os.path.join(root_folder, "data")
    export_folder = os.path.join(root_folder, "export")
    import_folder = os.path.join(root_folder, "import")
    backup_folder = os.path.join(root_folder, "backup")

    data_config = DataConfig(CsvFile(os.path.join(data_folder, "accounts.csv"), csv_config),
                                CsvFile(os.path.join(data_folder, "transactions.csv"), csv_config),
                                CsvFile(os.path.join(data_folder, "balances.csv"), csv_config),
                                1)

    export_config = ExportConfig(CsvFile(os.path.join(export_folder, "accounts.csv"), csv_config),
                                    CsvFile(os.path.join(export_folder, "transactions.csv"), csv_config),
                                    CsvFile(os.path.join(export_folder, "balances.csv"), csv_config),
                                    {})

    import_config = ImportConfig(CsvFile(os.path.join(import_folder, "classification rules.csv"), csv_config),
                                    [],
                                    CsvFile(os.path.join(import_folder, "new transactions.csv"), csv_config),
                                    CsvFile(os.path.join(import_folder, "unmatched descriptions.csv"), csv_config))

    auto_balance = AutoBalance({}, None)
    auto_statement_date = AutoStatementDate([], 7)

    journal_config = JournalConfig(None,
                                   data_config,
                                   export_config,
                                   import_config,
                                   auto_balance,
                                   auto_statement_date,
                                   backup_folder)
    
    return journal_config

def load_config(path: str) -> JournalConfig:
    """Load the journal configuration from a YAML file."""

    root_folder = os.path.dirname(path)
    journal_config = default_config(root_folder)
    journal_config.config_path = path
    source = SourcePosition(path, None, None)
    
    # Infer language from the config file name (e.g. balancebook.fr.yaml)
    # if first extension is fr
    basename = os.path.basename(path)
    lang = os.path.splitext(os.path.splitext(basename)[0])[1]
    lang = lang[1:] # Remove the dot
    if lang in supported_languages:
        journal_config.i18n = get_default_i18n(lang)
    else:
        lang = "en"

    i18n = journal_config.i18n
    def mk_path_abs(path: str, root: str = None) -> str:
        """Make a path absolute if it is not already, up to the root folder"""
        if root is None:
            root = root_folder

        if not os.path.isabs(path):
            return os.path.normpath(os.path.join(root, path))
        else:
            return path

    with open(path, 'r') as f:
        data = safe_load(f)
        if lang != "en":
            data = translate_json_dict_to_en(data, i18n)

        if "root folder" in data:
            root_folder = mk_path_abs(data["root folder"])

        if "default csv config" in data:
            csv_config = load_config_from_yaml(data["default csv config"], source)

            journal_config.data.account_file.config = csv_config
            journal_config.data.txn_file.config = csv_config
            journal_config.data.balance_file.config = csv_config

            journal_config.export.account_file.config = csv_config
            journal_config.export.txn_file.config = csv_config
            journal_config.export.balance_file.config = csv_config

            journal_config.import_.classification_rule_file.config = csv_config
            journal_config.import_.new_txns_file.config = csv_config
            journal_config.import_.unmatched_payee_file.config = csv_config

        if "backup folder" in data:
            journal_config.backup_folder = mk_path_abs(data["backup folder"])
        
        if "data" in data:
            if "folder" in data["data"]:
                data_folder = mk_path_abs(data["data"]["folder"])
            else:
                data_folder = root_folder

            if "account file" in data["data"]:
                journal_config.data.account_file.path = mk_path_abs(data["data"]["account file"], data_folder)
            if "transaction file" in data["data"]:
                journal_config.data.txn_file.path = mk_path_abs(data["data"]["transaction file"], data_folder)
            if "balance file" in data["data"]:
                journal_config.data.balance_file.path = mk_path_abs(data["data"]["balance file"], data_folder)

            # Warns about unknown keys
            for key in data["data"]:
                if key not in ["folder", "account file", "transaction file", "balance file"]:
                    logger.warning(f"Unknown key {key} for object data in {source.file}")
  
        if "export" in data:
            if "folder" in data["export"]:
                export_folder = mk_path_abs(data["export"]["folder"])
            else:
                export_folder = root_folder
            if "account file" in data["export"]:
                journal_config.export.account_file.path = mk_path_abs(data["export"]["account file"], export_folder)
            if "transaction file" in data["export"]:
                journal_config.export.txn_file.path = mk_path_abs(data["export"]["transaction file"], export_folder)
            if "balance file" in data["export"]:
                journal_config.export.balance_file.path = mk_path_abs(data["export"]["balance file"], export_folder)
            if "account groups" in data["export"]:
                for group in data["export"]["account groups"]:
                    name = group["name"]
                    true_label = group.get("true label", i18n["True"])
                    false_label = group.get("false label", i18n["False"])
                    accounts = group["accounts"]
                    journal_config.export.account_groups[name] = (true_label, false_label, accounts)
            # Warns about unknown keys
            for key in data["export"]:
                if key not in ["folder", "account file", "transaction file", "balance file", "account groups"]:
                    logger.warning(f"Unknown key {key} for object export in {source.file}")
        
        if "first fiscal month" in data:
            journal_config.data.first_fiscal_month = read_int(data["first fiscal month"], source)

        if "import" in data:
            if "folder" in data["import"]:
                import_folder = mk_path_abs(data["import"]["folder"])
            else:
                import_folder = root_folder
            if "classification file" in data["import"]:
                journal_config.import_.classification_rule_file.path = mk_path_abs(data["import"]["classification file"], import_folder)
            if "new transactions file" in data["import"]:
                journal_config.import_.new_txns_file.path = mk_path_abs(data["import"]["new transactions file"], import_folder)
            if "unmatched payees file" in data["import"]:
                journal_config.import_.unmatched_payee_file.path = mk_path_abs(data["import"]["unmatched payees file"], import_folder)
            if "account folders" in data["import"]:
                journal_config.import_.account_folders = []
                for p in data["import"]["account folders"]:
                    p = mk_path_abs(p, import_folder)
                    journal_config.import_.account_folders.append(p)
            # Warns about unknown keys
            for key in data["import"]:
                if key not in ["folder", "classification file", "new transactions file", "unmatched payees file", "account folders"]:
                    logger.warning(f"Unknown key {key} for object import in {source.file}")

        if "auto balance" in data:
            if "comment" in data["auto balance"]:
                journal_config.auto_balance.comment = data["auto balance"]["comment"]
            if "accounts" in data["auto balance"]:
                auto_balance = {}
                for ab in data["auto balance"]["accounts"]:
                    account = ab["account"]
                    balance_from = ab["balance from"]
                    auto_balance[account] = balance_from
                journal_config.auto_balance.accounts = auto_balance
            # Warns about unknown keys
            for key in data["auto balance"]:
                if key not in ["comment", "accounts"]:
                    logger.warning(f"Unknown key {key} for object auto balance in {source.file}")

        if "auto statement date" in data:
            if "accounts" in data["auto statement date"]:
                journal_config.auto_statement_date.accounts = data["auto statement date"]["accounts"]
            if "days limit" in data["auto statement date"]:
                journal_config.auto_statement_date.dayslimit = data["auto statement date"]["days limit"]
            # Warns about unknown keys
            for key in data["auto statement date"]:
                if key not in ["accounts", "days limit"]:
                    logger.warning(f"Unknown key {key} for object auto statement date in {source.file}")

        if "i18n" in data:
            journal_config.i18n = data["i18n"]

        # Warns about unknown keys
        for key in data:
            if key not in ["root folder", "default csv config", "backup folder", 
                           "data", "export", "first fiscal month", "import", "auto balance", 
                           "auto statement date", "i18n"]:
                logger.warning(f"Unknown key {key} in {source.file}")

    return journal_config