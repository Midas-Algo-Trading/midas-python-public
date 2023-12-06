import yaml
import platform

from files.file import File
from files import MIDAS_PATH
from utils import utils


class Config(File):
    """
    Stores data from the config file.

    Methods
    -------
    read :
        Reads the contents of the config file and stores it.
    get : str
        Returns the func of the key in the config.

    Notes
    -----
    Child items are separated by a period from the parent.

    """
    @staticmethod
    def read():
        # Check the OS and create the correct file path
        path = ''
        if platform.system() == "Windows":
            path = f'{MIDAS_PATH}\config.yml'
        if platform.system() == "Darwin":
            path = f'{MIDAS_PATH}/config.yml'
        if platform.system() == "Linux":
            path = f'{MIDAS_PATH}/config.yml'

        with open(path, 'r') as file:
            Config.data = utils.flatten_dict(yaml.load(file, Loader=yaml.loader.SafeLoader))

    @staticmethod
    def get(key: str):
        return Config.data[key]
