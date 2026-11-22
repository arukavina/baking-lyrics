"""
Script:    Module to set-up logging structure
"""

# Generic
import importlib.metadata
import logging
import logging.handlers
import sys
from pathlib import Path

# Repository root: baking/main/util/log_utils.py -> repo
_REPO_ROOT = Path(__file__).resolve().parents[3]

_INT_TO_LEVEL = {
    5: logging.CRITICAL,
    4: logging.ERROR,
    3: logging.WARNING,
    2: logging.INFO,
    1: logging.DEBUG,
    0: logging.NOTSET,
}


def setup_logging(name, time_stamp, args):
    """
    Sets up the named logger with a stdout handler and, when LOG_DIR is set and writable, a file handler.
    With LOG_DIR = None (production on Lambda, whose filesystem is read-only except /tmp) only stdout is used.
    Calling it again (e.g. on repeated create_app calls) replaces the handlers previously added here,
    so no duplicated output is produced.
    :param name: Logger instance name
    :param time_stamp: The timestamp to apply to the file
    :param args: a mapping (dict or Flask config) holding LOG_DIR and LOG_LEVEL. It is not modified.
    :return: None
    """

    named_level = logging.DEBUG

    log_dir = args.get('LOG_DIR', 'logs')
    if log_dir:
        log_dir = Path(log_dir)
        if not log_dir.is_absolute():
            log_dir = _REPO_ROOT / log_dir

    level = args.get('LOG_LEVEL', 1)

    try:
        named_level = _INT_TO_LEVEL[level]
    except KeyError:
        print('[WARNING] - Verbosity non-existent, using DEBUG')

    if log_dir:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            print(f'[WARNING] - Cannot create {log_dir} ({error}), logging to stdout only')
            log_dir = None

    print(f"Logging to {log_dir or 'stdout'} named: {name}")

    # Logger
    my_log = logging.getLogger(name)
    my_log.propagate = False
    for handler in list(my_log.handlers):
        my_log.removeHandler(handler)
        handler.close()
    my_log.setLevel(named_level)

    formatter = logging.Formatter('%(asctime)s [%(threadName)s] [%(levelname)s]'
                                  ' ([%(filename)s::%(funcName)s) :: %(message)s',
                                  datefmt='%m/%d/%Y %H:%M:%S')

    # Handlers
    if log_dir:
        file_handler = logging.FileHandler(log_dir / f'{name}_{time_stamp}.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        my_log.addHandler(file_handler)

    std_handler = logging.StreamHandler(sys.stdout)
    std_handler.setFormatter(formatter)
    my_log.addHandler(std_handler)


def get_logger(name):
    """
    Returns logger for the given name
    :param name: Logger name
    :return: None
    """
    return logging.getLogger(name)


def print_imports_versions(logger):
    """
    Prints on logger the information about the version of all the imported modules
    :param logger: Logging object to be used
    :return: None
    """
    for dist in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
        logger.debug(f"{dist.metadata['Name']} :: {dist.version}")


def an_print(logger, string=''):
    """
    Prints if logger level is 10
    :param logger: Logger instance
    :param string: String to be printed
    :return: None
    """
    if logger is not None:
        if logger.getEffectiveLevel() == 10:
            print(string)
