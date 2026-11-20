# energy_sys/core/system_tweaks.py
from __future__ import annotations
import winreg
import ctypes
import subprocess
import os
from typing import Tuple, List

def is_admin() -> bool:
    """Verifica se o terminal está com privilégios de Administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def _set_reg(hive: int, path: str, name: str, value: int) -> Tuple[bool, str]:
    """Escreve um DWORD no registro."""
    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
        return True, "OK"
    except PermissionError:
        return False, "Acesso negado. Execute como Administrador."
    except Exception as e:
        return False, str(e)

def _get_reg(hive: int, path: str, name: str) -> int | None:
    """Lê um DWORD do registro."""
    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return val
    except FileNotFoundError:
        return None
    except Exception:
        return None

def apply_modern_standby_network(disable: bool) -> Tuple[bool, str]:
    """
    Ativa/desativa a conectividade de rede durante o Modern Standby (S0).
    Desativar economiza muita bateria enquanto o notebook está fechado.
    """
    if not is_admin():
        return False, "Requer Administrador."
    # 0 = Desativado (Economia), 1 = Ativado (Conectado)
    value = 0 if disable else 1
    path = r"SYSTEM\CurrentControlSet\Control\Power\ModernSleep"
    return _set_reg(winreg.HKEY_LOCAL_MACHINE, path, "NetworkConnectivityInStandby", value)

def apply_fast_startup(disable: bool) -> Tuple[bool, str]:
    """
    Desativa a Inicialização Rápida (Fast Startup). Ajuda a evitar drenos
    fantasmas e garante que o desligamento seja completo.
    """
    if not is_admin():
        return False, "Requer Administrador."
    value = 0 if disable else 1
    path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Power"
    return _set_reg(winreg.HKEY_LOCAL_MACHINE, path, "HiberbootEnabled", value)

def apply_hybrid_cpu_policy(disable: bool) -> Tuple[bool, str]:
    """
    Força o processador a priorizar núcleos de eficiência (E-Cores) na bateria.
    Usa o powercfg para alterar a política de agendamento de núcleos.
    """
    # GUID para "Processor performance core parking min cores" (na bateria)
    # Valor 100 = força uso máximo dos E-Cores quando possível
    cmd = [
        "powercfg", "/setdcvalueindex", "SCHEME_CURRENT",
        "54533251-82be-4824-96c1-47b60b740d00", # SUB_PROCESSOR
        "0cc5b647-c1df-4637-891a-dec35c318583", # Core Parking
        "100" if disable else "0"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0, res.stderr.strip() or "OK"
    except Exception as e:
        return False, str(e)

def get_intel_dtt_version() -> str | None:
    """Verifica a versão do Intel Dynamic Tuning / IPF via PowerShell."""
    ps_cmd = (
        "Get-CimInstance Win32_PnPSignedDriver | "
        "Where-Object {$_.DeviceName -match 'Intel\\(R\\) Dynamic Tuning' -or $_.DeviceName -match 'Innovation Platform Framework'} | "
        "Select-Object DeviceName, DriverVersion | Format-List"
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], 
                             capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return None
