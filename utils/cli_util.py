from color import color

"""For utility functions that involve the command line/console."""


def output(msg: str):
    """
    Outputs a message to the console.
    Auto-rests colors.

    Parameters
    ----------
    msg : str
        The message that will be outputted to console.

    """
    print(f'{msg}' + color.RESET)
