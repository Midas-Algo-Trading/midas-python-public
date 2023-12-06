import threading
import traceback
from threading import Thread

import positions
import schedule
import stock_split_tracker
from color import color
import midas
from commands import command_list
from data import market_data
from files.config import Config
from files.structure_setup import setup_files_structure
from tda import tda_client

from utils import cli_util

end_midas = threading.Event()


def user_input():
    """Allows the user to exit/quit Midas by typing an equivalent to "quit" or "exit" into the console."""
    command_manager = command_list.initialize_commands()

    while not end_midas.is_set():
        try:
            u_input = input()
            u_input_parts = u_input.split(' ')
            command_manager.get_command(cmd_name=u_input_parts[0], args=u_input_parts[1:])
        except Exception:
            cli_util.output(color.FAIL + traceback.format_exc()[:-1])


if __name__ == '__main__':
    # Tell console Midas is loading.
    cli_util.output(color.YELLOW + 'Loading Midas...')

    # Load file structure.
    setup_files_structure()

    # Read config.
    Config.read()

    # Fill the schedule.
    schedule.fill_schedule()

    # Load market data.
    market_data.load()

    # Load TDA client.
    tda_client.load(0)
    tda_client.load(1)

    # Load positions.
    positions.load(0)
    positions.load(1)

    # Load stock split tracker.
    stock_split_tracker.update(True)

    # Start the thread that allows the user to stop Midas.
    user_input_thread = Thread(target=user_input)
    user_input_thread.start()

    # Run the run_midas Midas function.
    midas.run_midas()
