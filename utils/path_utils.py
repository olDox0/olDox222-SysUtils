# utils/path_utils.py

import os


def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def is_accessible(path: str) -> bool:
    return os.path.exists(path) and os.access(path, os.R_OK)


def get_extension(path: str) -> str:
    _, ext = os.path.splitext(path)
    return ext.lower()