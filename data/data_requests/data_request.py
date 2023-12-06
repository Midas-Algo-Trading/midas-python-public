from abc import ABC, abstractmethod
from typing import List


class DataRequest(ABC):
    """
    Used to communicate between 'MarketData' and strategies to request and retrieve data.

    Parameters
    ----------
    columns : List[str]
        Data columns that will be retrieved from MarketData requests.
        Can contain the following values:

        - 'open': The first listed price of a stock.
        - 'high': The highest price achieved by a stock.
        - 'low': The lowest price achieved by a stock.
        -'close': The last listed price of a stock.
        -'volume': The number of shares traded of a stock.
    round_to : int
        The decimal func returned data will be rounded to.

    """
    def __init__(self,
                 columns: List[str],
                 round_to: int):
        self.columns = columns
        self.round_to = round_to

    def __hash__(self):
        return hash(str(self))

    @abstractmethod
    def can_merge_with(self, data_request) -> bool:
        raise NotImplementedError

    def __str__(self):
        return str(self.__dict__)
