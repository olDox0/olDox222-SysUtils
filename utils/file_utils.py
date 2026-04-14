# utils/file_utils.py

import os


def safe_stat(path):
    try:
        return os.stat(path)
    except (PermissionError, FileNotFoundError, OSError):
        return None


def is_file(path):
    return os.path.isfile(path)


def is_dir(path):
    return os.path.isdir(path)