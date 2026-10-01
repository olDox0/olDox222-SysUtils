# sysutils/leap_sys/leap_engine/leap_daemon.py
"""
Poseidon: Gestor de Processos em Background para Daemons KVM.
Suporte total a Deskflow (deskflow-core), Barrier e Input Leap.
"""
from __future__ import annotations
import subprocess
import os
import psutil
from pathlib import Path
from sysutils.leap_sys.leap_engine import leap_installer

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

TARGET_PROCESS_NAMES = {
    "deskflow-core.exe", "deskflow-server.exe", "deskflow-client.exe", "deskflow.exe",
    "barriers.exe", "barrierc.exe", "barrier.exe",
    "input-leaps.exe", "input-leapc.exe"
}

def get_running_status() -> dict:
    server_pids = []
    client_pids = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = (proc.info['name'] or '').lower()
            if name in ("deskflow-server.exe", "barriers.exe", "input-leaps.exe"):
                server_pids.append(proc.info['pid'])
            elif name in ("deskflow-client.exe", "barrierc.exe", "input-leapc.exe"):
                client_pids.append(proc.info['pid'])
            elif name == "deskflow-core.exe":
                cmd = " ".join(proc.info.get('cmdline') or []).lower()
                if "server" in cmd:
                    server_pids.append(proc.info['pid'])
                elif "client" in cmd:
                    client_pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "server_running": len(server_pids) > 0,
        "server_pids": server_pids,
        "client_running": len(client_pids) > 0,
        "client_pids": client_pids,
    }

def spawn_server(conf_path: Path, port: int, server_name: str, log_file: Path) -> subprocess.Popen:
    bin_path = leap_installer.find_server_binary()
    if not bin_path:
        raise FileNotFoundError("Binário do servidor KVM não localizado.")

    if bin_path.name.lower() == "deskflow-core.exe":
        cmd = [
            str(bin_path.resolve()),
            "server",
            "-s", str(conf_path.resolve())
        ]
    else:
        cmd = [
            str(bin_path.resolve()),
            "-f",
            "--disable-crypto",
            "--address", f":{port}",
            "-c", str(conf_path.resolve()),
            "--name", server_name
        ]

    out_fh = open(log_file, "a", encoding="utf-8")
    return subprocess.Popen(
        cmd,
        stdout=out_fh,
        stderr=out_fh,
        shell=False,
        creationflags=CREATE_NO_WINDOW
    )

def spawn_client(server_ip: str, port: int, client_name: str, log_file: Path) -> subprocess.Popen:
    bin_path = leap_installer.find_client_binary()
    if not bin_path:
        raise FileNotFoundError("Binário do cliente KVM não localizado.")

    if bin_path.name.lower() == "deskflow-core.exe":
        cmd = [
            str(bin_path.resolve()),
            "client",
            f"{server_ip}:{port}"
        ]
    else:
        cmd = [
            str(bin_path.resolve()),
            "-f",
            "--disable-crypto",
            "--name", client_name,
            f"{server_ip}:{port}"
        ]

    out_fh = open(log_file, "a", encoding="utf-8")
    return subprocess.Popen(
        cmd,
        stdout=out_fh,
        stderr=out_fh,
        shell=False,
        creationflags=CREATE_NO_WINDOW
    )

def stop_all() -> int:
    """Mata todos os processos KVM ativos e retorna a quantidade encerrada."""
    killed = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = (proc.info['name'] or '').lower()
            if name in TARGET_PROCESS_NAMES:
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed
