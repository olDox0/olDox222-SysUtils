# sysdiag/platform/windows/registry_tweaks.py
import winreg

def set_registry_value(root, path, name, value, val_type=winreg.REG_DWORD):
    try:
        key = winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, val_type, value)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: set_registry_value\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return False

def apply_responsiveness_tweaks():
    """Melhora a velocidade de resposta da interface e menus."""
    # 1. Diminui o tempo de exibição de menus (Padrão 400ms -> 10ms)
    set_registry_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", "MenuShowDelay", "10", winreg.REG_SZ)
    
    # 2. Acelera o fechamento de apps travados no desligamento
    set_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control", "WaitToKillServiceTimeout", "2000", winreg.REG_SZ)
    
    # 3. Desativa o 'Throttling' de rede para jogos/streaming
    set_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "NetworkThrottlingIndex", 0xFFFFFFFF)
    
    # 4. Prioridade de CPU para Win32 Apps (Melhora o foco no app em uso)
    set_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", 38)

def apply_ntfs_optimizations():
    """Otimiza o sistema de arquivos para reduzir latência em DDR3/SSDs antigos."""
    # 1. Desativa a criação de nomes curtos (8.3) - Legado do MS-DOS que atrasa a criação de arquivos
    set_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", "NtfsDisable8dot3NameCreation", 1)
    
    # 2. Desativa a atualização do carimbo de "Último Acesso" (Reduz escritas desnecessárias)
    set_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", "NtfsDisableLastAccessUpdate", 1)
    
    # 3. Aumenta a memória reservada para a MFT (Master File Table) - Melhora a navegação em pastas grandes
    set_registry_value(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", "NtfsMemoryUsage", 2)

def apply_io_priority_tweaks():
    """Garante que o app em foco tenha prioridade máxima de I/O."""
    path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"
    set_registry_value(winreg.HKEY_LOCAL_MACHINE, path, "GPU Priority", 8)
    set_registry_value(winreg.HKEY_LOCAL_MACHINE, path, "Priority", 6)
    set_registry_value(winreg.HKEY_LOCAL_MACHINE, path, "Scheduling Category", "High", winreg.REG_SZ)