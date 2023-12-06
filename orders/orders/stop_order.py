from typing import Union, Dict

from orders.order import Order
from orders.order_properties import Session, Duration


class StopOrder(Order):
    def __init__(self, symbol: str, quantity: Union[int, float], stop_price: float):
        super().__init__(symbol, quantity, Session.NORMAL, Duration.GOOD_TILL_CANCEL)
        self.stop_price = stop_price

    def to_json(self):
        return super()._build_json('STOP', stopPrice=self.stop_price)

    def can_merge_with(self, other):
        return self.stop_price == other.stop_price and super().can_merge_with(other)

    def __str__(self):
        return f'MKT: {self._Order__get_instruction()} {self.symbol}, qty={round(self.quantity, 2)}, stop_price={self.stop_price}'

    def get_save_format(self) -> Dict:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'stop_price': self.stop_price,
            'id': self.id,
            'composition': {strategy.name: qty for strategy, qty in self.composition.items()}
        }
