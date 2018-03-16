#!/usr/bin/env python
"""
Model Factory for BL models
"""

# Generic
import argparse
import datetime
import os

# Own
from util import log_utils
from util import settings_util

__author__ = "Andrei Rukavina"
__credits__ = ["Andrei Rukavina"]
__license__ = "GNU GENERAL PUBLIC LICENSE"
__version__ = "0.0.1"
__maintainer__ = "Andrei Rukavina"
__email__ = "rukavina.andrei@gmail.com"
__status__ = "DEV"

logger = None


def get_cli_args():
    """
    Returns the command line arguments.
    :return: A dictionary with the command line argument keys
    """
    parser = argparse.ArgumentParser(description="""Baking Lyrics model factory""")
    parser.add_argument("--log-dir",
                        help="Directory used to writing classification log files.",
                        default='../logs',
                        dest='log_dir')
    parser.add_argument("--output-dir",
                        help="Directory used to write results into.",
                        default='../output',
                        dest='output_dir')
    parser.add_argument("--log-level",
                        help=("The log level for the bl-model script"
                              " 5: CRITICAL"
                              " 4: ERROR,"
                              " 3: WARNING,"
                              " 2: INFO,"
                              " 1: DEBUG,"
                              " 0: NOTSET"),
                        default=1,
                        type=int,
                        choices=[0, 1, 2, 3, 4, 5],
                        dest='log_level')
    args_dict = vars(parser.parse_args())

    return args_dict


def main():

    global logger

    args_dict = get_cli_args()

    root_dir = os.getcwd()
    settings = settings_util.fix_settings(args_dict, root_dir)

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M_%S')

    log_utils.setup_logging('bl-model', timestamp, settings)
    logger = log_utils.get_logger('bl-model')

    log_utils.print_imports_versions(logger)

    logger.info('Settings processed: [Ok]')


if __name__ == '__main__':
    main()
