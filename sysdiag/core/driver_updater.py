# sysdiag/core/driver_updater.py
from __future__ import annotations
import subprocess
import os
from pathlib import Path
from typing import List, Callable, Optional

def check_dell_command_update() -> bool:
    paths = [
        Path(r"C:\Program Files\Dell\CommandUpdate\dcu-cli.exe"),
        Path(r"C:\Program Files (x86)\Dell\CommandUpdate\dcu-cli.exe"),
    ]
    return any(p.exists() for p in paths)

def run_process_with_live_output(cmd: List[str], callback: Callable[[str], None]) -> int:
    """Executa um processo e envia o output linha a linha para o callback."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="cp850", # Encoding padrão do CMD do Windows
            errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        if proc.stdout:
            for line in proc.stdout:
                line = line.strip()
                if line:
                    callback(line)
        proc.wait()
        return proc.returncode
    except Exception as e:
        callback(f"[ERRO FATAL] {e}")
        return -1

def run_dell_update(callback: Callable[[str], None]) -> List[str]:
    logs = []
    
    def log(msg):
        logs.append(msg)
        callback(msg)

    if not check_dell_command_update():
        log("[*] Dell Command Update não encontrado. Instalando via winget...")
        code = run_process_with_live_output(
            ["winget", "install", "--id", "Dell.CommandUpdate", "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements"],
            log
        )
        if code != 0 or not check_dell_command_update():
            log("[ERRO] Falha ao instalar o DCU. Baixe manualmente no site da Dell.")
            return logs

    dcu_cli = r"C:\Program Files\Dell\CommandUpdate\dcu-cli.exe"
    if not os.path.exists(dcu_cli):
        dcu_cli = r"C:\Program Files (x86)\Dell\CommandUpdate\dcu-cli.exe"

    log("[*] Iniciando varredura e atualização de drivers (Dell Command Update)...")
    # O DCU pode demorar, mas agora vemos o output dele em tempo real
    code = run_process_with_live_output([dcu_cli, "/applyUpdates", "-silent", "-reboot=disable"], log)
    
    if code == 0:
        log("[OK] Atualização concluída com sucesso!")
    else:
        log(f"[AVISO] O DCU finalizou com código {code}.")
        
    return logs
