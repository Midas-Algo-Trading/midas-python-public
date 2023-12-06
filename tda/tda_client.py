import json
import os
import time
from datetime import timedelta
from typing import Optional, Tuple, Union, List, Dict

import schedule
from files.config import Config
from files import MIDAS_PATH
from logger import dlog
from orders.order_properties import PositionEffect
from tda.tda_account import tdaAccount
from tda.tokens.access_token import AccessToken
from tda.tokens.refresh_token import RefreshToken
from utils import t_util, r_util
from alert import send_sms

access_token = {0: AccessToken, 1: AccessToken}
refresh_token = {0: RefreshToken, 1: RefreshToken}
__account = {0: tdaAccount, 1: tdaAccount}
traded_capital = {0: 0, 1: 0}


def load(tda_account_id: int):
    global refresh_token
    global access_token
    global __account

    access_token[tda_account_id], refresh_token[tda_account_id] = __get_refresh_token(tda_account_id)

    if not access_token[tda_account_id]:
        access_token[tda_account_id] = AccessToken(refresh_token[tda_account_id].token, tda_account_id)

    __account[tda_account_id] = tdaAccount(access_token[tda_account_id].token, Config.get(f'tda{tda_account_id}.account_number'))


def __get_refresh_token(tda_account_id: int) -> Tuple[Union[AccessToken, None], RefreshToken]:
    # Get refresh token from file.
    refresh_token_path = f'{MIDAS_PATH}/refresh_token_{tda_account_id}.json'
    if os.path.exists(refresh_token_path):
        with open(refresh_token_path, 'r') as file:
            file_data = json.load(file)

            # Return the refresh refresh_token if the refresh_token is not expired.
            if (expire_time := file_data['expire_time']) > int(time.time()):
                return None, RefreshToken(file_data['token'], tda_account_id, expire_time)
            else:
                return get_new_refresh_token(file_data['token'], tda_account_id)
    else:
        # Get refresh token from user.
        refresh_token_from_user = input(f'Enter your Refresh Token for the TDA-API for TDA account id {tda_account_id}:\n')
        return get_new_refresh_token(refresh_token_from_user, tda_account_id)


def get_new_refresh_token(existing_refresh_token: str, tda_account_id: int) -> Tuple[AccessToken, RefreshToken]:
    # Get new refresh token from TDA.
    new_refresh_token = RefreshToken(existing_refresh_token, tda_account_id)

    # Store the refresh token in file.
    refresh_token_path = f'{MIDAS_PATH}/refresh_token_{tda_account_id}.json'
    with open(refresh_token_path, 'w') as file:
        data = json.dumps({
            'token': new_refresh_token.token,
            'expire_time': new_refresh_token.expire_time
        })
        file.write(data)

    return new_refresh_token.access_token, new_refresh_token


def access_tda_account(func):
    def wrapper(*args, **kwargs):
        for _access_token in access_token.values():
            if _access_token.is_expired:
                _access_token.refresh()
        return func(*args, **kwargs)
    return wrapper


@access_tda_account
@dlog('tda/client', 'Placed order @0. Replaced order @1')
def __place_order(order, tda_account_id: int, replace_order_id: Optional[int] = None) -> Optional[int]:
    # Redundancy system.

    # Get the order's total trade capital
    order_total_trade_capital = 0
    if order.position_effect == PositionEffect.OPEN:
        order_total_trade_capital += order.quantity * order.current_price
    if order.child_order and order.child_order.position_effect == PositionEffect.OPEN:
        order_total_trade_capital += order.child_order.quantity * order.current_price

    # Check if the trade capital limit is breached
    global traded_capital
    order_trade_capital = abs(order_total_trade_capital)
    traded_capital[tda_account_id] += order_trade_capital

    if traded_capital[tda_account_id] >= Config.get(f'trade_capital_limit{tda_account_id}.capital'):
        return None

    schedule.add(t_util.get_current_datetime() + timedelta(minutes=Config.get(f'trade_capital_limit{tda_account_id}.minutes') + 1),
                 remove_traded_capital, order_trade_capital, tda_account_id)

    # Send the order
    response = r_util.send_request('POST',
                                   url=f'https://api.tdameritrade.com/v1/accounts/{Config.get(f"tda{tda_account_id}.account_number")}/orders{f"/{replace_order_id}" if replace_order_id else ""}',
                                   accept_bad_response=True,
                                   json=order.to_json(),
                                   headers={'Authorization': f'Bearer {access_token[tda_account_id].token}'})

    # Set the order id
    try:
        order.id = int(response.headers['Location'].split('orders/')[1])
    except Exception:
        print(f'Order error with order: {order.heaaders}')
        order.quantity = 0
        return -1

    return order.id


