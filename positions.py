import json
import os
from typing import List, Dict, Optional

import alert
from direction import Direction
from files import MIDAS_PATH
from orders.orders.stop_order import StopOrder
from position import Position
from strategies import strategy_list
from tda import tda_client

positions_file_path = {0: f'{MIDAS_PATH}/positions_0.json', 1: f'{MIDAS_PATH}/positions_1.json'}
positions = {0: [], 1: []}


def update(tda_account_id: int):
    # Update positions
    for position in positions[tda_account_id]:
        position.update(tda_account_id)

    # Get positions from TDA
    tda_positions = tda_client.get_positions(tda_account_id)

    for position in positions[tda_account_id].copy():
        # The position is not in TDA...
        if position.symbol not in tda_positions:
            if position.direction != Direction.FLAT:
                alert.alert(f'Unaccounted for position: {position.symbol!r}')
            continue

        # The position's quantity does not match TDA...
        if position.quantity != tda_positions[position.symbol]:
            alert.alert(f'Unexpected position quantity in {position.symbol!r}. Expected: {position.quantity!r} actual: {tda_positions[position.symbol]!r}')

        # Remove TDA position1 since it has been checked
        del tda_positions[position.symbol]

    # There are positions in TDA that are not registered in positions...
    if tda_positions:
        alert.alert(f'Unregistered position in TDA: {tda_positions!r}')


def get_by_symbol(symbol: str, tda_account_id: int):  # -> Optional[Position]
    for position in positions[tda_account_id]:
        if position.symbol == symbol:
            return position


def register(symbol: str, quantity: int, composition: Dict, fill_price: float, tda_account_id: int, stop_losses: Optional[List[StopOrder]] = None):
    # Get the position for the stock
    position = get_by_symbol(symbol, tda_account_id)

    # If the position exists... add to it
    if position:
        position.add(composition, fill_price, stop_losses)

    # If the position does not exist... create it
    else:
        position = Position(symbol, quantity, composition, fill_price, stop_losses)
        positions[tda_account_id].append(position)

    # Save to file
    save(tda_account_id)


def save(tda_account_id: int):
    with open(positions_file_path[tda_account_id], 'w') as file:
        json.dump([position.get_save_format() for position in positions[tda_account_id]], file)


def load(tda_account_id: int):
    # No positions have been saved...
    if not os.path.exists(positions_file_path[tda_account_id]):
        return

    with open(positions_file_path[tda_account_id], 'r') as file:
        file_contents = json.load(file)

    for position_data in file_contents:
        p_symbol = position_data['symbol']
        p_quantity = position_data['quantity']
        p_composition = {strategy_list.get_by_name(strat_name): qty for strat_name, qty in position_data['composition'].items()}
        p_fill_prices = {strategy_list.get_by_name(strat_name): price for strat_name, price in position_data['fill_prices'].items()}

        # Load stop losses
        p_stop_losses: List[StopOrder] = []
        for stop_loss_data in position_data['stop_losses']:
            sl_symbol = stop_loss_data['symbol']
            sl_quantity = stop_loss_data['quantity']
            sl_stop_price = stop_loss_data['stop_price']
            sl_id = stop_loss_data['id']
            sl_composition = {strategy_list.get_by_name(strat_name): qty for strat_name, qty in stop_loss_data['composition'].items()}

            stop_loss = StopOrder(sl_symbol, sl_quantity, sl_stop_price)
            stop_loss.id = sl_id
            stop_loss.composition = sl_composition

            p_stop_losses.append(stop_loss)

        position = Position(p_symbol, p_quantity, p_composition, p_fill_prices, p_stop_losses)
        positions[tda_account_id].append(position)

    update(tda_account_id)


def get_positions_by_strategy(strategy, tda_account_id: int) -> List[Optional[Position]]:
    strategy_positions: List[Position] = []
    for position in positions[tda_account_id]:
        if strategy in position.composition:
            strategy_positions.append(position)
    return strategy_positions
