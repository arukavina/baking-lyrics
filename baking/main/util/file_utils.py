"""
Module holding some utilities for doing file related stuff
"""

# Generic
import os.path


class FileSystemException(RuntimeError):
    """
    Simple extension to have args handy.
    """
    def __init__(self, arg):
        self.arg = arg
        super.__init__(arg)


def expand_paths(file_names, recursive=True):
    """
    Goes through the list of *file_names* and expands any directory to the files
    included in that directory.

    :param file_names: A list of paths to expand. If any path is a directory,
        it will be replaced in the list with the
                      contents of the directory.
    :param recursive: If True, any directory in an expanded directory will also be expanded.
    :return: A list of files.
    """

    new_files = []
    for file in file_names:
        if os.path.isdir(file):
            if recursive:
                # We recurse over all files contained in the directory and add them to the list of files
                for dir_path, _, sub_file_names in os.walk(file):
                    new_files.extend([os.path.join(dir_path, filename)
                                      for filename in sub_file_names])
            else:
                # No recursion, we just do a list_file on the files of any directory in file_names
                for sub_file in os.listdir(file):
                    if os.path.isfile(sub_file):
                        new_files.append(os.path.join(file, sub_file))
        elif os.path.isfile(file):
            new_files.append(file)
    return new_files


def create_path(path):
    """
    Creates paths if it doesn't exit
    :param path:
    :return:
    """
    if isinstance(path, list):
        for k in path:
            if not os.path.exists(k):
                try:
                    os.makedirs(k)
                except OSError as error:
                    print('Can\'t create path {}: {}'.format(k, error))
    else:
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as error:
                print('Can\'t create path {}: {}'.format(path, error))
