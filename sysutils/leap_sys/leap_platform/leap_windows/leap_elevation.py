# sysutils/leap_sys/leap_platform/leap_windows/leap_elevation.py
"""
⚔️ ARES — Motor de Elevação e Compatibilidade Nativa do Windows.
Gerencia a injeção silenciosa de regras de compatibilidade (HKCU) 
para garantir que o Lite XL solicite UAC e habilite os Hooks de Baixo Nível.
"""
import os
import sys
import shutil
import ctypes
import subprocess
from pathlib import Path

def is_admin() -> bool:
    """Verifica se o processo atual possui privilégios de Administrador."""
    if os.name != 'nt':
        return os.geteuid() == 0 if hasattr(os, 'geteuid') else False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def _find_litexl_exe() -> str | None:
    """Sonda o sistema para encontrar o caminho absoluto do lite-xl.exe."""
    if os.name != 'nt': return None
    common_paths = [
        r"C:\Program Files\Lite XL\lite-xl.exe",
        r"C:\Program Files (x86)\Lite XL\lite-xl.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Lite XL\lite-xl.exe"),
    ]
    for p in common_paths:
        if os.path.exists(p): return p
    return None

def create_sovereign_shortcut() -> tuple[bool, str]:
    """
    ⚔️ ARES + HEFESTO: Forja um atalho .lnk na Área de Trabalho com a flag RunAsAdministrator.
    Injeta o bit SLDF_RUNAS_USER (0x20 no offset 0x15) diretamente no binário do atalho.
    """
    exe_path = _find_litexl_exe()
    if not exe_path:
        return False, "lite-xl.exe não encontrado no sistema."

    desktop = Path(os.path.join(os.environ['USERPROFILE'], 'Desktop'))
    shortcut_path = desktop / "Doxly (Admin).lnk"
    
    # Script PowerShell microscópico para criar o atalho e injetar a flag de Admin
    ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{str(shortcut_path)}')
$Shortcut.TargetPath = '{exe_path}'
$Shortcut.WorkingDirectory = '{os.path.expanduser("~")}'
$Shortcut.IconLocation = '{exe_path},0'
$Shortcut.Description = 'Doxly IDE (Elevated for KVM/Leap)'
$Shortcut.Save()

# Injeção Binária da Flag RunAsAdministrator (Ares Hack)
$bytes = [System.IO.File]::ReadAllBytes('{str(shortcut_path)}')
$bytes[0x15] = $bytes[0x15] -bor 0x20 
[System.IO.File]::WriteAllBytes('{str(shortcut_path)}', $bytes)
"""
    try:
        # Execução 100% silenciosa (Zero-Flash, Zero-Window)
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", ps_script],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return True, f"Atalho soberano forjado em: {shortcut_path}"
    except Exception as e:
        return False, f"Falha ao forjar atalho: {e}"

def ensure_litexl_admin_elevation() -> tuple[bool, str]:
    """
    ⚔️ ARES: Injeta silenciosamente a regra 'RUNASADMIN' no Registro do Usuário (HKCU).
    Isso força o Windows a solicitar UAC e habilitar os Hooks Globais (WH_MOUSE_LL) 
    sempre que o editor for aberto, seja pelo ícone, menu iniciar ou CLI.
    """
    if os.name != 'nt':
        return False, "Recurso exclusivo do Windows."

    exe_path = _find_litexl_exe()
    if not exe_path:
        return False, "lite-xl.exe não foi encontrado no sistema. Instale-o ou adicione-o ao PATH."

    try:
        import winreg
        # A chave HKCU NÃO requer privilégios de Admin para ser escrita!
        reg_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
        
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
        # O valor "RUNASADMIN" é o contrato oficial do Windows para forçar elevação
        winreg.SetValueEx(key, exe_path, 0, winreg.REG_SZ, "RUNASADMIN")
        winreg.CloseKey(key)
        
        return True, f"Regra de elevação injetada com sucesso para: {exe_path}"
    except Exception as e:
        return False, f"Falha ao acessar o registro do Windows: {e}"

def remove_litexl_admin_elevation() -> tuple[bool, str]:
    """Remove a regra de elevação forçada (caso o usuário queira reverter)."""
    if os.name != 'nt': return False, "Apenas Windows."
    exe_path = _find_litexl_exe()
    if not exe_path: return False, "Executável não encontrado."
    
    try:
        import winreg
        reg_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, exe_path)
        winreg.CloseKey(key)
        return True, "Regra de elevação removida."
    except FileNotFoundError:
        return True, "Nenhuma regra estava ativa."
    except Exception as e:
        return False, f"Erro ao remover: {e}"
