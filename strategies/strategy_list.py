import importlib
import os
from typing import List

from strategies.strategy import Strategy

__non_strategy_files = ['strategy_list.py', 'strategy.py', 'midas_path.py']

strategies: List[Strategy] = []  # List of all strategies

# Load strategies
for py_file in os.listdir('strategies'):
    if py_file.endswith('.py') and py_file not in __non_strategy_files:
        module = importlib.import_module(f'strategies.{py_file[:-3]}')
        class_instance = module.Strategy()
        strategies.append(class_instance)


def get_by_name(name: str) -> Strategy:
    for strategy in strategies:
        if strategy.name == name:
            return strategy

    raise ValueError(f'{name!r} is not a strategy name')
