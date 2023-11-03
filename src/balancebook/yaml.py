import logging
from datetime import date
from yaml import safe_load

from balancebook.csv import read_date, read_int, read_yyyy_mm_date, CsvConfig
import balancebook.errors as bberr
from balancebook.amount import any_to_amount

logger = logging.getLogger(__name__)

class YamlElement():
    def __init__(self,
                 type: str, 
                 required: bool = True,
                 default: any = None,
                 list_type: 'YamlElement' = None,
                 dict_type: dict[str, 'YamlElement'] = None) -> None:
        """
        type: type of the element (str, int, date, amount, ymdate, list, dict)
        required: True if the element is required. Applies only to dict elements.
        default: default value if the element is not present. Applies only to dict elements. 
            If default is None, the element will not be present in the dict.
        list_type: type of the list elements
        dict_type: type of the dict values
        """
        self.type = type
        self.required = required
        self.default = default
        self.list_type = list_type
        self.dict_type = dict_type

def decode_yaml(data: any, spec: YamlElement, warn_extra_keys: bool = False) -> any:
    """Decode a yaml file"""

    if spec.type == "str":
        if not isinstance(data, str):
            raise bberr.InvalidYamlType("str", type(data))
        return data
    elif spec.type == "int":
        if isinstance(data, int):
            return data
        elif isinstance(data, str):
            return read_int(data)
        else:
            raise bberr.InvalidYamlType("int", type(data))
    elif spec.type == "date":
        if isinstance(data, str):
            return read_date(data)
        elif isinstance(data, date):
            return data
        else:
            raise bberr.InvalidYamlType("date", type(data))
    elif spec.type == "amount":
        if isinstance(data, str):
            return any_to_amount(data)
        elif isinstance(data, int):
            return any_to_amount(data)
        else:
            raise bberr.InvalidYamlType("amount", type(data))
    elif spec.type == "ymdate":
        if isinstance(data, str):
            return read_yyyy_mm_date(data)
        elif isinstance(data, date):
            return data
        else:
            raise bberr.InvalidYamlType("ymdate", type(data))
    elif spec.type == "list":
        if not isinstance(data, list):
            raise bberr.InvalidYamlType("list", type(data))
        return [decode_yaml(e, spec.list_type) for e in data]
    elif spec.type == "dict":
        if not isinstance(data, dict):
            raise bberr.InvalidYamlType("dict", type(data))
        if warn_extra_keys:
            for k in data.keys():
                if k not in spec.dict_type:
                    logger.warning(f"Unknown key '{k}' in YAML config.")
        d = {}
        for k, e in spec.dict_type.items():
            if k in data:
                d[k] = decode_yaml(data[k], e)
            elif e.required:
                raise bberr.MissingRequiredKey(k)
            elif e.default is not None:
                    d[k] = e.default
        return d
    
def csv_config_spec() -> YamlElement:
    """Return the YAML spec for the CSV config"""
    default = CsvConfig()
    return YamlElement("dict",required=False, default=default, dict_type={
        "encoding": YamlElement("str", required=False, default=default.encoding),
        "column separator": YamlElement("str", required=False, default=default.column_separator),
        "quotechar": YamlElement("str", required=False, default=default.quotechar),
        "decimal separator": YamlElement("str", required=False, default=default.decimal_separator),
        "skip X lines": YamlElement("int", required=False, default=default.skip_X_lines),
        "join separator": YamlElement("str", required=False, default=default.join_separator),
        "thousands separator": YamlElement("str", required=False, default=default.thousands_separator),
        "currency sign": YamlElement("str", required=False, default=default.currency_sign)
    })

def space_to_underscore(d: dict[str, any]) -> dict[str, any]:
    """Replace spaces in keys by underscores"""
    return {k.replace(" ", "_"): v for k, v in d.items()}