import asyncio
import copy
import json
import os
import time
from datetime import datetime
from threading import Thread
from typing import List, Dict, Any, Union, Optional

import aiohttp
import pandas as pd

import schedule
from data import daily_aggs_websocket
from data.data_requests.data_request import DataRequest
from data.data_requests.market_snapshot_data_request import MarketSnapshotRequest
from files.config import Config
from files import MIDAS_PATH
from logger import log, dlog
from utils import t_util, dreqst_util, r_util

data = dict()
data_folder = os.path.join(MIDAS_PATH, 'data')
daily_aggs_websocket_thread = None


def load(data_requests: Optional[List[DataRequest]] = None):
    # Clear old data.
    global data
    data = dict()

    # Get data requests.
    if not data_requests:
        data_requests = get_today_data_requests()

    if any([data_request.min_rel_mkt_cap for data_request in data_requests]):
        data_requests = [MarketSnapshotRequest(columns=['close', 'volume'], day=i) for i in range(-1, -11, -1)] + data_requests

    # Split historical data.
    adjust_historical_data_for_splits()

    # Load data.
    if data_requests:
        asyncio.run(download_historical_data(data_requests))
        load_data(data_requests)

    # Start websocket to get daily aggs.
    global daily_aggs_websocket_thread
    daily_aggs_websocket_thread = Thread(target=daily_aggs_websocket.load)
    daily_aggs_websocket_thread.start()

    # Schedule reload.
    add_to_schedule()

    log('market_data', f'Loaded: @0', data)


def get_today_data_requests():
    return dreqst_util.get_data_requests(schedule.get_today_strategy_funcs())


@dlog('market_data', f'Loading live data: @0')
async def load_live_data(data_requests: List[DataRequest]):
    if not data_requests:
        return

    # Wait until 5 second mark for websocket data to come through
    while t_util.get_current_time().second < 5:
        time.sleep(1)

    for data_request in merge_data_requests(data_requests):
        # 'data_request' does not request any live data, so skip it.
        if data_request.day == 0:
            # Wait for websocket to receive data for this minute
            market_snapshot = pd.DataFrame.from_dict(daily_aggs_websocket.daily_aggs_data, orient='index')
            market_snapshot = format_market_snapshot(market_snapshot, data_request.columns,
                                                     data_request.shortable, data_request.min_rel_mkt_cap,
                                                     data_request.round_to)
            market_snapshot.to_csv('market_snapshot.csv')
            market_snapshot = {data_request.day: market_snapshot}
            data_request_market_snapshots = data.get(data_request, dict())
            data_request_market_snapshots.update(market_snapshot)
            data[data_request] = data_request_market_snapshots
            log('market_data', f'Loaded live data. Data: @0', data)
            return


@dlog('market_data', 'Getting: @0')
def get(data_requests: Union[DataRequest, List[DataRequest], None]):
    if not data_requests:
        return None
    if isinstance(data_requests, DataRequest):
        data_requests = [data_requests]

    ret = dict()
    for data_request in data_requests:
        for data_request_, data_ in data.items():
            if data_request_.can_merge_with(data_request):
                ret.update(data_)
                break

    ret = (ret if len(ret) > 1 else list(ret.values())[0]) if ret else None

    log('market_data', f'Got: {ret}')

    return ret


def load_data(data_requests: List[DataRequest]):
    for data_request in data_requests:
        # Market snapshot request.
        if (data_request_day := t_util.add_to_mkt_date(data_request.day)) != t_util.get_today():
            market_snapshot = pd.read_feather(os.path.join(data_folder, 'snapshots', f'{data_request_day}.feather'),
                                              list(set(data_request.columns + ['T', 'close', 'volume'])))
            market_snapshot = market_snapshot.set_index('T')
            market_snapshot = format_market_snapshot(market_snapshot, data_request.columns, data_request.shortable,
                                                     data_request.min_rel_mkt_cap, data_request.round_to)
            market_snapshot = {data_request.day: market_snapshot}
            data_request_market_snapshots = data.get(data_request, dict())
            data_request_market_snapshots.update(market_snapshot)
            data[data_request] = data_request_market_snapshots


