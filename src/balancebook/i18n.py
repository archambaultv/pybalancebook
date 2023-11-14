# Small i18n module for Balancebook

# Used so the user can have the csv and config files in his own language
import json
import yaml
import os
import logging
from typing import Any
from string import Template

import balancebook.errors as bberr


logger = logging.getLogger(__name__)

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
        if self.i18n is None:
            return key
        elif key not in self.i18n:
            logger.debug(f"Translation not found for '{key}'")
            return key
        return self.i18n[key]
    
    def translate(self, key: str, **kwargs) -> str:
        """Translate a string with keyword arguments"""
        if self.i18n is None:
            return Template(key).safe_substitute(**kwargs)
        elif key not in self.i18n:
            logger.debug(f"Translation not found for '{key}'")
            return Template(key).safe_substitute(**kwargs)
        else:
            return Template(self.i18n[key]).safe_substitute(**kwargs)
    
    def t(self, key: str, **kwargs) -> str:
        """Translate a string with keyword arguments"""
        return self.translate(key, **kwargs)
    
    def is_default(self) -> bool:
        """Check if the i18n dictionary is the default one"""
        return self.i18n is None

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