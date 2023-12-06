from abc import ABC, abstractmethod
from typing import Union, Optional
from pydantic.types import PositiveFloat

from orders.order_properties import Session, PositionEffect, Duration
from direction import Direction


class Order(ABC):
    """
    Orders are used to send orders to text or market.
    Used to build other orders.

    Parameters
    ----------
    symbol : str
        Symbol of the stock the other will trade.
    quantity : int
        Number of shares to trade.

    Methods
    -------
    can_merge_with(other: Order) -> bool
        Returns whether 'other' can be combined with this.
        'other' must have the same direction and symbol as this.
    merge_with(other: Order):
        Used to combine two orders.
        Adds 'other''s quantity and strategy to this.

    """
    def __init__(
            self,
            symbol: str,
            quantity: Union[int, float],
            session: Session,
            duration: Duration,
            stop: Optional[PositiveFloat] = None,
            position_effect: Optional[PositionEffect] = None
    ):
        self.symbol = symbol
        self.quantity = quantity
        self.session = session
        self.duration = duration
        self.stop = stop

        self.position_effect: Optional[PositionEffect] = position_effect
        self.child_order: Optional[Order] = None
        self.stop_losses = []  # List[StopOrder]
        self.id: int = 0
        self.current_price: float = 0
        self.composition = dict()  # Dict[Strategy, int]
        self.parent_order: Optional[Order] = None
        self.fill_tries = 0

    def can_merge_with(self, other):
        return type(self) == type(other) and other.symbol == self.symbol

    def merge_with(self, other):
        # If there is a child order, just merge with that
        if self.child_order:
            self.child_order.merge_with(other)
            return

        # If this order does not have a child order...

        old_direction = self.direction

        # Update quantity
        self.quantity += other.quantity

        # Update composition
        for strategy, qty in other.composition.items():
            self_strategy_qty = self.composition.get(strategy, 0)
            self.composition[strategy] = self_strategy_qty + qty

        # Add stop losses
        self.stop_losses.extend(other.stop_losses)

        # If this is a child order and has been flipped, it now equals the parent order's direction so merge back
        # into parent order.
        if self.parent_order and self.direction != old_direction:
            self.parent_order.child_order = None
            self.parent_order.merge_with(self)

    @abstractmethod
    def to_json(self):
        raise NotImplementedError

    def _build_json(self, order_type: str, **kwargs):
        json_order = {
            'orderType': order_type,
            'session': self.session.value,
            'duration': self.duration.value,
            'orderStrategyType': 'SINGLE' if not self.child_order else 'TRIGGER',
            'orderLegCollection': [
                {
                    'instruction': self._Order__get_instruction(),
                    'quantity': abs(self.quantity),
                    'instrument': {
                        'symbol': self.symbol,
                        'assetType': 'EQUITY'
                    }
                }
            ]
        }

        # Linked order
        if self.child_order:
            json_order['childOrderStrategies'] = [self.child_order.to_json()]

        # Stop losses are sent after order is filled

        # Additional JSON args
        json_order.update(kwargs)

        return json_order

    def __get_instruction(self) -> str:
        if self.quantity > 0:
            if self.position_effect == PositionEffect.OPEN:
                return 'BUY'
            else:
                return 'BUY_TO_COVER'
        else:
            if self.position_effect == PositionEffect.OPEN:
                return 'SELL_SHORT'
            else:
                return 'SELL'

    @property
    def direction(self) -> Direction:
        if self.quantity > 0:
            return Direction.LONG
        elif self.quantity < 0:
            return Direction.SHORT
        else:
            return Direction.FLAT

    def merge_into_parent(self):
        self.parent_order.child_order = None
        self.parent_order.merge_with(self)

    def split_composition(self, new_composition_qty: int):  # -> Dict[Strategy, float]
        new_composition = dict()
        for strategy, strategy_qty in list(self.composition.items()):
            strategy_qty_sacrifice = min(strategy_qty, new_composition_qty)

            self.composition[strategy] = strategy_qty - strategy_qty_sacrifice
            # If the strategy's value is now 0, remove it
            if not self.composition[strategy]:
                self.composition.pop(strategy)

            new_composition[strategy] = strategy_qty_sacrifice

            new_composition_qty -= strategy_qty_sacrifice
            if new_composition_qty == 0:
                break

        return new_composition
