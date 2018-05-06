"""
Module to process settings
"""

# Generics
import json
import os.path

# Own
from util import file_utils as fu

REQUIRED_KEYS = (
    "LOG_PATH",
    "WORKERS",
    "RANDOM_STATE"
)


def create_paths_if_necessary(settings):
    for key, setting in settings.items():
        if 'path' in key.lower():
            fu.create_path(setting)


def fix_settings(settings, root_dir):
    """
    Goes through the settings dictionary and makes sure the paths are correct.
    :param settings: A dictionary with settings, usually obtained from SETTINGS.json in the root directory.
    :param root_dir: The root path to which any path should be relative.
    :return: A settings dictionary where all the paths are fixed to be relative to the supplied root directory.
    """
    fixed_settings = dict()
    for key, setting in settings.items():
        if 'path' in key.lower():
            if isinstance(setting, str):
                setting = os.path.join(root_dir, setting)
            elif isinstance(setting, list):
                setting = [os.path.join(root_dir, path) for path in setting]
        fixed_settings[key] = setting
        # print("k {} - s {}".format(key, setting))

        create_paths_if_necessary(fixed_settings)

    return fixed_settings


def get_settings(settings_path):
    """
    Reads the given json settings file and makes sure the path in it are correct.
    Creates path variables if necessary
    :param settings_path: The path to the json file holding the settings.
    :return: A dictionary with settings.
    """
    with open(settings_path) as settings_fp:
        settings = json.load(settings_fp)
    root_dir = os.path.dirname(settings_path)
    fixed_settings = fix_settings(settings, root_dir)

    return fixed_settings
