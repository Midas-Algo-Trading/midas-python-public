from abc import ABC, abstractmethod


class File(ABC):
    data = None

    @staticmethod
    @abstractmethod
    def read():
        """Reads the contents of the file."""
        raise NotImplementedError
