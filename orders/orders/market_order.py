from typing import Union, Optional

from pydantic import PositiveFloat

from orders.order import Order, Session, Duration


class MarketOrder(Order):
    """
    Represents a market other.

    Methods
    -------
    can_merge_with(other: Order) -> bool
        Returns whether 'other' can be combined with this.
        'other' must be a 'MarketOrder', and the base orders can be combined.

    """
    def __init__(self, symbol: str, quantity: Union[int, float], stop: Optional[PositiveFloat] = None):
        super().__init__(symbol, quantity, Session.NORMAL, Duration.DAY, stop)

    def __str__(self):
        return f'MKT: {self._Order__get_instruction()} {self.symbol}, qty={round(self.quantity, 2)}'

    def can_merge_with(self, other: Order) -> bool:
        return isinstance(other, MarketOrder) and super().can_merge_with(other)

    def to_json(self):
        return super()._build_json('MARKET')
