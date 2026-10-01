# sysutils/leap_sys/leap_engine/leap_installer.py
"""
Hefesto: Instalador e Auditor de Binários KVM (Deskflow Primário / Barrier Portátil).
Blindado contra espaços em diretórios (shell=False) e suporte nativo a Winget / MSI.
"""
from __future__ import annotations
import os
import sys
import shutil
import subprocess
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BIN_DIR = PROJECT_ROOT / "bin" / "input-leap"

# Coloque BIN_DIR como primeiro item absoluto:
SYSTEM_SEARCH_DIRS = [
    BIN_DIR,  # <- Prioridade 1: sempre usar os binários portáteis do projeto!
    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Barrier",
    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Deskflow",
]

# E garanta que barrierc.exe vem antes de deskflow-core.exe:
CLIENT_NAMES = [
    "barrierc.exe", "input-leapc.exe", "deskflow-client.exe", "deskflow-core.exe"
]

SERVER_NAMES = [
    "barriers.exe", "barrier.exe", "input-leaps.exe", "deskflow-server.exe", "deskflow-core.exe"
]

BARRIER_RELEASE_URL = (
    "https://github.com/debauchee/barrier/releases/download/v2.4.0/BarrierSetup-2.4.0-release.exe"
)

def find_server_binary() -> Path | None:
    for search_dir in SYSTEM_SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for name in SERVER_NAMES:
            p = search_dir / name
            if p.exists():
                return p
    return None

def find_client_binary() -> Path | None:
    for search_dir in SYSTEM_SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for name in CLIENT_NAMES:
            p = search_dir / name
            if p.exists():
                return p
    return None

def is_installed() -> bool:
    return find_server_binary() is not None and find_client_binary() is not None

def get_installed_info() -> dict[str, str]:
    srv = find_server_binary()
    cli = find_client_binary()
    return {
        "server": f"{srv.name} ({srv.parent})" if srv else "Ausente",
        "client": f"{cli.name} ({cli.parent})" if cli else "Ausente",
        "dir": str(BIN_DIR)
    }

def try_winget_install() -> bool:
    """Tenta instalar o Deskflow oficial via winget silenciosamente."""
    winget = shutil.which("winget")
    if not winget:
        return False
    print("[*] Ferramenta 'winget' detectada. Tentando instalar Deskflow oficial...")
    cmd = [
        winget, "install", "--id", "Deskflow.Deskflow",
        "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return res.returncode == 0 and is_installed()
    except Exception:
        return False

def ensure_binaries(force: bool = False) -> tuple[bool, str]:
    if not force and is_installed():
        info = get_installed_info()
        return True, f"Binários prontos: Servidor [{info['server']}] | Cliente [{info['client']}]"

    BIN_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Tentar Deskflow via Winget
    if try_winget_install():
        info = get_installed_info()
        return True, f"Deskflow instalado com sucesso via winget! Servidor: [{info['server']}]"

    # 2. Fallback: Download e extração portátil local protegida contra caminhos com espaço
    installer_exe = BIN_DIR / "barrier_installer_temp.exe"
    try:
        print(f"[*] Baixando pacote KVM portátil (Fallback seguro)...")
        print(f"    Origem: {BARRIER_RELEASE_URL}")
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        req = urllib.request.Request(BARRIER_RELEASE_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp, open(installer_exe, "wb") as out_f:
            out_f.write(resp.read())

        print(f"[*] Extraindo binários portáteis silenciosamente em:\n    {BIN_DIR}")
        
        # Invocação sem shell=True para o Windows não quebrar caminhos com espaços
        cmd = [
            str(installer_exe.resolve()),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/SP-",
            f"/DIR={str(BIN_DIR.resolve())}"
        ]
        res = subprocess.run(cmd, shell=False, capture_output=True, text=True)

        if installer_exe.exists():
            try: installer_exe.unlink()
            except Exception: pass

        if is_installed():
            info = get_installed_info()
            return True, f"Instalação finalizada com sucesso! Motores: {info['server']}"
        else:
            return False, f"Falha na extração. Detalhes: {res.stderr or res.stdout}"

    except Exception as e:
        if installer_exe.exists():
            try: installer_exe.unlink()
            except Exception: pass
        return False, f"Falha no download/extração: {e}"
