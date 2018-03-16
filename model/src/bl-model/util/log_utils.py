"""
------------------------------------------------------------------------------------------------------
Script:    Module to set-up logging structure
------------------------------------------------------------------------------------------------------
"""

import logging
import logging.handlers
import os
import sys

_levelToLevel = {
    5: logging.CRITICAL,
    4: logging.ERROR,
    3: logging.WARNING,
    2: logging.INFO,
    1: logging.DEBUG,
    0: logging.NOTSET,
}


def setup_logging(name, ts, args):
    """
    Sets up the logger for the classification.
    :param name: Logger insance name
    :param ts: The timestamp to apply to the file
    :param args: a dictionary with the arguments which are used by the classifier. This dict will be modified,
                 removing items which shouldn't be sent to the classification function.
    :return: None
    """

    named_level = logging.DEBUG

    log_dir = args['log_dir']
    del args['log_dir']

    level = args['log_level']
    del args['log_level']

    try:
        named_level = _levelToLevel[level]
    except IndexError:
        print('[WARNING] - Verbosity non-existent, using DEBUG')

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    print("Logging to {}/ named: {}".format(log_dir, name))

    log_file = '{}_{}.log'.format(name, ts)

    # Logger
    my_log = logging.getLogger(name)
    my_log.propagate = False
    my_log.handlers = []
    my_log.setLevel(named_level)

    formatter = logging.Formatter('%(asctime)s [%(threadName)s] [%(levelname)s] ([%(filename)s::%(funcName)s) '
                                  ':: %(message)s', datefmt='%m/%d/%Y %H:%M:%S')

    # Handlers
    fh_path = os.path.join(log_dir, log_file)

    file_handler = logging.FileHandler(fh_path)
    file_handler.setFormatter(formatter)

    std_handler = logging.StreamHandler(sys.stdout)
    std_handler.setFormatter(formatter)

    my_log.addHandler(file_handler)
    my_log.addHandler(std_handler)


def get_logger(name):
    return logging.getLogger(name)


def print_imports_versions(logger):
    """
    Prints on logger the information about the version of all the imported modules

    :param logger: Logging object to be used
    :return:
    """
    for name, module in sorted(sys.modules.items()):
        if hasattr(module, '__version__'):
            logger.debug('{0} :: {1}'.format(name, module.__version__))


def an_print(logger, string=''):

    if logger is not None:
        if logger.getEffectiveLevel() == 10:
            print(string)