@dlog('tda/client', 'Placed orders @0')
def place_orders(orders, tda_account_id: int) -> List[int]:
    check_trade_capital_limit_on_account(tda_account_id)

    # Place orders
    orders_capital = 0
    for order in orders:
        # Safety check
        order_capital = order.current_price * order.quantity if order.position_effect == PositionEffect.OPEN else 0
        # Check capital spent every $200 in orders
        if orders_capital + order_capital >= 200:
            check_trade_capital_limit_on_account(tda_account_id)
            orders_capital = 0
        else:
            orders_capital += order_capital

        # Place order
        order_id = __place_order(order, tda_account_id)
        if not order_id:
            send_sms(f"Trade Capital Limit Breached On Account {tda_account_id}!")
            break

    # Set orders' child order's id
    tda_orders_data = get_orders(tda_account_id)
    for order in orders:
        if not order.child_order:
            continue

        for tda_order_data in tda_orders_data:
            if tda_order_data['orderId'] == order.id:
                order.child_order.id = tda_order_data['childOrderStrategies'][0]['orderId']
                break


def check_trade_capital_limit_on_account(tda_account_id: int):
    import main
    tda_account = get_account(tda_account_id)
    capital_spent = tda_account.available_funds_non_marginable_trade - tda_account.buying_power_non_marginableTrade
    if capital_spent > Config.get(f'trade_capital_limit{tda_account_id}.capital'):
        send_sms(f"Trade Capital Limit Breached On Account {tda_account_id}!")
        main.end_midas.set()
        exit()


@access_tda_account
def cancel_order(order_id: int, tda_account_id: int):
    r_util.send_request('DELETE',
                        f'https://api.tdameritrade.com/v1/accounts/{Config.get(f"tda{tda_account_id}.account_number")}/orders/{order_id}',
                        True,
                        headers={'Authorization': f'Bearer {access_token[tda_account_id].token}'})


@access_tda_account
def get_account(tda_account_id: int):
    __account[tda_account_id].refresh(access_token[tda_account_id].token)
    return __account[tda_account_id]


@access_tda_account
def get_orders(tda_account_id: int, from_=t_util.get_today()):
    return r_util.send_request('GET',
                               f'https://api.tdameritrade.com/v1/accounts/{Config.get(f"tda{tda_account_id}.account_number")}/orders/',
                               False,
                               params={'fromEnteredTime': from_, 'toEnteredTime': t_util.get_today()},
                               headers={'Authorization': f'Bearer {access_token[tda_account_id].token}'}).json()


@access_tda_account
def get_positions(tda_account_id) -> Dict[str, int]:
    raw_tda_positions = r_util.send_request(
        'GET',
        f'https://api.tdameritrade.com/v1/accounts/{Config.get(f"tda{tda_account_id}.account_number")}',
        False,
        params={'fields': 'positions'},
        headers={'Authorization': f'Bearer {access_token[tda_account_id].token}'}
    ).json()['securitiesAccount']

    if 'positions' not in raw_tda_positions:
        return dict()

    formatted_positions = dict()
    for position in raw_tda_positions['positions']:
        symbol = position['instrument']['symbol']
        qty = position['longQuantity']
        if not qty:
            qty = position['shortQuantity'] * -1

        formatted_positions[symbol] = qty

    return formatted_positions


@access_tda_account
def get_order(order_id: int, tda_account_id: int):
    return r_util.send_request('GET',
                               f'https://api.tdameritrade.com/v1/accounts/{Config.get(f"tda{tda_account_id}.account_number")}/orders/{order_id}',
                               False,
                               headers={'Authorization': f'Bearer {access_token[tda_account_id].token}'}).json()


def remove_traded_capital(amount: Union[int, float], tda_account_id: int):
    global traded_capital
    traded_capital[tda_account_id] -= amount

