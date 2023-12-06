import os

# To allow the command prompt to use colors
os.system('color')


class color:
    """Can be added before strings to color text that is outputted to the console."""

    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'