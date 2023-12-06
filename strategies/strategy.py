from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import List, Union, Type, Optional

import positions
from data.data_requests.data_request import DataRequest
from orders.order import Order
from files import MIDAS_PATH


class Strategy(ABC):
    """
    Used to build strategies

    Parameters
    ----------
    name : str
        The name of the strategy.
        Is not used for anything other than displaying where an 'Order' was created.

    Attributes
    ----------
    get_next_run_time : datetime or time
        The next time the strategy should be ran.

    Methods
    -------
    run(_market_data: MarketData) -> List[Order]
        Gets buy signals from the strategy.
    get_data_request() -> DataRequest:
        Gets the DataRequest of data needed to run the strategy.

    """
    def __init__(self, name: str):
        self.name = name
        self.dd_lookback: Optional[int] = None
        self.max_dd: Optional[int] = None
        self.npositions: int = 5
        self.data_folder = f'{MIDAS_PATH}/strategies/{self.name}'

    @property
    @abstractmethod
    def next_sell_time(self) -> Union[datetime, time]:
        raise NotImplementedError

    @property
    @abstractmethod
    def next_buy_time(self) -> Union[datetime, time]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_buy_data_request() -> Union[DataRequest, List[DataRequest], None]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_sell_data_request() -> Union[DataRequest, List[DataRequest], None]:
        raise NotImplementedError

    @abstractmethod
    def buy(self, data, tda_account_id: int) -> Union[Order, List[Order], None]:
        raise NotImplementedError

    @abstractmethod
    def sell(self, data, tda_account_id: int) -> Union[Order, List[Order], None]:
        raise NotImplementedError

    def get_close_orders_for_all_positions(self, order_type: Type[Order], tda_account_id: int) -> List[Order]:
        close_orders: List[Order] = []
        for position in positions.get_positions_by_strategy(self, tda_account_id):
            strategy_qty = position.composition[self]
            close_orders.append(order_type(position.symbol, -strategy_qty))

        return close_orders

    def cancel_stop_orders(self, tda_account_id: int):
        for position in positions.get_positions_by_strategy(self, tda_account_id):
            for stop_loss in position.stop_losses:
                if self in stop_loss.composition:
                    position.cancel_stop_loss(stop_loss, tda_account_id)
