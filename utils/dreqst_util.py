from typing import List, Callable

from data.data_requests.data_request import DataRequest


def get_data_requests(funcs: List[Callable]) -> List[DataRequest]:
    data_requests = []
    for func in funcs:
        func_name = func.__name__
        strategy = func.__self__.__class__
        strategy_data_requests = strategy.get_buy_data_request() if func_name == 'buy' else strategy.get_sell_data_request()
        strategy_data_requests = [strategy_data_requests] if isinstance(strategy_data_requests, DataRequest) else strategy_data_requests
        if strategy_data_requests:
            data_requests.extend(strategy_data_requests)
    return data_requests
