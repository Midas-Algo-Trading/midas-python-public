from datetime import datetime, time, timedelta
from typing import Type, Union, List, Optional, Dict, Any

import alert
import positions
import schedule
from data import live_data
from direction import Direction

from orders.order import Order
from orders.orders.limit_order import LimitOrder
from orders.orders.market_on_close_order import MarketOnCloseOrder
from orders.orders.market_order import MarketOrder
from . import order_pool
from tda import tda_client
from utils import t_util


def check_order(order, tda_account_id: int, tda_order_details: Optional[Dict[str, Any]] = None, send_anew: bool = False) -> bool:
    """
    returns
    -------
    True if the order was fully filled.
    False if the order was not filled or partially filled.
    """
    if not tda_order_details:
        try:
            tda_order_details = tda_client.get_order(order.id, tda_account_id)
        except:
            print('error', order.__dict__)
            return False

    # Check if cancelled
    if tda_order_details['status'] == 'CANCELED':
        alert.alert(f'Cancelled: {str(order)}. ({order.id})')
        order_pool.remove(order, tda_account_id)
        return False

    # Get the quantity filled
    filled_qty = int(tda_order_details['filledQuantity'])
    if order.direction == Direction.SHORT:
        filled_qty *= -1

    # Total fill...
    if filled_qty == order.quantity:
        # Update current price
        order.current_price = tda_order_details["orderActivityCollection"][0]["executionLegs"][0]["price"]

        # Register position
        positions.register(order.symbol, filled_qty, order.composition, order.current_price, tda_account_id, order.stop_losses)

        # Remove from order pool
        order_pool.remove(order, tda_account_id)

        # If child order, schedule fill check
        if order.child_order:
            schedule.add(get_check_time(type(order.child_order)), check_order, order.child_order, tda_account_id)

        return True

    # Partial fill...
    elif filled_qty != 0:
        # Adjust the order for the partial fill

        order.quantity -= filled_qty

        # Adjust the composition
        filled_composition = order.split_composition(filled_qty)

        # Update current price
        order.current_price = tda_order_details["orderActivityCollection"][0]["executionLegs"][0]["price"]

        # Register position
        positions.register(order.symbol, filled_qty, filled_composition, order.current_price, tda_account_id)

        # Increment fill try
        order.fill_tries += 1

    # Schedule check again
    schedule.add(get_check_time(type(order)), check_order, order, tda_account_id, None, send_anew)

    # Resend order if send_anew
    if send_anew:
        stock_market_price = live_data.get_market_prices([order.symbol], tda_account_id)[order.symbol]
        if order.price == order.current_price and stock_market_price != order.current_price:
            order.price, order.current_price = stock_market_price, stock_market_price
            tda_client.cancel_order(order.id)
            tda_client.place_orders([order], tda_account_id, tda_account_id)

    # Increment fill try
    order.fill_tries += 1
    # If this the fifth fill try, give up
    if order.fill_tries == 5:
        tda_client.cancel_order(order.id, tda_account_id)
        alert.alert(f'Unfilled & cancelled: {str(order)}. ({order.id})')
        order_pool.remove(order, tda_account_id)

    return False


def check_orders(orders: List[Order], tda_account_id: int):
    # Check unsent orders
    unsent_orders = [order for order in orders if not order.quantity]
    check_unsent_orders(unsent_orders, tda_account_id)

    # Check sent orders
    sent_orders = [order for order in orders if order.quantity]
    check_sent_orders(sent_orders, tda_account_id)


def check_sent_orders(orders: List[Order], tda_account_id: int):
    tda_orders_details = tda_client.get_orders(tda_account_id, t_util.get_today())
    filled_orders: List[Order] = []
    for order in orders:
        # If the order is no longer in the order pool it was filled by another check.
        if order not in order_pool.__order_pool[tda_account_id]:
            continue

        send_anew = True if isinstance(order, LimitOrder) else False

        for tda_order_details in tda_orders_details:
            if tda_order_details['orderId'] == order.id:
                order_filled = check_order(order, tda_account_id, tda_order_details, send_anew)
                if order_filled:
                    filled_orders.append(order)
                break
        else:
            check_order(order, tda_account_id, dict(), send_anew)

    __send_filled_orders_stop_losses(filled_orders, tda_account_id)


def check_unsent_orders(orders: List[Order], tda_account_id: int):
    orders_symbols = [order.symbol for order in orders]
    market_prices = live_data.get_market_prices(orders_symbols, tda_account_id)
    for order in orders:
        # Register position
        positions.register(order.symbol, 0, order.composition, market_prices.get(order.symbol, order.current_price), tda_account_id, order.stop_losses)
        # Remove from order pool
        order_pool.remove(order, tda_account_id)


def __send_filled_orders_stop_losses(filled_orders: List[Order], tda_account_id: int):
    # Only send stop losses from orders if the position is short
    filled_orders_for_short_positions = [order for order in filled_orders if (position := positions.get_by_symbol(order.symbol, tda_account_id)) and position.direction == Direction.SHORT]
    # Only send stop losses from order s that have a quantity
    filled_qty_orders_for_short_positions = [order for order in filled_orders_for_short_positions if order.quantity]
    # Get the stop losses from valid orders
    valid_stop_losses = [stop_loss for order in filled_qty_orders_for_short_positions for stop_loss in order.stop_losses]
    # Send stop losses
    tda_client.place_orders(valid_stop_losses, tda_account_id)

    # Update positions with stop losses
    for order in filled_orders:
        for stop_loss in order.stop_losses:
            positions.get_by_symbol(order.symbol).stop_losses.append(stop_loss)


def get_check_time(order_type: Type[Order]) -> Union[datetime, time]:
    if order_type == MarketOrder:
        check_time = max(t_util.get_current_datetime() + timedelta(minutes=2),
                         t_util.get_current_datetime().replace(hour=9, minute=32))
        if check_time.time() < time(hour=16):
            return check_time
        else:
            return datetime.combine(t_util.add_to_mkt_date(1), time(9, 32))
    elif order_type == MarketOnCloseOrder:
        return time(16, 2)
    elif order_type == LimitOrder:
        return t_util.get_current_datetime() + timedelta(minutes=1)


def schedule_checks(orders: List[Order], tda_account_id: int):
    # Split orders by check times
    check_time_2_orders: Dict[Union[datetime, time], List[Order]] = dict()
    for order in orders:  # Only want to check orders that had a quantity
        check_time = get_check_time(type(order))
        check_time_2_orders[check_time] = check_time_2_orders.get(check_time, []) + [order]

    # Schedule order fill checks
    for check_time, orders in check_time_2_orders.items():
        schedule.add(check_time, check_orders, orders, tda_account_id)
