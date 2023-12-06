import asyncio
import copy
from typing import List, Callable, Dict

import portfolio_manager
import positions
import schedule
import stock_split_tracker
from data import market_data, live_data
from direction import Direction
from logger import dlog, log
from orders import order_pool, order_fill_checker
from orders.orders.market_order import MarketOrder

from orders.order import Order, PositionEffect
from orders.orders.stop_order import StopOrder
from strategies import strategy_list
from tda import tda_client
from utils import dreqst_util


@dlog('strategy_runner', 'Running funcs: @0')
def run(funcs: List[Callable], update_schedule: bool):
    run_for_tda_account(funcs, update_schedule, get_next_tda_account_id())
    run_for_tda_account(funcs, update_schedule, get_next_tda_account_id())


last_tda_account_id: int = 1


def get_next_tda_account_id() -> int:
    global last_tda_account_id
    new_tda_account_id = 1 if last_tda_account_id == 0 else 0
    last_tda_account_id = new_tda_account_id
    return new_tda_account_id


def run_for_tda_account(funcs: List[Callable], update_schedule: bool, tda_account_id: int):
    """Performs all actions to run each strategy in 'strategies'."""

    # Load live market data.
    asyncio.run(market_data.load_live_data(dreqst_util.get_data_requests(funcs)))

    # Update positions.
    positions.update(tda_account_id)

    # Get orders by running the strategies.
    orders = get_orders(funcs, tda_account_id)

    # Filter stock splits.
    filter_split_stocks(orders)

    # Create orders' stop losses.
    create_orders_stop_losses(orders)

    # Set the orders' current prices.
    set_current_prices(orders, tda_account_id)

    # Set the proper quantity for each order.
    portfolio_manager.allocate_to_orders(orders, tda_account_id)

    # Log strategy orders
    log_strategy_orders(orders)

    # Add orders to pool.
    orders = order_pool.add_orders(orders, tda_account_id)

    # Update stop losses based on positions.
    update_stop_losses_by_positions(orders, tda_account_id)

    log('strategy_runner', str([str(position) for position in positions.positions[tda_account_id]]))
    log_strategy_orders(orders)

    # Update orders based on positions.
    update_orders_by_positions(orders, tda_account_id)

    # Send orders
    send_orders(orders, tda_account_id)

    # Add back to schedule.
    if update_schedule:
        reschedule_strategies(funcs)


def log_strategy_orders(orders: List[Order]):
    # Get strategy to orders
    strategy_2_orders: Dict[str, List[Order]] = dict()
    for order in orders:
        strategy_name = list(order.composition)[0].name
        strategy_2_orders[strategy_name] = strategy_2_orders.get(strategy_name, []) + [order]

    # Create well-formatted strategy to orders string
    strategy_2_orders_str = 'Strategy orders:'
    for strategy_name, strategy_orders in strategy_2_orders.items():
        strategy_2_orders_str += f'\n                     {strategy_name}:'
        for order in strategy_orders:
            strategy_2_orders_str += f'\n                     -{str(order)}'

    log('strategy_runner', strategy_2_orders_str)


def send_orders(orders: List[Order], tda_account_id: int):
    # Place orders with a quantity
    orders_with_quantity = [order for order in orders if order.quantity]
    tda_client.place_orders(orders_with_quantity, tda_account_id)
    # Schedule fill checks for sent orders
    order_fill_checker.schedule_checks(orders, tda_account_id)


def reschedule_strategies(funcs):
    for func in funcs:
        func_strategy = func.__self__.__class__()
        if func.__name__ == 'buy':
            func_next_run_time = func_strategy.next_buy_time
        else:
            func_next_run_time = func_strategy.next_sell_time
        schedule.add(func_next_run_time, func)


