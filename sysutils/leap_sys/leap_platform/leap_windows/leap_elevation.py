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
    if os.name != 'nt':
        return None

    # 1. Tenta encontrar via Registro (App Paths - O caminho mais confiável no Windows)
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\lite-xl.exe")
        path = winreg.QueryValue(key, None)
        winreg.CloseKey(key)
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    # 2. Tenta encontrar via Variável de Ambiente PATH (where lite-xl)
    path = shutil.which("lite-xl")
    if path and os.path.exists(path):
        return path

    # 3. Fallback: Caminhos comuns de instalação
    common_paths = [
        r"C:\Program Files\Lite XL\lite-xl.exe",
        r"C:\Program Files (x86)\Lite XL\lite-xl.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Lite XL\lite-xl.exe"),
        os.path.expanduser(r"~\AppData\Local\lite-xl\lite-xl.exe")
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
            
    return None

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
