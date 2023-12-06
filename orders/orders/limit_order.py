from typing import Union, Optional

from pydantic.types import PositiveFloat

from orders.order import Order, Session, Duration, PositionEffect


class LimitOrder(Order):
    def __init__(self,
                 symbol: str,
                 quantity: Union[int, float],
                 price: float,
                 session: Session,
                 duration: Duration,
                 stop: Optional[PositiveFloat] = None,
                 position_effect: Optional[PositionEffect] = None):
        super().__init__(symbol, quantity, session, duration, stop, position_effect)
        self.price = price

    def to_json(self):
        return super()._build_json('LIMIT', price=str(self.price))

    def can_merge_with(self, other: Order) -> bool:
        return isinstance(other, LimitOrder) and other.price == self.price and super().can_merge_with(other)

    def __str__(self):
        return f'MOC: {self._Order__get_instruction()} {self.symbol}, price={self.price}, qty={round(self.quantity, 2)}'
