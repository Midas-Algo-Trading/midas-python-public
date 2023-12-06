import json
from datetime import date, datetime
from typing import List, Dict, Iterable, Tuple

import numpy as np
from numpy import mean

from files import MIDAS_PATH
from files.config import Config
from orders.order import Order
from strategies import strategy_list
from strategies.strategy import Strategy
from tda import tda_client
from utils import t_util


def allocate_to_orders(orders: List[Order], tda_account_id: int):
    """
    Sets a share quantity to each other.

    Notes
    -----
    If a other's quantity is set to 0, it is removed.
    If any strategies have no remaining orders, the strategy will be removed.
    """

    # If port is in drawdown, all orders will have a quantity of 0
    if midas_in_dd()[0]:
        for order in orders:
            order.quantity = 0
        return

    # Get the strategies allocations
    strategies = set()
    for order in orders:
        strategies.update(order.composition)

    if Config.get('strategy_allocations.adjust_to_use_all_capital'):
        strategies_allocations = get_adj_strategies_allocations(strategies, 0)
    else:
        strategies_allocations = get_strategies_allocations(strategies, 0)
    strategies_allocations = strategies_allocations[list(strategies_allocations.keys())[-1]]

    for order in orders:
        for strategy, qty in list(order.composition.items()):
            # The other is relying on the portfolio manager to allocate a quantity to it
            if type(order.quantity) == float:
                # Get the allocation of the strategy
                strategy_allocation = strategies_allocations[strategy]
                if type(strategy_allocation) == np.float64:
                    strategy_allocation *= tda_client.get_account(tda_account_id).buying_power_non_marginableTrade

                # Allocate the right quantity
                strategy_order_allocation = order.quantity * strategy_allocation
                order.composition[strategy] = int(strategy_order_allocation / order.current_price)

            # The strategy has set a specific quantity
            else:
                order.composition[strategy] = qty

        # Set the order quantity
        order.quantity = sum(order.composition.values())


def get_trade(strategy: Strategy, start: date) -> Dict[date, float]:
    strategy_pl_path = f'{MIDAS_PATH}/strategies/{strategy.name}/pl.json'
    with open(strategy_pl_path, 'r') as file:
        trade_pls: Dict[str, List[float]] = json.load(file)
    return {day_: mean([trade_pl for trade_pl in trade_pls if -50 < trade_pl <= 100]) for day, trade_pls in trade_pls.items()
            if (day_ := datetime.strptime(day, '%Y-%m-%d').date()) >= start}


def is_in_drawdown(strategy: Strategy, lookback: int, trades=None) -> Dict[date, Tuple[bool, float]]:
    if not trades:
        trades = get_trade(strategy, t_util.add_to_mkt_date(-(strategy.dd_lookback + lookback)))
    days = list(trades.keys())
    pls = np.asarray(list(trades.values()))
    in_dds = dict()
    for i, day in enumerate(days[strategy.dd_lookback-1:]):
        this_pls = np.cumsum(pls[i:i+strategy.dd_lookback])
        this_pls_cummax = np.maximum.accumulate(this_pls)
        dd = abs(this_pls[-1] - this_pls_cummax[-1])
        in_dds[day] = (dd >= 2, dd)
    return in_dds


def get_strategies_allocations(strategies: Iterable[Strategy], lookback: int, trades=None) -> Dict[date, Dict[Strategy, float]]:
    strategies_allocations = dict()
    for strategy in strategies:
        drawdowns = is_in_drawdown(strategy, lookback, trades[strategy] if trades else None)
        for day in drawdowns:
            allocations = strategies_allocations.get(day, dict())
            allocations.update({strategy: Config.get(f'strategy_allocations.{strategy.name}') if not drawdowns[day][0] else 0})
            strategies_allocations[day] = allocations

    return strategies_allocations


def get_adj_strategies_allocations(strategies: Iterable[Strategy], lookback: int, trades=None) -> Dict[date, Dict[Strategy, float]]:
    raw_strategy_allocations = {strategy: Config.get(f'strategy_allocations.{strategy.name}')for strategy in strategies}
    total_allocation = sum(raw_strategy_allocations.values())
    strategy_allocations = get_strategies_allocations(strategies, lookback, trades)
    day_total_allocations = {date: sum(strat_allocs.values()) for date, strat_allocs in strategy_allocations.items()}
    for day in strategy_allocations:
        alloc_mult = np.clip(total_allocation / day_total_allocations[day], 0, 4) if day_total_allocations[day] else 1
        strategy_allocations[day] = {strat: alloc * alloc_mult for strat, alloc in strategy_allocations[day].items()}
    return strategy_allocations


def get_midas_pl(adj: bool) -> Dict[date, float]:
    trades = {strat: get_trade(strat, t_util.add_to_mkt_date(-(strat.dd_lookback + 30 + (30 if adj else 0)))) for strat in strategy_list.strategies}

    if Config.get('strategy_allocations.adjust_to_use_all_capital'):
        strategies_allocations = get_adj_strategies_allocations(strategy_list.strategies, 30 + (30 if adj else 0), trades)
    else:
        strategies_allocations = get_strategies_allocations(strategy_list.strategies, 30 + (30 if adj else 0), trades)

    max_alloc = sum([Config.get(f'strategy_allocations.{strat.name}') for strat in strategy_list.strategies])

    midas_pls = {day: 0 for day in strategies_allocations}
    yesterday = list(strategies_allocations)[0]
    for day, strat_allocs in list(strategies_allocations.items())[1:]:
        for strat in strat_allocs:
            alloc = strategies_allocations[yesterday][strat] / max_alloc
            midas_pls[day] = midas_pls.get(day, 0) + (trades[strat][day] * alloc)
        yesterday = day

    if adj:
        pls = list(midas_pls.values())
        adj_midas_pls = dict()
        for i, (day, pl) in enumerate(list(midas_pls.items())[-30:], 30):
            prev_pls = np.cumsum(pls[i-30:i])
            dd = max(prev_pls) - prev_pls[-1] if any(prev_pls) else 0
            if dd >= 2:
                adj_midas_pls[day] = 0
            else:
                adj_midas_pls[day] = pl
        midas_pls = adj_midas_pls

    return midas_pls


def midas_in_dd() -> Tuple[bool, float]:
    midas_pl = np.cumsum(list(get_midas_pl(False).values()))
    dd = max(midas_pl) - midas_pl[-1]
    return dd >= 2, dd


