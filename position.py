import json
import os
from typing import List, Optional, Dict, Union

import positions
from direction import Direction
from files import MIDAS_PATH

from orders.orders.stop_order import StopOrder
from tda import tda_client
from utils import t_util


class Position:
    def __init__(self, symbol: str, quantity: int, composition: Dict, fill_price: Union[float, Dict],
                 stop_losses: Optional[List[StopOrder]] = None):
        self.symbol = symbol
        self.quantity = quantity
        self.composition = composition  # Dict[Strategy, int]
        self.fill_prices = {strat: fill_price for strat in composition} if type(fill_price) == float else fill_price
        self.stop_losses = stop_losses or []

    def add(self, composition, fill_price, tda_account_id: int, stop_losses: Optional[List[StopOrder]] = None):
        # Add to composition
        for strategy, qty in list(composition.items()):
            self.composition[strategy] = self.composition.get(strategy, 0) + qty

            if not self.composition[strategy]:
                self.__log_profit_loss(fill_price, strategy)
                del self.composition[strategy]
                del self.fill_prices[strategy]
            else:
                self.fill_prices[strategy] = fill_price

        # Add stop losses
        if stop_losses:
            self.stop_losses.extend(stop_losses)

        self.__handle_delete(tda_account_id)

    def cancel_stop_loss(self, stop_loss, tda_account_id: int):
        self.stop_losses.remove(stop_loss)
        if stop_loss.id:
            tda_client.cancel_order(stop_loss.id, tda_account_id)

    def __handle_delete(self, tda_account_id: int):
        should_delete = (not self.composition) and (not self.stop_losses)
        if should_delete:
            positions.positions[tda_account_id].remove(self)

    @property
    def direction(self) -> Direction:
        if self.quantity > 0:
            return Direction.LONG
        elif self.quantity < 0:
            return Direction.SHORT
        else:
            return Direction.FLAT

    def update(self, tda_account_id: int):
        """Updates the position by checking if the stoplosses were filled."""
        for stop_loss in self.stop_losses.copy():
            # Skip stop loss if the stop loss was not sent to TD
            if not stop_loss.id:
                continue

            stop_loss_tda = tda_client.get_order(stop_loss.id, tda_account_id)
            filled_qty = stop_loss_tda['filledQuantity']
            fill_price = stop_loss_tda["orderActivityCollection"]["executionLegs"]["price"]

            if not filled_qty:
                continue

            if self.direction == Direction.SHORT:
                filled_qty *= -1

            # Subtract the filled_qty from the position's quantity
            if self.quantity > 0:
                # Update position quantity
                self.quantity -= filled_qty

                # Update the position composition and fill prices
                self.add(stop_loss.composition, fill_price, tda_account_id)

            # If the stop loss was completely filled, remove it
            remaining_qty = stop_loss_tda['remainingQuantity']
            if not remaining_qty:
                self.stop_losses.remove(stop_loss)

            # If the position's quantity is now 0, remove the position
            if not self.quantity:
                positions.positions.remove(self)

    def get_save_format(self) -> Dict:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'composition': {strategy.name: qty for strategy, qty in self.composition.items()},
            'fill_prices': {strategy.name: price for strategy, price in self.fill_prices.items()},
            'stop_losses': [stop_loss.get_save_format() for stop_loss in self.stop_losses]
        }

    def __log_profit_loss(self, close_price: float, strategy):
        pl_path = f'{MIDAS_PATH}/strategies/{strategy.name}/pl.json'

        # Get the strategy pls
        if os.path.isfile(pl_path):
            with open(pl_path, 'r') as file:
                strategy_pls = json.load(file)
        else:
            strategy_pls = dict()

        # Add this trade pl to strategy pls
        open_price = self.fill_prices[strategy]
        pl = round(((close_price - open_price) / open_price) * 100, 2)
        today = str(t_util.get_today())
        strategy_pls[today] = strategy_pls.get(today, []) + [pl]

        # Write back to file
        with open(pl_path, 'w') as file:
            json.dump(strategy_pls, file)
