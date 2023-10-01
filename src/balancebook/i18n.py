# Small i18n module for PyBalanceBook
# Mainly intended for French and English
# Used so the user can have the csv files in his own language
import json
from string import Template

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
        if self.i18n is None or key not in self.i18n:
            return key
        return self.i18n[key]
    
    def __contains__(self, key: str) -> bool:
        if self.i18n is None:
            return True
        return key in self.i18n
    
    def translate(self, key: str, **kwargs) -> str:
        """Translate a key"""
        if self.i18n is None or key not in self.i18n:
            return Template(key).safe_substitute(**kwargs)
        
        if key not in self.i18n:
            raise KeyError(f"Key {key} not found in i18n dictionary")
        
        return Template(self.i18n[key]).safe_substitute(**kwargs)
    
    def t(self, key: str, **kwargs) -> str:
        """Translate a key"""
        return self.translate(key, **kwargs)

# Load a i18n dictionary from a json file
def load_i18n_from_json(path: str) -> I18n:
    """Load a i18n dictionary from a json file"""
    with open(path, encoding="utf-8") as f:
        return I18n(json.load(f))

# Default english i18n
i18n_en = I18n()

# The i18n object used by the library
i18n = i18n_en