# Small i18n module for Balancebook

# Used so the user can have the csv and config files in his own language
import json
import yaml
import os
from typing import Any
from string import Template

import balancebook.errors as bberr

class I18n:
    """Internationalization class.
    
    Basically a english to another language dictionary.
    Fall back to english if the key is not found in the dictionary.
    """

    def __init__(self, dict: dict[str,str] = None) -> None:
        """Initialize the i18n class
        
        dict: dictionary of translations.
        If dict is None, no translation will be done.
        """
        self.i18n = dict

    def __getitem__(self, key: str) -> str:
        """Translate a string"""
        if self.i18n is None or key not in self.i18n:
            return key
        return self.i18n[key]
    
    def translate(self, key: str, **kwargs) -> str:
        """Translate a string with keyword arguments"""
        if self.i18n is None or key not in self.i18n:
            return Template(key).safe_substitute(**kwargs)
        
        return Template(self.i18n[key]).safe_substitute(**kwargs)
    
    def t(self, key: str, **kwargs) -> str:
        """Translate a string with keyword arguments"""
        return self.translate(key, **kwargs)

# Load a i18n dictionary from a json file
def load_i18n_from_file(path: str) -> I18n:
    """Load a i18n dictionary from a json file"""
    # Check if extension is yaml or json
    ext = os.path.splitext(path)[1]
    with open(path, encoding="utf-8") as f:
        if ext == ".yaml" or ext == ".yml":
            return I18n(yaml.safe_load(f))
        else:
            return I18n(json.load(f))

supported_languages = ["en", "fr"]

def get_default_i18n(lang: str) -> I18n:
    """Get the default i18n dictionary for the given language"""
    if lang == "en":
        return I18n()
    elif lang == "fr":
        path = os.path.join(os.path.dirname(__file__),'..','..', "i18n", lang + ".json")
        return load_i18n_from_file(path)
    else:
        return bberr.InvalidLanguage(lang)
    
def translate_json_dict_to_en(mydict: dict[str,Any], i18n: I18n) -> dict[str,Any]:
    """Recursively translate a dictionary to english
    
    Used to translate the config file to english.
    The returned dictionary only contains the keys that are in the i18n dictionary if the value is in the dict."""
    d = {}
    for key, value in i18n.i18n.items():
        if value in mydict:
            v = mydict[value]
            if isinstance(v, dict):
                d[key] = translate_json_dict_to_en(v, i18n)
            elif isinstance(v, list):
                if len(v) == 0:
                    d[key] = []
                elif isinstance(v[0], dict):
                    d[key] = [translate_json_dict_to_en(x, i18n) for x in v]
                else:
                    d[key] = v
            else:
                d[key] = mydict[value]
    return d