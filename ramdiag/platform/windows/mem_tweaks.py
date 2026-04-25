# ramdiag/platform/windows/mem_tweaks.py
import winreg

def _set_reg_value(path, name, value, type=winreg.REG_DWORD):
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, type, value)
        winreg.CloseKey(key)
        return True
    except WindowsError:
        return False

def set_disable_paging_executive(enabled):
    path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
    return _set_reg_value(path, "DisablePagingExecutive", enabled)

def set_large_system_cache(enabled):
    path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
    return _set_reg_value(path, "LargeSystemCache", enabled)

def optimize_io_lock_limit():
    """Calcula um valor ideal baseado na RAM total para o IoPageLockLimit."""
    import psutil
    ram_gb = psutil.virtual_memory().total / (1024**3)
    
    # Valor em bytes. Ex: Para 8GB DDR3, 64MB de lock é um valor equilibrado.
    value = 65536 if ram_gb >= 4 else 32768
    path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
    return _set_reg_value(path, "IoPageLockLimit", value)