def update_orders_by_positions(orders: List[Order], tda_account_id: int):
    for order in orders:
        position = positions.get_by_symbol(order.symbol, tda_account_id)

        # If no position exists... the order will open a new position
        if not position or position.direction == Direction.FLAT:
            order.position_effect = PositionEffect.OPEN

        # A positions already exists...
        else:
            # Get new position direction
            new_position_qty = position.quantity + order.quantity
            new_position_direction = Direction.LONG if new_position_qty > 0 else Direction.SHORT if new_position_qty < 0 else Direction.FLAT

            # The order is attempting to close the position
            if new_position_direction == Direction.FLAT:
                order.position_effect = PositionEffect.CLOSE

            # Order is not attempting to flip the position
            elif new_position_direction == position.direction:

                # The order is attempting to increase to the position quantity
                if abs(new_position_qty) > abs(position.quantity):
                    # You set the positionEffect to OPEN to change a position's quantity
                    order.position_effect = PositionEffect.OPEN

                # The order is attempting to decrease the position quantity
                else:
                    # You set the positionEffect to OPEN change a position's quantity
                    order.position_effect = PositionEffect.CLOSE

            # The order is attempting to flip the position
            # Split the order to make the original order close the position and a new order to open a new position
            else:
                # Create the new (child) order
                new_order = copy.deepcopy(order)
                new_order.position_effect = PositionEffect.OPEN
                new_order.quantity = order.quantity + position.quantity

                # Refactor order
                order.position_effect = PositionEffect.CLOSE
                order.quantity -= new_order.quantity
                order.stop_losses = []

                # Refactor composition
                split_composition = order.split_composition(new_order.quantity)
                new_order.composition = split_composition

                # Set relationships
                new_order.parent_order = order
                order.child_order = new_order


def update_stop_losses_by_positions(orders: List[Order], tda_account_id: int):
    for order in orders:
        position = positions.get_by_symbol(order.symbol, tda_account_id)

        # Get the new position quantity
        new_position_qty = order.quantity + position.quantity if position else order.quantity

        # Merge any stop losses' child order back into the parent stop order
        for stop_loss in order.stop_losses:
            if stop_loss.child_order:
                stop_loss.child_order.merge_into_parent()

        # Reorder the stop losses from least risky to most risky
        order.stop_losses.sort(key=lambda sl: sl.stop_price)

        for stop_loss in order.stop_losses:
            qty_sacrifice_to_close_position = min(stop_loss.quantity, -new_position_qty)

            # If all of stop_loss's quantity can be used for closing the position...
            if qty_sacrifice_to_close_position == stop_loss.quantity:
                stop_loss.position_effect = PositionEffect.CLOSE

            # If some of the stop_loss's quantity can be be used for closing...
            elif new_position_qty:
                # Create the new (child) order
                new_order = MarketOrder(symbol=stop_loss.symbol, quantity=stop_loss.quantity + new_position_qty)
                new_order.position_effect = PositionEffect.OPEN

                # Refactor self
                stop_loss.position_effect = PositionEffect.CLOSE
                stop_loss.quantity = qty_sacrifice_to_close_position

                # Refactor composition
                new_composition = stop_loss.split_composition(new_order.quantity)
                new_order.composition = new_composition

                # Set relationships
                new_order.parent_order = stop_loss
                stop_loss.child_order = new_order

            # The rest of the stop losses will be opening a position
            else:
                stop_loss.position_effect = PositionEffect.OPEN

            new_position_qty += qty_sacrifice_to_close_position


def create_orders_stop_losses(orders: List[Order]):
    for order in orders:
        if not order.stop:
            continue

        # Create stop loss order
        stop_price = round(order.current_price + (order.stop * order.current_price), 2)
        stop_loss_order = StopOrder(order.symbol, -order.quantity, stop_price)
        stop_loss_order.composition = {strat: -qty for strat, qty in order.composition.items()}

        # Add stop loss order
        order.stop_losses.append(stop_loss_order)


def set_current_prices(orders: List[Order], tda_account_id: int):
    orders_symbols = {order.symbol for order in orders}
    symbols_current_prices = live_data.get_market_prices(orders_symbols, tda_account_id)

    for order in orders.copy():
        order_symbol_current_price = symbols_current_prices.get(order.symbol, None)
        if order_symbol_current_price:
            order.current_price = order_symbol_current_price
        else:
            orders.remove(order)


def filter_split_stocks(orders: List[Order]):
    splitting_stocks = stock_split_tracker.get_splitting_stocks()
    for order in orders.copy():
        if order.symbol in splitting_stocks:
            orders.remove(order)


def get_orders(funcs: List[Callable], tda_account_id: int) -> List[Order]:
    """Runs each strategy and returns all the cumulative orders // Store orders in folders"""
    orders = []
    for func in funcs:
        strategy = strategy_list.get_by_name(func.__self__.__class__().name)

        # Get the orders from the strategy
        if func.__name__ == 'buy':
            strategy_orders = func(market_data.get(strategy.get_buy_data_request()), tda_account_id)
        else:
            strategy_orders = func(market_data.get(strategy.get_sell_data_request()), tda_account_id)

        # Ensure strategy_orders is a list
        if isinstance(strategy_orders, Order):
            strategy_orders = [strategy_orders]

        # Set the order composition
        for order in strategy_orders:
            order.composition = {strategy: order.quantity}

        orders.extend(strategy_orders)

    return orders
