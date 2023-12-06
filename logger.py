import os
from typing import Optional, Any

from files import MIDAS_PATH
from utils import t_util


def log(folder: Optional[str], msg: str, *args):
    """
    Base function to log a message.

    Parameters
    ----------
    folder : optional, str
        The folder the logs will be written in.
        If 'None' (default), logs will be written in the logs directory.
    msg : str
        The message that will be logged.
    *args : Arguments
        Can be used to write an object in 'msg'.

    See Also
    --------
    log : to log

    Notes
    -----
    This method should be not be called directly. Use the log decorator to log.
    Use a '@' in the 'msg', followed by the number that represents the argument index in the wrapped function to write
    an object to 'msg'.

    """
    logs_dir_path = f'{MIDAS_PATH}/logs/{folder + "/" if folder is not None else ""}'
    try:
        with open(f'{logs_dir_path}/{t_util.get_today()}', 'a') as log_file:
            log_file.write(f'{t_util.get_current_time()}   {__format_log_msg(msg, *args)}\n')
    except FileNotFoundError:
        os.makedirs(logs_dir_path)
        log(folder, msg)


def dlog(folder: Optional[str], msg: str):
    """
    Used to log message.

    Parameters
    ----------
    folder : optional, str
        The folder the logs will be written in.
        If 'None' (default), logs will be written in the logs directory.
    msg : str
        The message that will be logged.

    """

    def inner(func):
        def wrapper(*args, **kwargs):
            log(folder, msg, *args)
            return func(*args, **kwargs)

        return wrapper

    return inner


def __format_log_msg(msg: str, *args):
    """
    Used in 'log_' to format a message.

    Parameters
    ----------
     msg : str
        The message that will be logged.
    *args : Arguments
        Can be used to write an object in 'msg'.

    Notes
    -----
    Use a '@' in the 'msg', followed by the number that represents the argument index in the wrapped function to write
    an object to 'msg'.

    """
    for i in range(len(msg) - 1):
        if (at_ := msg[i]) == '@' and (idx := msg[i + 1]).isdigit():
            if (idx := int(idx)) < len(args):
                val = to_string(args[idx])
            else:
                val = 'None'
            msg = msg.replace(f'{at_}{idx}', val)
    return msg


def to_string(obj: Any):
    if isinstance(obj, list) or isinstance(obj, tuple):
        return str([to_string(ele) for ele in obj])
    elif isinstance(obj, dict):
        return str({to_string(k): to_string(v) for k, v in obj.items()})
    else:
        return str(obj)
