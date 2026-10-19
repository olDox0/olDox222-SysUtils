# syncdiag/core/network_connect.py
"""
Módulo de Conexão de Rede SMB sobre Tailscale/LAN.
Gerencia testes de porta 445, credenciais cmdkey, mapeamento net use e Explorer.
"""
from __future__ import annotations

import json
import os
import shutil
import string
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_FILE = Path(__file__).resolve().parents[2] / "data" / "network_credentials.json"
PRESET_PROFILES = {
    "amaranth": {
        "peer_name": "bluebaby",
        "peer_hostname_hints": ["desktop-5np5bhe", "bluebaby"],
        "local_share_name": "Apricot",
        "local_folder_path": r"C:\SysUtils_Shared",
        "remote_share_name": "Bluebaby_Share",
    },
    "bluebaby": {
        "peer_name": "amaranth",
        "peer_hostname_hints": ["amaranth"],
        "local_share_name": "Bluebaby_Share",
        "local_folder_path": r"C:\SysUtils_Shared",
        "remote_share_name": "Apricot",
    },
}

def get_available_drive_letter() -> str:
    """Busca a próxima letra de unidade livre no Windows (começando de Z até D)."""
    used_letters = set()
    proc = subprocess.run(["net", "use"], capture_output=True, text=True, errors="replace")
    for line in proc.stdout.splitlines():
        for token in line.split():
            if len(token) == 2 and token[1] == ":" and token[0].isalpha():
                used_letters.add(token.upper())

    # Também checa letras de discos físicos
    for drive in string.ascii_uppercase:
        if os.path.exists(f"{drive}:"):
            used_letters.add(f"{drive}:")

    # Varre de Z para baixo procurando uma letra livre
    for letter in reversed(string.ascii_uppercase):
        candidate = f"{letter}:"
        if candidate not in used_letters and candidate not in ["A:", "B:", "C:"]:
            return candidate

    return "Z:"


def fix_uac_linked_connections() -> None:
    """
    Ativa EnableLinkedConnections no Registro do Windows.
    Garante que unidades mapeadas no terminal Administrador apareçam
    imediatamente no Windows Explorer sem o erro 'Z:\ não está disponível'.
    """
    cmd = (
        'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" '
        '/v EnableLinkedConnections /t REG_DWORD /d 1 /f'
    )
    try:
        subprocess.run(cmd, capture_output=True, text=True, shell=True)
    except Exception:
        pass


def identify_current_station() -> Tuple[str, Dict]:
    """Identifica se o computador atual é Amaranth ou Bluebaby."""
    hostname = socket.gethostname().lower()
    if "amaranth" in hostname:
        return "amaranth", PRESET_PROFILES["amaranth"]
    return "bluebaby", PRESET_PROFILES["bluebaby"]

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


def probe_smb_port(host: str, port: int = 445, timeout: float = 1.8, retries: int = 3) -> bool:
    """Verifica se o host responde na porta 445 com retries para absorver o despertar do Tailscale."""
    for attempt in range(retries):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            if attempt < retries - 1:
                time.sleep(1.0)
    return False

def cleanup_stale_mounts_for_unc(unc_path: str) -> List[str]:
    """
    Localiza e desconecta todas as unidades duplicadas ou zumbis 
    que apontem para o mesmo caminho UNC remoto.
    """
    removed_letters = []
    proc = subprocess.run(["net", "use"], capture_output=True, text=True, errors="replace")
    target_norm = unc_path.lower().rstrip("\\")

    for line in proc.stdout.splitlines():
        parts = line.split()
        for i, token in enumerate(parts):
            if len(token) == 2 and token[1] == ":" and token[0].isalpha():
                letter = token.upper()
                for candidate in parts[i + 1:]:
                    if candidate.startswith(r"\\") and candidate.lower().rstrip("\\") == target_norm:
                        subprocess.run(["net", "use", letter, "/DELETE", "/YES"], capture_output=True, text=True)
                        removed_letters.append(letter)
                        break
    return removed_letters

def get_preferred_drive_letter(preferred: str = "Z:") -> str:
    """Retorna a letra Z: preferencialmente; se ocupada por disco físico, busca a próxima livre."""
    # Se Z: não for um disco local físico (C:, D: de verdade), ela é a escolhida
    if not os.path.exists(preferred):
        return preferred

    # Se estiver ocupada por um mapeamento de rede antigo, será limpa pelo cleanup
    # Caso seja disco físico fixo, busca de Y para trás
    for letter in reversed(string.ascii_uppercase):
        candidate = f"{letter}:"
        if not os.path.exists(candidate) and candidate not in ["A:", "B:", "C:"]:
            return candidate

    return preferred

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
