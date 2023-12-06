import json
import os
import shutil
from typing import List

from strategies.strategy_list import strategies
from files import MIDAS_PATH
from utils import t_util


def setup_files_structure():
    # Setup Midas directory
    setup_midas_dir()

    # Setup config file
    setup_config()

    # Setup logs directory
    setup_logs_dir()

    # Setup data directory
    setup_data_dir()

    # Setup other directory
    setup_strategies_dir()


def setup_logs_dir():
    """Creates any required directories for logs for any missing directories."""

    # Create main directory
    ensure_dir_exists('logs')

    # Create sub directories
    sub_directories = ['market_data', 'strategies', 'tda', 'alert', 'strategy_runner', 'midas', 'r_util', 'stock_splits']
    create_sub_directories('logs', sub_directories)

    # Create sub directories for tda
    tda_sub_directories = ['client', 'account']
    create_sub_directories('logs/tda', tda_sub_directories)

    # Create sub directories for strategies
    tda_sub_directories = [strategy.name for strategy in strategies]
    create_sub_directories('logs/strategies', tda_sub_directories)


def setup_data_dir():
    """Creates any required directories for data for any missing directories."""
    ensure_dir_exists('data')

    # Create sub directories
    sub_directories = ['snapshots', 'stocks']
    create_sub_directories('data', sub_directories)

    # Create splits file
    with open(os.path.join(MIDAS_PATH, 'data', 'splits.json'), 'w') as file:
        file.write(json.dumps({'last_split_date': t_util.get_today().strftime('%Y-%m-%d')}))


def setup_strategies_dir():
    """Creates any required directories for data for any missing directories."""
    ensure_dir_exists('strategies')

    # Add strategy names to list to create sub_directories
    sub_directories = []
    for strategy in strategies:
        sub_directories.append(strategy.name)

    # Create sub directories
    create_sub_directories('strategies', sub_directories)


def ensure_dir_exists(directory: str):
    if not os.path.exists(os.path.join(MIDAS_PATH, directory)):
        os.mkdir(f'{MIDAS_PATH}/{directory}')


def create_sub_directories(main_dir: str, sub_dirs_to_make: List[str]):
    for sub_dir in sub_dirs_to_make:
        sub_dir_path = os.path.join(MIDAS_PATH, main_dir, sub_dir)
        if not os.path.exists(sub_dir_path):
            os.mkdir(sub_dir_path)


def setup_midas_dir():
    """Creates the directory for Midas files if the Midas directory does not exist."""
    if not os.path.exists(MIDAS_PATH):
        os.makedirs(MIDAS_PATH)


def setup_config():
    """Creates the config if the config does not exist."""
    config_path = os.path.join(MIDAS_PATH, "config.yml")
    if not os.path.exists(config_path):
        shutil.copy('config.yml', config_path)

