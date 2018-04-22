"""
Module holding some utilities for doing file related stuff
"""

import os.path


class FileSystemException(RuntimeError):
    def __init__(self, arg):
        self.arg = arg


def expand_paths(file_names, recursive=True):
    """
    Goes through the list of *filenames* and expands any directory to the files included in that directory.

    :param file_names: A list of paths to expand. If any path is a directory, it will be replaced in the list with the
                      contents of the directory.
    :param recursive: If True, any directory in an expanded directory will also be expanded.
    :return: A list of files.
    """

    new_files = []
    for file in file_names:
        if os.path.isdir(file):
            if recursive:
                # We recurse over all files contained in the directory and add them to the list of files
                for dirpath, _, subfilenames in os.walk(file):
                    new_files.extend([os.path.join(dirpath, filename)
                                      for filename in subfilenames])
            else:
                # No recursion, we just do a listfile on the files of any directoy in filenames
                for subfile in os.listdir(file):
                    if os.path.isfile(subfile):
                        new_files.append(os.path.join(file, subfile))
        elif os.path.isfile(file):
            new_files.append(file)
    return new_files


def create_path(p):
    """
    Creates paths if it doesn't exit
    :param p:
    :return:
    """
    if isinstance(p, list):
        for k in p:
            if not os.path.exists(k):
                try:
                    os.makedirs(k)
                except OSError as e:
                    print('Can\'t create path {}: {}'.format(k, e))
    else:
        if not os.path.exists(p):
            try:
                os.makedirs(p)
            except OSError as e:
                print('Can\'t create path {}: {}'.format(p, e))