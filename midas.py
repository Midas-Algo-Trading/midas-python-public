import inspect
import traceback

import main
import schedule
import alert
from color import color
from files.config import Config
from time import sleep

import strategy_runner
from logger import log
from strategies.strategy import Strategy
from utils import cli_util, t_util


def run_midas():
    try:
        """Primary function that runs Midas."""

        cli_util.output(color.GREEN + 'Midas Running')
        while not main.end_midas.is_set():
            next_run_time = schedule.get_next_run_time()
            current_time = t_util.get_current_datetime().replace(second=0, microsecond=0)

            if current_time == next_run_time:
                funcs_to_execute = schedule.schedule[current_time]

                # Call any non-strategy functions.
                for func in [func for func in funcs_to_execute if
                             not inspect.ismethod(func) or Strategy not in func.__self__.__class__.__bases__]:
                    if callable(func):
                        func()
                    else:
                        func_, args, kwargs = func[0], func[1], func[2]
                        func_(*args, **kwargs)

                # Buy any strategies.
                strategy_sells_to_run = [func for func in funcs_to_execute if
                                         inspect.ismethod(func) and func.__name__ == 'buy']
                if strategy_sells_to_run:
                    strategy_runner.run(strategy_sells_to_run, True)

                # Sell any strategies.
                strategy_sells_to_run = [func for func in funcs_to_execute if
                                         inspect.ismethod(func) and func.__name__ == 'sell']
                if strategy_sells_to_run:
                    strategy_runner.run(strategy_sells_to_run, True)

                # Remove functions from schedule.
                del schedule.schedule[current_time]

                # Set the new next_run_time.
                next_run_time = schedule.get_next_run_time()

                log('midas', f'Ran functions {funcs_to_execute}. Schedule: {schedule.schedule}')

            dif = next_run_time - current_time
            sleep(min(dif.seconds * 0.95, Config.get('midas_max_sleep_time')))
    except Exception:
        alert.alert(traceback.format_exc()[:-1])
        main.end_midas.set()
    cli_util.output(color.YELLOW + 'Midas thread exited')
    exit()
