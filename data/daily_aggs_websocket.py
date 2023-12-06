import json
import time
import traceback
from datetime import datetime
from typing import Dict, Any, List, Union

import requests
import websocket

import main
from color import color
from files.config import Config
from logger import log
from utils import t_util, cli_util

daily_aggs_data: Dict[str, Dict[str, Union[int, float]]] = dict()
last_received_date = t_util.get_today()


def run():
    ws = websocket.WebSocket()

    ws.connect("wss://socket.polygon.io/stocks")

    ws.send(json.dumps({
    "action": "auth",
    "params": Config.get("polygon_api_key")
    }))

    ws.send(json.dumps({
    "action": "subscribe",
    "params": f"{','.join(['AM.*'])}"
    }))

    global last_received_date
    global daily_aggs_data

    # log('market_data/daily_aggs_websocket', 'started')
    while not main.end_midas.is_set():
        x = ws.recv()
        try:
            received = json.loads(x)

            if received[0]['ev'] == 'AM':
                # Reset daily candle on new day
                if t_util.get_today() != last_received_date:
                    daily_aggs_data = dict()
                    last_received_date = t_util.get_today()

                # Update daily candle if in market times
                update_daily_aggs_data(received, False)

            # Market has closed, so close websocket until next market open
            if t_util.get_current_time() > t_util.get_market_close_time():
                time_until_next_market_open = datetime.combine(t_util.get_next_market_open_date(t_util.get_today()), datetime.min.time()) - t_util.get_current_datetime().replace(tzinfo=None)
                log('market_data/daily_aggs_websocket', 'websocket thread sleeping')
                time.sleep(time_until_next_market_open.seconds)
                log('market_data/daily_aggs_websocket', 'websocket thread no longer sleeping')

        except json.decoder.JSONDecodeError as e:
            today_aggs = requests.get(f'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{t_util.get_today()}?adjusted=false&include_otc=false&apiKey={Config.get("polygon_api_key")}').json()['results']
            log('market_data/daily_aggs_websocket', f'error: {e}. Recieved: {received} Getting grouped daily aggs')
            update_daily_aggs_data(today_aggs, True)
            ws.close()
            run()

    ws.close()
    cli_util.output(color.YELLOW + 'Websocket thread exited')
    exit()


def update_daily_aggs_data(new_aggs_data: List[Dict[str, Any]], daily_aggs: bool):
    global daily_aggs_data

    for symbol_data in new_aggs_data:
        symbol = symbol_data['sym' if not daily_aggs else 'T']

        if not (symbol.isalpha() and symbol.isupper()):
            continue

        if 'otc' in symbol:
            continue

        if symbol not in daily_aggs_data:
            daily_aggs_data[symbol] = dict()

        if not daily_aggs:
            daily_aggs_data[symbol]['volume'] = daily_aggs_data[symbol].get('volume', 0) + symbol_data['v']

        if not (t_util.get_market_open_time() <= t_util.get_current_time() <= t_util.get_market_close_time()):
            continue

        if 'open' not in daily_aggs_data[symbol]:
            daily_aggs_data[symbol]['open'] = round(symbol_data['o'], 3)
            daily_aggs_data[symbol]['high'] = round(symbol_data['h'], 3)
            daily_aggs_data[symbol]['low'] = round(symbol_data['l'], 3)

        if symbol_data['h'] > daily_aggs_data[symbol]['high']:
            daily_aggs_data[symbol]['high'] = round(symbol_data['h'], 3)

        if symbol_data['l'] < daily_aggs_data[symbol]['low']:
            daily_aggs_data[symbol]['low'] = round(symbol_data['l'], 3)

        daily_aggs_data[symbol]['close'] = round(symbol_data['c'], 3)


def load():
    global daily_aggs_data

    try:
        # Wait until new minute, then load grouped daily aggs to get 'missing' data for today.
        while t_util.get_current_time().second != 0:
            time.sleep(1)

        # Load any missed data today
        load_today_aggs()

        # Start websocket
        run()

    except Exception:
        log('market_data/daily_aggs_websocket', f'error: {traceback.format_exc()}. Rerunning')
        cli_util.output(color.WARNING + traceback.format_exc())
        daily_aggs_data = dict()
        load()


def load_today_aggs():
    today_aggs = requests.get(f'https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{t_util.get_today()}?adjusted=false&include_otc=false&apiKey={Config.get("polygon_api_key")}').json()
    if 'results' not in today_aggs:
        return

    today_aggs = today_aggs['results']

    for symbol_data in today_aggs:
        symbol = symbol_data['T']
        if not (symbol.isalpha() and symbol.isupper()):
            continue

        daily_aggs_data[symbol] = {
            'open': round(symbol_data['o'], 3),
            'high': round(symbol_data['h'], 3),
            'low': round(symbol_data['l'], 3),
            'close': round(symbol_data['c'], 3),
            'volume': symbol_data['v']
        }
