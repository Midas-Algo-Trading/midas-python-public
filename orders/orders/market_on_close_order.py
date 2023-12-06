from typing import Union, Optional

from pydantic import PositiveFloat

from orders.order import Order, Duration, Session


class MarketOnCloseOrder(Order):
    """Represents a Market On Close other."""
    def __init__(self, symbol: str, quantity: Union[int, float], stop: Optional[PositiveFloat] = None):
        super().__init__(symbol, quantity, Session.NORMAL, Duration.DAY, stop)

    def __str__(self):
        return f'MOC: {self._Order__get_instruction()} {self.symbol}, qty={round(self.quantity, 2)}'

    def can_merge_with(self, other: Order) -> bool:
        return isinstance(other, MarketOnCloseOrder) and super().can_merge_with(other)

    def to_json(self):
        return super()._build_json('MARKET_ON_CLOSE')
