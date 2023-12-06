import inspect
from datetime import datetime, time
from pytz import timezone
from typing import List, Callable, Union

from strategies.strategy import Strategy
from strategies.strategy_list import strategies
from utils import t_util

schedule = dict()


def fill_schedule():
    for strategy in strategies:
        add(strategy.next_buy_time, strategy.buy)
        add(strategy.next_sell_time, strategy.sell)


def add(run_time: Union[datetime, time], value: Callable, *args, **kwargs):
    """Add a function to the schedule."""
    if isinstance(run_time, time):
        if t_util.get_current_time() < run_time:
            run_date = t_util.get_today()
        else:
            run_date = t_util.get_tomorrow()

        run_date = t_util.get_next_market_open_date(run_date)

        run_time = timezone('US/Eastern').localize(datetime.combine(run_date, run_time))

    run_time = run_time.replace(second=0, microsecond=0)

    # Add *arg and **kwarg arguments.
    if args or kwargs:
        value = (value, args, kwargs)

    # There is already a function set to run at date_time.
    if run_time in schedule.keys():
        schedule[run_time].append(value)
    # No function has been set to run at date_time.
    else:
        # function is put into a list so more strategies can be easily added to run at date_time and iterated
        # through.
        schedule[run_time] = [value]


def get_next_run_time() -> datetime:
    """Gets the next datetime from schedule a strategy needs to be run."""
    return min(list(schedule)) if schedule else None


def get_next_strategy_run_time() -> datetime:
    return min(list({k: v for k, v in schedule.items() if any([Strategy in ele.__self__.__class__.__bases__ for ele in v if inspect.ismethod(ele)])})) if schedule else None


def get_today_strategy_funcs() -> List[Callable]:
    strategies = set()
    for funcs in {run_time: funcs for run_time, funcs in schedule.items() if run_time.date() == t_util.get_today()}.values():
        for func in funcs:
            if inspect.ismethod(func) and Strategy in func.__self__.__class__.__bases__:
                strategies.add(func)
    return list(strategies)