def format_market_snapshot(market_snapshot: pd.DataFrame, columns: List[str], shortable: bool, min_rel_mkt_cap: int,
                           round_to: int):
    if min_rel_mkt_cap:
        past_snapshots = get([MarketSnapshotRequest(columns=['close', 'volume'], day=i) for i in range(-1, -11, -1)])
        past_rel_mkt_caps: Dict[str, float] = dict()
        for past_snapshot in list(past_snapshots.values()) + [market_snapshot]:
            rel_mkt_caps = past_snapshot['close'] * past_snapshot['volume']
            for symbol, rel_mkt_cap in zip(past_snapshot.index, rel_mkt_caps):
                past_rel_mkt_caps[symbol] = min(past_rel_mkt_caps.get(symbol, min_rel_mkt_cap), rel_mkt_cap)
        symbols_with_enough_rel_mkt_cap = [symbol for symbol, rel_mkt_cap in past_rel_mkt_caps.items() if rel_mkt_cap >= min_rel_mkt_cap]
        market_snapshot = market_snapshot[market_snapshot.index.isin(symbols_with_enough_rel_mkt_cap)]

    if shortable:
        shortable_symbols = get_shortable_symbols()
        market_snapshot = market_snapshot[market_snapshot.index.isin(shortable_symbols)]

    market_snapshot = market_snapshot.drop(columns=set(market_snapshot.columns).difference(columns))
    market_snapshot = market_snapshot.round(round_to)
    return market_snapshot


def get_shortable_symbols() -> List[str]:
    with open(os.path.join(data_folder, 'shortable_symbols.json'), 'r') as file:
        return [symbol for symbol, shortable in json.load(file).items() if shortable]


def adjust_historical_data_for_splits():
    # Get the days we need to create_child data for.
    with open(os.path.join(MIDAS_PATH, 'data', 'splits.json'), 'r') as file:
        last_split_date = datetime.strptime(json.load(file)['last_split_date'], '%Y-%m-%d').date()

    dates_to_split_for = t_util.get_market_dates(last_split_date, t_util.get_today())

    for split_date in dates_to_split_for:

        splits = r_util.send_request(
            method='GET',
            url=f'https://api.polygon.io/v3/reference/splits?execution_date={split_date}&limit=1000&apiKey={Config.get("polygon_api_key")}',
            accept_bad_response=False).json()['results']

        # Adjust market snapshots.
        dates_before_splits = [day for file in os.listdir(os.path.join(data_folder, 'snapshots')) if
                               (day := datetime.strptime(file.split('.')[0], '%Y-%m-%d').date()) < split_date]

        market_snapshots_to_adjust = {day: pd.read_feather(os.path.join(data_folder, 'snapshots', f'{day}.feather')) for day in dates_before_splits}

        for day, df in market_snapshots_to_adjust.items():
            for split in splits:
                symbol = split['ticker']
                try:
                    symbol_idx = list(df['T']).index(symbol)
                except ValueError:
                    continue  # No data for this stock.

                split_by = split['split_from'] / split['split_to']

                stock_data = df.iloc[symbol_idx]
                df.iloc[symbol_idx] = [symbol,
                                       round(stock_data['open'] * split_by, 4),
                                       round(stock_data['high'] * split_by, 4),
                                       round(stock_data['low'] * split_by, 4),
                                       round(stock_data['close'] * split_by, 4),
                                       stock_data['volume']]
            df.to_feather(os.path.join(data_folder, 'snapshots', f'{day}.feather'))

        # Adjust stocks data.
        for split in splits:
            symbol = split['ticker']
            split_by = split['split_from'] / split['split_to']
            if os.path.isdir(symbol_data_path := os.path.join(data_folder, 'stocks', symbol)):
                for file in os.listdir(symbol_data_path):
                    df = pd.read_feather(os.path.join(symbol_data_path, file))
                    pre_df = df.loc[df['t'] < split_date].copy()
                    pre_df['open'] = round(pre_df['open'] * split_by, 4)
                    pre_df['high'] = round(pre_df['high'] * split_by, 4)
                    pre_df['low'] = round(pre_df['low'] * split_by, 4)
                    pre_df['close'] = round(pre_df['close'] * split_by, 4)

                    post_df = df.loc[df['t'] >= split_date]
                    df = pd.concat([pre_df, post_df])
                    df.to_feather(os.path.join(symbol_data_path, file))

    # Set new last create_child date
    with open(os.path.join(MIDAS_PATH, 'data', 'splits.json'), 'w') as file:
        file.write(json.dumps({'last_split_date': t_util.get_today().strftime('%Y-%m-%d')}))


