import logging
import os
from yaml import safe_load
from balancebook.account import Account
from balancebook.i18n import I18n, supported_languages, get_default_i18n, translate_json_dict_to_en
from balancebook.csv import CsvFile, CsvConfig, SourcePosition
from balancebook.yaml import YamlElement, decode_yaml, csv_config_spec, space_to_underscore
from balancebook.errors import add_source_position

logger = logging.getLogger(__name__)

class DataConfig():
    def __init__(self, 
                 account_file: CsvFile, 
                 txn_file: CsvFile, 
                 balance_file: CsvFile):
        self.account_file = account_file
        self.txn_file = txn_file
        self.balance_file = balance_file

class ExportConfig():
    def __init__(self, 
                 # account_file: CsvFile,
                 txn_file: CsvFile,
                 # balance_file: CsvFile,
                 account_group: dict[str, tuple[str, str, list[Account]]] = None) -> None:
        # self.account_file = account_file
        self.txn_file = txn_file
        # self.balance_file = balance_file
        if account_group:
            self.account_groups = account_group
        else:
            self.account_groups = {}

class ImportConfig():
    def __init__(self, 
                 account_folders: list[str],
                 new_txns_file: CsvFile,
                 unmatched_payee_file: CsvFile) -> None:
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
                 default_csv_config: CsvConfig = None,
                 i18n: I18n = None,
                 first_fiscal_month: int = 1) -> None:
        self.config_path = config_path
        self.data = data_config
        self.export = export_config
        self.import_ = import_config
        self.auto_balance = auto_balance
        self.auto_statement_date = auto_statement_date
        self.backup_folder = backup_folder
        self.first_fiscal_month = first_fiscal_month
        if default_csv_config:
            self.default_csv_config = default_csv_config
        else:
            self.default_csv_config = CsvConfig()
        if i18n:
            self.i18n = i18n
        else:
            self.i18n = I18n() # English by default

def default_config(root_folder: str = "journal") -> JournalConfig:
    csv_config = CsvConfig()
    data_folder = os.path.join(root_folder, "data")
    export_folder = os.path.join(root_folder, "export")
    backup_folder = os.path.join(root_folder, "backup")

    data_config = DataConfig(CsvFile(os.path.join(data_folder, "accounts.csv"), csv_config),
                             CsvFile(os.path.join(data_folder, "transactions.csv"), csv_config),
                             CsvFile(os.path.join(data_folder, "balances.csv"), csv_config))

    export_config = ExportConfig(# CsvFile(os.path.join(export_folder, "accounts.csv"), csv_config),
                                 CsvFile(os.path.join(export_folder, "transactions.csv"), csv_config),
                                 # CsvFile(os.path.join(export_folder, "balances.csv"), csv_config),
                                 {})

    journal_config = JournalConfig(None,
                                   data_config,
                                   export_config,
                                   None,
                                   None,
                                   None,
                                   backup_folder)
    
    return journal_config

