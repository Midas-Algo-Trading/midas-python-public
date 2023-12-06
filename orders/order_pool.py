from typing import List, Optional, Dict

from orders.order import Order
from tda import tda_client

__order_pool: Dict[int, List[Order]] = {0: [], 1: []}


def add_order(order: Order, tda_account_id: int) -> Optional[Order]:
    """
    Adds an order to the order pool

    returns
    -------
    The resulting order
    """
    for pool_order in __order_pool[tda_account_id]:
        if order.can_merge_with(pool_order):
            pool_order.merge_with(order)

            if pool_order.id:
                tda_client.cancel_order(pool_order.id, tda_account_id)

            return pool_order

    # If order could not merge with any pool orders...
    __order_pool[tda_account_id].append(order)
    return order


def add_orders(orders: List[Order], tda_account_id: int) -> List[Order]:
    return list(set(order_ for order in orders if (order_ := add_order(order, tda_account_id))))


def remove(order: Order, tda_account_id: int):
    __order_pool[tda_account_id].remove(order)


def get_order_by_symbol(symbol: str, tda_account_id: int) -> Order or None:
    for order in __order_pool[tda_account_id]:
        # If the order exists, return the order, otherwise return None
        if order.symbol == symbol:
            return order
    return None
