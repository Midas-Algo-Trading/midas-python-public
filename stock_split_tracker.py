import json
from datetime import time, timedelta, date, datetime
from typing import List, Set, Dict

from bs4 import BeautifulSoup

import positions
import schedule
from data import live_data
from files.config import Config
from logger import log
from orders import order_fill_checker, order_pool
from orders.orders.limit_order import LimitOrder
from orders.order import Session, Duration, PositionEffect
from tda import tda_client
from utils import t_util, r_util

stock_splits: Dict[date, Set[str]] = dict()


def update(reschedule: bool):
    # Ensure yesterday data exists
    last_mkt_date = t_util.add_to_mkt_date(-1)
    if not stock_splits.get(last_mkt_date):
        stock_splits[last_mkt_date] = get_yesterday_splits_from_polygon()

    # Ensure today data exists
    if not stock_splits.get(t_util.get_today()):
        # Load set for today's stock splits
        stock_splits[t_util.get_today()] = set()

    # Ensure tomorrow data exists
    next_mkt_date = t_util.add_to_mkt_date(1)
    if not stock_splits.get(next_mkt_date):
        # Load set for today's stock splits
        stock_splits[next_mkt_date] = set()

    # Get stock splits

    get_splits_from_yahoo_finance()

    get_today_splits_from_polygon()

    get_splits_from_benzinga()

    log('stock_splits', str(stock_splits))

    close_positions_of_splitting_stocks()

    if reschedule:
        reschedule_update()


def get_splits_from_yahoo_finance():
    stock_split_calendar_response = r_util.send_request(
        'GET',
        f'https://finance.yahoo.com/calendar/splits?from={t_util.add_to_mkt_date(-3).strftime("%Y-%m-%d")}&to={t_util.get_today().strftime("%Y-%m-%d")}&day={t_util.get_today().strftime("%Y-%m-%d")}',
        False,
        headers={"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"}
    )
    soup = BeautifulSoup(stock_split_calendar_response.text, "html.parser")

    table_contents = soup.tbody.contents if soup.tbody else []
    splitting_stocks = [stock.contents[0].a.string for stock in table_contents]

    stock_splits[t_util.get_today()].update(splitting_stocks)


def get_today_splits_from_polygon():
    splitting_stocks_url = f'https://api.polygon.io/v3/reference/splits?execution_date.gte={t_util.get_today()}&apiKey={Config.get("polygon_api_key")}'
    splitting_stocks = [result['ticker'] for result in r_util.send_request('GET', splitting_stocks_url, False).json()['results']]

    stock_splits[t_util.get_today()].update(splitting_stocks)


def get_splits_from_benzinga():
    stock_split_calendar_response = r_util.send_request(
        'GET',
        f'https://www.benzinga.com/calendars/stock-splits',
        False,
        headers={"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"}
    )
    soup = BeautifulSoup(stock_split_calendar_response.text, "html.parser")
    data = soup.find('script', type='application/json')

    for split_data in json.loads(data.text)["props"]["pageProps"]["calendarDataSet"]:
        split_date = datetime.strptime(split_data['date_ex'], '%Y-%m-%d').date()
        if t_util.add_to_mkt_date(-1) <= split_date <= t_util.add_to_mkt_date(1):
            splits = stock_splits.get(split_date, set())
            splits.add(split_data["ticker"])
            stock_splits[split_date] = splits


def close_positions_of_splitting_stocks():
    # Get unregistered stock splits
    splitting_stocks = get_splitting_stocks()

    # Close any positions of a splitting stock
    for tda_account_id in [0, 1]:
        for symbol in splitting_stocks:

            # Check for current close order, and close if necessary
            order = order_pool.get_order_by_symbol(symbol, tda_account_id)
            if order:
                tda_client.cancel_order(order.id)

            position = positions.get_by_symbol(symbol, tda_account_id)

            if (not position) or (not position.quantity):
                continue

            # Check if account can day trade
            if not tda_client.get_account(tda_account_id).day_trades_left:
                continue

            # Close the position

            # Create the order
            stock_mkt_price = live_data.get_market_prices([position.symbol], tda_account_id)[position.symbol]
            session = Session.PM if t_util.get_current_time() > t_util.get_market_close_time() else Session.AM
            order = LimitOrder(position.symbol, -position.quantity, stock_mkt_price, session, Duration.DAY,
                               position_effect=PositionEffect.CLOSE)
            order.current_price = stock_mkt_price
            order.composition = {strat: -qty for strat, qty in position.composition.items()}

            # Add order to order pool
            order = order_pool.add_order(order, tda_account_id)
            # Place the order
            tda_client.place_orders([order], tda_account_id)
            # Schedule fill checks for sent orders
            order_fill_checker.schedule_checks([order], tda_account_id)


def get_yesterday_splits_from_polygon() -> Set[str]:
    split_request_url = f'https://api.polygon.io/v3/reference/splits?execution_date.gte={t_util.get_yesterday()}&apiKey={Config.get("polygon_api_key")}'
    return {result['ticker'] for result in r_util.send_request('GET', split_request_url, False).json()['results']}


def get_splitting_stocks() -> List[str]:
    yesterday_stock_splits = [symbol for symbol in stock_splits[t_util.add_to_mkt_date(-1)]]
    today_stock_splits = [symbol for symbol in stock_splits[t_util.get_today()]]
    tomorrow_stock_splits = [symbol for symbol in stock_splits[t_util.add_to_mkt_date(1)]]
    return list(set(yesterday_stock_splits + today_stock_splits + tomorrow_stock_splits))


def reschedule_update():
    if t_util.get_current_time() < time(9, 27):
        schedule.add(min(t_util.get_current_datetime().replace(hour=9, minute=28),
                         t_util.get_current_datetime() + timedelta(minutes=5)), update, True)
    else:
        schedule.add(max(t_util.get_current_datetime().replace(hour=15, minute=47),
                         t_util.get_current_datetime() + timedelta(minutes=5)), update, True)