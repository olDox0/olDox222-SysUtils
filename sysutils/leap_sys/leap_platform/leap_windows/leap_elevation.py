# sysutils/leap_sys/leap_platform/leap_windows/leap_elevation.py
import ctypes
import os

def is_admin() -> bool:
    """Verifica se o processo possui privilégios de Administrador."""
    if os.name != 'nt':
        return os.geteuid() == 0 if hasattr(os, 'geteuid') else False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
