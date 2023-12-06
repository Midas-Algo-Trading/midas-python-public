import os
import platform
import numpy as np

import portfolio_manager
import schedule
import strategy_runner
from color import color
from commands import command_manager
from commands.Command import Command
from data import market_data
from files.config import Config
from strategies import strategy_list
from strategies.strategy_list import strategies
from tda import tda_client
from utils import cli_util, t_util
from alert import send_sms
import main


def initialize_commands():
    command_manager.add_command(
        Command(name='force-buy', desc='Force a strategy to buy', func=force_buy, usage='force-buy <strategy name>')
    )
    command_manager.add_command(
        Command(name='force-sell', desc='Force a strategy to sell', func=force_sell, usage='force-sell <strategy name>')
    )
    command_manager.add_command(
        Command(name='exit', desc='Exits Midas', func=stop, usage='exit|stop')
    )
    command_manager.add_command(
        Command(name='stop', desc='Exits Midas', func=stop, usage='exit|stop')
    )
    command_manager.add_command(
        Command(name='refresh-refresh-token', desc='Refreshes your TDA refresh token.', func=refresh_refresh_token, usage='refresh-refresh-token')
    )
    command_manager.add_command(
        Command(name='show-schedule', desc='Displays the schedule.', func=show_schedule, usage='show-schedule')
    )
    command_manager.add_command(
        Command(name='show-orders', desc='Displays all orders sent.', func=show_orders, usage='show-orders <from, today> <raw, False>')
    )
    command_manager.add_command(
        Command(name='force-text', desc='Force a test text.', func=force_text, usage='force-text')
    )
    command_manager.add_command(
        Command(name='clear', desc='Clears the console', func=clear, usage='clear | cls')
    )
    command_manager.add_command(
        Command(name='cls', desc='Clears the console', func=clear, usage='clear | cls')
    )
    command_manager.add_command(
        Command(name='strategies-dd', desc='States whether each strategies is in a drawdown or not', func=strategies_dd, usage='strategies-dd')
    )
    command_manager.add_command(
        Command(name='midas-dd', desc='States whether Midas is in a drawdown or not', func=midas_dd, usage='midas-dd')
    )
    command_manager.add_command(
        Command(name='midas-pl', desc='Gets the pls of Midas', func=midas_pl, usage='midas-pl')
    )

    return command_manager


def force_buy(strategy: str):
    strategies_str = [strategy_name for strategy_name in strategy.split('.') if strategy_name]
    strategies_to_buy = [strategy for strategy in strategies if strategy.name in strategies_str]

    # Check if user entered a valid strategy name
    if not strategies_to_buy:
        cli_util.output(color.FAIL + 'This strategy does not exist.')
        return

    cli_util.output(color.CYAN + f'Running buy for {", ".join(strategies_str)!r}')

    # Store old market data.
    old_market_data_data = market_data.data

    # Run the strategy.
    strategy_runner.run([strategy.buy for strategy in strategies_to_buy], False)

    # Reset the market data data.
    market_data.data = old_market_data_data

    cli_util.output(color.GREEN + f'Ran buy for {", ".join(strategies_str)!r}')


def force_sell(strategy: str):
    strategies_str = [strategy_name for strategy_name in strategy.split('.') if strategy_name]
    strategies_to_sell = [strategy for strategy in strategies if strategy.name in strategies_str]

    # Check if user entered a valid strategy name
    if not strategies_to_sell:
        cli_util.output(color.FAIL + 'This strategy does not exist.')
        return

    cli_util.output(color.CYAN + f'Running sell for {", ".join(strategies_str)!r}')

    # Store old market data.
    old_market_data_data = market_data.data

    # Run the strategy.
    strategy_runner.run([strategy.sell for strategy in strategies_to_sell], False)

    # Reset the market data data.
    market_data.data = old_market_data_data

    cli_util.output(color.GREEN + f'Ran sell for {", ".join(strategies_str)!r}')


def stop():
    main.end_midas.set()
    cli_util.output(color.YELLOW + 'User input thread exited')
    exit()


def refresh_refresh_token():
    tda_client.get_new_refresh_token(tda_client.refresh_token.token)
    cli_util.output(color.GREEN + 'Refreshed refresh token')


def show_schedule():
    cli_util.output(f'{color.UNDERLINE}Schedule:{color.RESET} {t_util.get_current_time().replace(microsecond=0)}\n')
    for k in sorted(schedule.schedule):
        print(f'{"-".join(str(k).split("-")[:-1])}: {schedule.schedule[k]}')


def show_orders():
    cli_util.output(color.UNDERLINE + 'Orders:\n')
    for order in tda_client.get_orders(0):
        print(order)


def force_text():
    send_sms()
    cli_util.output(color.CYAN + 'Sent text')


def clear():
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        os.system('clear')


def strategies_dd():
    trades = {strat: portfolio_manager.get_trade(strat, t_util.add_to_mkt_date(-strat.dd_lookback)) for strat in strategy_list.strategies}
    if Config.get('strategy_allocations.adjust_to_use_all_capital'):
        strategies_allocations = portfolio_manager.get_adj_strategies_allocations(strategies, 0, trades)
    else:
        strategies_allocations = portfolio_manager.get_strategies_allocations(strategies, 0, trades)

    cli_util.output(f'{color.UNDERLINE}Strateies Drawdowns:\n')
    for strategy in strategy_list.strategies:
        is_in_drawdown = portfolio_manager.is_in_drawdown(strategy, 0, trades[strategy])
        in_dd, dd = is_in_drawdown[list(is_in_drawdown.keys())[-1]]
        print(f'{strategy.name} > {in_dd}: -{round(dd, 2)}% - ${round(strategies_allocations[list(strategies_allocations.keys())[-1]][strategy])}')


def midas_dd():
    in_dd, dd = portfolio_manager.midas_in_dd()
    print(f'Midas is in drawdown > {in_dd}: -{round(dd, 2)}%')


def midas_pl():
    pl = {str(day): round(pl, 2) for day, pl in portfolio_manager.get_midas_pl(True).items()}
    cum_pl = {day: round(pl, 2) for day, pl in zip(pl, np.cumsum(list(pl.values())))}
    print(f'Adj Daily PL: {pl}')
    print(f'Adj Cumulative PL: {cum_pl}')
    pl = {str(day): round(pl, 2) for day, pl in portfolio_manager.get_midas_pl(False).items()}
    cum_pl = {day: round(pl, 2) for day, pl in zip(pl, np.cumsum(list(pl.values())))}
    print(f'Raw Daily PL: {pl}')
    print(f'Raw Cumulative PL: {cum_pl}')