async def download_historical_data(data_requests: List[DataRequest]):
    urls_to_download = []

    # Get URLs to download from Polygon.io
    for data_request in merge_data_requests(data_requests):
        # Market snapshots
        existing_data_dates = [datetime.strptime(file.split('.')[0], '%Y-%m-%d').date() for file in
                               os.listdir(os.path.join(data_folder, 'snapshots'))]
        data_request_day = t_util.add_to_mkt_date(data_request.day)
        if data_request_day != t_util.get_today() and data_request_day not in existing_data_dates:
            url = f'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{data_request_day}?adjusted=false&apiKey={Config.get("polygon_api_key")}'
            urls_to_download.append(url)

    # Download data from Polygon.io
    async with aiohttp.ClientSession() as session:
        responses = await asyncio.gather(*[fetch(url, session) for url in urls_to_download])

        for url, response in zip(urls_to_download, responses):
            response = await response.json()
            split_url = url.split('/')

            # Response was a market snapshot
            if 'aggs/grouped' in url:
                df = market_snapshot_to_dataframe(response)
                date_ = split_url[10].split('?')[0]
                write_market_snapshot(df, date_)
            # Response was a stock's data
            else:
                symbol, timeframe, multiplier = split_url[6], split_url[9], int(split_url[8])
                df = stock_data_to_dataframe(response, timeframe)
                if os.path.isfile(existing_data_path := os.path.join(data_folder, 'stocks', symbol,
                                                                     f'{timeframe}_{multiplier}.feather')):
                    df = pd.concat([pd.read_feather(existing_data_path), df], ignore_index=True)
                    df = df.drop_duplicates(subset='t', keep='first', ignore_index=True)
                    df = df.sort_values(by='t', ignore_index=True)
                write_stock_data(df, symbol, timeframe, multiplier)


def market_snapshot_to_dataframe(response: Dict[str, Any]) -> pd.DataFrame:
    """
    Converts a response from Polygon.io servers to a DataFrame.
    Parameters
    ----------
    response: Dict[str, Any]
        Response from Polygon.io servers that will be converted to the returned DataFrame.
    Notes
    -----
    The returned DataFrame contains the columns 'open', 'high', 'low', 'close', 'volume'
    """
    df = pd.DataFrame(data=response['results'], index=None)
    df = df.drop(columns=['vw', 't', 'n'])

    df = df[df['T'].str.isalpha() & df['T'].str.isupper()]
    df = df.reset_index(drop=True)

    df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
    df = df.reindex(columns=['T', 'open', 'high', 'low', 'close', 'volume'])
    df = df.astype({'volume': int})
    return df


def stock_data_to_dataframe(response: Dict[str, Any], timeframe: str) -> pd.DataFrame:
    """
    Converts a response from Polygon.io servers to a DataFrame.
    Parameters
    ----------
    response: Dict[str, Any]
        Response from Polygon.io servers that will be converted to the returned DataFrame.
    Notes
    -----
    The returned DataFrame contains the columns 'open', 'high', 'low', 'close', 'volume'
    """
    df = pd.DataFrame(data=response['results'])

    if timeframe == 'minute' or timeframe == 'hour':
        df['t'] = pd.to_datetime(df['t'], unit='ms')
    else:
        df['t'] = pd.to_datetime(df['t'], unit='ms').dt.date

    df = df.drop(columns=['vw', 'n'])

    df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
    df = df.reindex(columns=['t', 'open', 'high', 'low', 'close', 'volume'])
    df = df.astype({'volume': int})
    return df


def write_market_snapshot(df: pd.DataFrame, date_: str):
    df.to_feather(os.path.join(data_folder, 'snapshots', f'{date_}.feather'))


def write_stock_data(df: pd.DataFrame, symbol: str, timeframe: str, multiplier: int):
    symbol_data_path = os.path.join(data_folder, 'stocks', symbol)
    if not os.path.isdir(symbol_data_path):
        os.mkdir(symbol_data_path)
    df.to_feather(os.path.join(symbol_data_path, f'{timeframe}_{multiplier}.feather'))


def merge_data_requests(data_requests: List[DataRequest]) -> List[DataRequest]:
    """Merges 'data_requests' to send the minimum number of requests to Polygon.io servers."""
    data_requests = copy.copy(data_requests)
    merged_data_requests = [data_requests[0]]
    data_requests.remove(data_requests[0])
    for data_request in data_requests:
        for i, merged_data_request in enumerate(merged_data_requests):
            if data_request.can_merge_with(merged_data_request):
                merged_data_requests[i] += data_request
                break
        else:
            merged_data_requests.append(data_request)
    return merged_data_requests


def fetch(url, session) -> Dict[str, Any]:
    """Sends HTML request to the given 'url'"""
    return session.get(url, ssl=False)


def add_to_schedule():
    schedule.add(t_util.get_market_open_time(), load)
