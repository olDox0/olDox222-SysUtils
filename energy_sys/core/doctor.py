# energy_sys/core/doctor.py
from __future__ import annotations
import ctypes
import importlib.util
import subprocess
from typing import Tuple, List

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def is_library_installed() -> bool:
    return importlib.util.find_spec("HardwareMonitor") is not None

def is_pawnio_running() -> bool:
    """Verifica se o serviço do driver PawnIO está ativo."""
    try:
        res = subprocess.run(["sc", "query", "PawnIO"], capture_output=True, text=True, encoding="cp850")
        return "RUNNING" in res.stdout.upper()
    except Exception:
        return False

def run_diagnostics() -> Tuple[bool, List[str]]:
    """Roda todos os checks e retorna o status geral + logs."""
    logs = []
    all_ok = True

    # 1. Admin
    if is_admin():
        logs.append("✔ [ADMIN] Terminal está com privilégios de Administrador.")
    else:
        logs.append("✘ [ADMIN] Terminal NÃO está como Administrador. O hardware pode falhar.")
        all_ok = False

    # 2. Biblioteca
    if is_library_installed():
        logs.append("✔ [BIBLIOTECA] Pacote 'HardwareMonitor' está instalado.")
    else:
        logs.append("✘ [BIBLIOTECA] Pacote 'HardwareMonitor' NÃO encontrado.")
        all_ok = False

    # 3. PawnIO Driver
    if is_pawnio_running():
        logs.append("✔ [DRIVER] Serviço PawnIO está rodando (leitura de hardware ativa).")
    else:
        logs.append("✘ [DRIVER] Serviço PawnIO NÃO está rodando. Instale/Inicie o driver.")
        all_ok = False

    return all_ok, logs
