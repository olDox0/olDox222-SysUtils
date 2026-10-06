# sysutils/leap_sys/leap_engine/leap_orchestration.py
"""
Atena: Orquestrador da ponte de execução, logs e lifecycle do Leap Sys.
"""
from __future__ import annotations
import time
from pathlib import Path
from leap_sys.leap_engine import leap_daemon, leap_config

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "leap"
LOG_DIR = DATA_DIR / "logs"

def start_host(server_name: str, client_name: str, position: str, port: int) -> tuple[bool, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "server.log"

    leap_daemon.stop_all()
    conf_path = leap_config.write_runtime_config(DATA_DIR, server_name, client_name, position)

    proc = leap_daemon.spawn_server(conf_path, port, server_name, log_file)
    time.sleep(1.0)

    if proc.poll() is not None:
        err = log_file.read_text(encoding="utf-8", errors="replace")[-500:] if log_file.exists() else "Erro desconhecido"
        return False, f"Falha ao iniciar o servidor. Saída do log:\n{err}"

    return True, f"Servidor rodando (PID: {proc.pid})"

def start_client(server_ip: str, client_name: str, port: int) -> tuple[bool, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "client.log"

    leap_daemon.stop_all()

    proc = leap_daemon.spawn_client(server_ip, port, client_name, log_file)
    time.sleep(1.0)

    if proc.poll() is not None:
        err = log_file.read_text(encoding="utf-8", errors="replace")[-500:] if log_file.exists() else "Erro desconhecido"
        return False, f"Falha ao iniciar o cliente. Saída do log:\n{err}"

    return True, f"Cliente rodando (PID: {proc.pid})"