def load_config(path: str) -> JournalConfig:
    """Load the journal configuration from a YAML file."""

    root_folder = os.path.dirname(path)
    source = SourcePosition(path, None, None)
    
    # Infer language from the config file name (e.g. balancebook.fr.yaml)
    # if first extension is fr
    basename = os.path.basename(path)
    lang = os.path.splitext(os.path.splitext(basename)[0])[1]
    lang = lang[1:] # Remove the dot
    if lang not in supported_languages:
        logger.warning(f"Unknown language {lang} in {path}. Using English.")
        lang = "en"

    i18n = get_default_i18n(lang)

    def mk_path_abs(path: str, root: str = None) -> str:
        """Make a path absolute if it is not already, up to the root folder"""
        if root is None:
            root = root_folder

        if not os.path.isabs(path):
            return os.path.normpath(os.path.join(root, path))
        else:
            return path

    base_config = default_config(root_folder)
    with open(path, 'r') as f:
        data = safe_load(f)
        if lang != "en":
            data = translate_json_dict_to_en(data, i18n)
        
        default_csv_spec = csv_config_spec()
        spec = YamlElement("dict", dict_type={
            "root folder": YamlElement("str", required=False, default='.'),
            "default csv config": default_csv_spec,
            "backup folder": YamlElement("str", required=False, default='backup'),
            "data": YamlElement("dict", dict_type={
                "folder": YamlElement("str", required=False),
                "account file": YamlElement("str", required=False, default='accounts.csv'),
                "transaction file": YamlElement("str", required=False, default='transactions.csv'),
                "balance file": YamlElement("str", required=False)
            }, required=False),
            "export": YamlElement("dict", dict_type={
                "folder": YamlElement("str", required=False),
                # "account file": YamlElement("str", required=False),
                "transaction file": YamlElement("str", required=False),
                # "balance file": YamlElement("str", required=False),
                "account groups": YamlElement("list", list_type=YamlElement("dict", dict_type={
                    "name": YamlElement("str", required=True),
                    "true label": YamlElement("str", required=False, default=i18n["True"]),
                    "false label": YamlElement("str", required=False, default=i18n["False"]),
                    "accounts": YamlElement("list", required=True, list_type=YamlElement("str"))
                }), required=False, default=[])
            }, required=False),
            "first fiscal month": YamlElement("int", required=False, default=1),
            "import": YamlElement("dict", dict_type={
                "folder": YamlElement("str", required=False),
                "new transactions file": YamlElement("str", required=False, default='new transactions.csv'),
                "unmatched payees file": YamlElement("str", required=False, default='unmatched payees.csv'),
                "account folders": YamlElement("list", required=True, list_type=YamlElement("str"))
            }, required=False),
            "auto balance": YamlElement("dict", dict_type={
                "comment": YamlElement("str", required=False),
                "accounts": YamlElement("list", required=True, list_type=YamlElement("dict", dict_type={
                    "account": YamlElement("str"),
                    "balance from": YamlElement("str")
                }))
            }, required=False),
            "auto statement date": YamlElement("dict", dict_type={
                "accounts": YamlElement("list", required=True, list_type=YamlElement("str")),
                "days limit": YamlElement("int", required=False, default=7)
            }, required=False)
        })

        data = add_source_position(source)(decode_yaml)(data, spec, warn_extra_keys=True)

        root_folder = mk_path_abs(data["root folder"])
        default_csv = CsvConfig(**space_to_underscore(data["default csv config"]))
        backup_folder = mk_path_abs(data["backup folder"])

        # Data
        if "data" not in data:
            data_config = base_config.data
        else:
            data_folder = mk_path_abs(data["data"]["folder"]) if "folder" in data["data"] else root_folder
            if "balance file" not in data["data"]:
                balance_file = None
            else:
                balance_file = CsvFile(mk_path_abs(data["data"]["balance file"], data_folder), default_csv)
            data_config = DataConfig(CsvFile(mk_path_abs(data["data"]["account file"], data_folder), default_csv),
                                    CsvFile(mk_path_abs(data["data"]["transaction file"], data_folder), default_csv),
                                    balance_file)

        # Export
        if "export" not in data:
            export_folder = mk_path_abs("export")
            # export_acc_file = os.path.basename(data_config.account_file.path)
            export_txn_file = os.path.basename(data_config.txn_file.path)
            # if data_config.balance_file is None:
            #     export_bal_file = None
            # else:
            #     basename = os.path.basename(data_config.balance_file.path)
            #     export_bal_file = CsvFile(mk_path_abs(basename, export_folder), default_csv)
            export_config = ExportConfig(#CsvFile(mk_path_abs(export_acc_file, export_folder), default_csv),
                                         CsvFile(mk_path_abs(export_txn_file, export_folder), default_csv),
                                         #export_bal_file,
                                            {})
        else:
            export_folder = mk_path_abs(data["export"]["folder"]) if "folder" in data["export"] else root_folder
            # if "account file" not in data["export"]:
            #     export_acc_file = os.path.basename(data_config.account_file.path)
            # else:
            #     export_acc_file = data["export"]["account file"]
            if "transaction file" not in data["export"]:
                export_txn_file = os.path.basename(data_config.txn_file.path)
            else:
                export_txn_file = data["export"]["transaction file"]
            # if "balance file" not in data["export"]:
            #     if balance_file is None:
            #         export_bal_file = None
            #     else:
            #         basename = os.path.basename(data_config.balance_file.path)
            #         export_bal_file = CsvFile(mk_path_abs(basename, export_folder), default_csv)
            # else:
            #     export_bal_file = CsvFile(mk_path_abs(data["export"]["balance file"], export_folder), default_csv)
            groups = {}
            if data["export"]["account groups"] is not None:
                for group in data["export"]["account groups"]:
                    name = group["name"]
                    true_label = group["true label"]
                    false_label = group["false label"]
                    accounts = group["accounts"]
                    groups[name] = (true_label, false_label, accounts)
                
            export_config = ExportConfig(# CsvFile(mk_path_abs(export_acc_file, export_folder), default_csv),
                                        CsvFile(mk_path_abs(export_txn_file, export_folder), default_csv),
                                        # export_bal_file,
                                        groups)

        # Import
        import_config = None
        if "import" in data:
            import_folder = mk_path_abs(data["import"]["folder"])
            new_txns_file = CsvFile(mk_path_abs(data["import"]["new transactions file"], import_folder), default_csv)
            unmatched_payee_file = CsvFile(mk_path_abs(data["import"]["unmatched payees file"], import_folder), default_csv)
            account_folders = []
            for p in data["import"]["account folders"]:
                p = mk_path_abs(p, import_folder)
                account_folders.append(p)
            import_config = ImportConfig(account_folders, new_txns_file, unmatched_payee_file)
            
        # Auto balance
        auto_balance = None
        if "auto balance" in data:
            accounts = {}
            for ab in data["auto balance"]["accounts"]:
                account = ab["account"]
                balance_from = ab["balance from"]
                accounts[account] = balance_from
            comment = data["auto balance"]["comment"] if "comment" in data["auto balance"] else None
            auto_balance = AutoBalance(accounts, comment)

        # Auto statement date
        auto_statement_date = None
        if "auto statement date" in data:
            accounts = data["auto statement date"]["accounts"]
            dayslimit = data["auto statement date"]["days limit"]
            auto_statement_date = AutoStatementDate(accounts, dayslimit)

        config = JournalConfig(path,
                               data_config,
                               export_config,
                               import_config,
                               auto_balance,
                               auto_statement_date,
                               backup_folder,
                               default_csv_config=default_csv,
                               i18n=i18n,
                               first_fiscal_month=data["first fiscal month"])
        return config