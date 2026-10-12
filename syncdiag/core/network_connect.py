# syncdiag/core/network_connect.py
"""
Módulo de Conexão de Rede SMB sobre Tailscale/LAN.
Gerencia testes de porta 445, credenciais cmdkey, mapeamento net use e Explorer.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_FILE = Path(__file__).resolve().parents[2] / "data" / "network_credentials.json"


def _find_tailscale_bin() -> Optional[str]:
    """Localiza o binário do Tailscale mesmo fora do PATH."""
    in_path = shutil.which("tailscale")
    if in_path:
        return in_path

    possible_paths = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Tailscale" / "tailscale.exe",
        Path(os.environ.get("LocalAppData", "")) / "Tailscale" / "tailscale.exe",
    ]
    for p in possible_paths:
        if p.exists():
            return str(p)
    return None


def probe_smb_port(host: str, port: int = 445, timeout: float = 2.0) -> bool:
    """Verifica se o host remoto responde na porta 445 sem congelar o sistema."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def get_tailscale_peers() -> List[Dict[str, str]]:
    """Consulta máquinas ativas via CLI do Tailscale."""
    bin_path = _find_tailscale_bin()
    if not bin_path:
        return []

    try:
        proc = subprocess.run(
            [bin_path, "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if proc.returncode != 0:
            return []
    except Exception:
        return []

    peers = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            ip, name = parts[0], parts[1]
            status = "offline" if "offline" in line else "active"
            peers.append({"ip": ip, "name": name, "status": status})
    return peers


def save_host_credentials(host: str, user: str, password: str) -> None:
    """Salva credenciais em cofre local para conexão automática."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    data[host] = {"user": user, "password": password}
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_saved_credentials(host: str) -> Tuple[Optional[str], Optional[str]]:
    """Recupera credenciais salvas para um host."""
    if not CONFIG_FILE.exists():
        return None, None
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        cred = data.get(host)
        if cred:
            return cred.get("user"), cred.get("password")
    except Exception:
        pass
    return None, None


def register_credentials(target: str, user: str, password: Optional[str] = None) -> bool:
    """Registra credenciais no Windows Credential Manager via cmdkey."""
    cmd = ["cmdkey", f"/add:{target}", f"/user:{user}"]
    if password:
        cmd.append(f"/pass:{password}")

    proc = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    return proc.returncode == 0


def mount_network_drive(
    unc_path: str,
    drive_letter: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    persistent: bool = True,
    host: Optional[str] = None,
) -> Tuple[bool, str]:
    """Mapeia pasta compartilhada via net use blindado contra erros de domínio e espaços."""
    target = drive_letter if drive_letter else unc_path
    cmd = ["net", "use", target, unc_path]

    # Previne erro de domínio: prefixa o host remoto caso não tenha
    formatted_user = user
    if formatted_user and host and ("\\" not in formatted_user):
        formatted_user = f"{host}\\{formatted_user}"

    if password is not None:
        cmd.append(password if password != "" else '""')

    if formatted_user:
        cmd.append(f"/USER:{formatted_user}")

    cmd.append(f"/PERSISTENT:{'YES' if persistent else 'NO'}")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )

    if proc.returncode == 0:
        return True, f"Compartilhamento '{unc_path}' conectado com sucesso!"

    err_msg = proc.stderr.strip() or proc.stdout.strip()
    return False, f"Falha ao conectar via 'net use': {err_msg}"


def unmount_network_drive(target: str) -> Tuple[bool, str]:
    """Desconecta a unidade de rede ou link montado."""
    cmd = ["net", "use", target, "/DELETE", "/YES"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if proc.returncode == 0:
        return True, f"Unidade/Caminho '{target}' desconectado com sucesso."
    return False, proc.stderr.strip() or proc.stdout.strip()


def open_in_explorer(target_path: str) -> None:
    """Abre o caminho montado no Windows Explorer nativo."""
    os.system(f'explorer.exe "{target_path}"')
