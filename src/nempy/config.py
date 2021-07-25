import os

DEFAULT_ACCOUNTS_DIR = os.path.expanduser('~/.config/nempy/accounts')
CONFIG_FILE = os.path.expanduser('~/.config/nempy/config.ini')
PROFILES_FILES = os.path.expanduser('~/.config/nempy/profiles')


class C:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    BLINKING = '\033[5m'
    ORANGE = '\033[33m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RED = '\033[31m'
    GREY = '\033[90m'
    INVERT = '\033[7m'
