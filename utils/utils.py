from typing import Dict, Any

import pandas as pd

"""For generic utility functions."""


def flatten_dict(dict_: Dict, parent_key: str = '', sep: str = '.') -> Dict[Any, Any]:
    items = []
    for key, value in dict_.items():
        new_key = parent_key + sep + key if parent_key else key
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    return dict(items)


def pct_chg(from_: pd.Series, to: pd.Series):
    return (to - from_) / from_