# sysdiag/core/startup_manager.py
import winreg

def list_startup_apps():
    """Lista aplicativos que iniciam com o Windows nos registros Run."""
    startup_list = []
    paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run")
    ]
    
    for root, path in paths:
        try:
            key = winreg.OpenKey(root, path, 0, winreg.KEY_READ)
            for i in range(winreg.QueryInfoKey(key)[1]):
                name, val, _ = winreg.EnumValue(key, i)
                startup_list.append({"name": name, "path": val, "root": "System" if root == winreg.HKEY_LOCAL_MACHINE else "User"})
            winreg.CloseKey(key)
        except Exception as e:
            import sys as _dox_sys, os as _dox_os
            exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: list_startup_apps\033[0m")
            print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
            continue
        
    return startup_list