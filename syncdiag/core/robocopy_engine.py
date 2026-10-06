# syncdiag/core/robocopy_engine.py
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Exclusões fundamentais para sincronização de repositórios/código entre máquinas distintas
DEFAULT_EXCLUDE_DIRS = [
    "venv", ".venv", "__pycache__", ".git", "node_modules",
    ".doxoade", ".doxoade_cache", ".pytest_cache", "build", "dist",
    "$RECYCLE.BIN", "System Volume Information"
]

DEFAULT_EXCLUDE_FILES = [
    "*.pyc", "*.pyo", "*.tmp", "*.bak", "*.swp", "*.lock",
    "thumbs.db", "desktop.ini", "*.db-wal", "*.db-shm"
]

_BIT_MEANINGS = {
    1: "arquivos copiados com sucesso",
    2: "arquivos extras removidos do destino (mirror)",
    4: "mismatches detectados",
}

def describe_exit_code(code: int) -> str:
    if code >= 16:
        return "ERRO FATAL: Robocopy não conseguiu acessar origem ou destino."
    if code >= 8:
        return "FALHA: Um ou mais arquivos não puderam ser copiados. Verifique permissões."
    if code == 0:
        return "Tudo atualizado: Origem e destino já estavam 100% sincronizados."
    parts = [msg for bit, msg in _BIT_MEANINGS.items() if code & bit]
    return "; ".join(parts) if parts else f"Sincronização finalizada (Código {code})."

def build_command(
    origem: str,
    destino: str,
    log_path: Path,
    threads: int = 16,
    retries: int = 2,
    wait: int = 3,
    dry_run: bool = False,
    excludes_dir: Optional[List[str]] = None,
    excludes_file: Optional[List[str]] = None,
) -> List[str]:
    cmd = [
        "robocopy",
        origem,
        destino,
        "/MIR",           # Espelhamento (cria, atualiza e remove órfãos no destino)
        "/FFT",           # Tolerância de 2s nos timestamps (essencial para SMB/Windows)
        f"/MT:{threads}", # Multi-threading para throughput máximo
        f"/R:{retries}",  # Máximo de tentativas em arquivos bloqueados
        f"/W:{wait}",     # Espera entre retentativas em segundos
        f"/LOG:{log_path}", # Salva log completo em disco
        "/TEE",           # Mostra o log no console em tempo real
        "/NP",            # Remove porcentagens poluídas no terminal
    ]

    if dry_run:
        cmd.append("/L")

    # Diretórios ignorados
    all_xd = list(DEFAULT_EXCLUDE_DIRS)
    if excludes_dir:
        all_xd.extend(excludes_dir)
    cmd.append("/XD")
    cmd.extend(list(set(all_xd)))

    # Arquivos ignorados
    all_xf = list(DEFAULT_EXCLUDE_FILES)
    if excludes_file:
        all_xf.extend(excludes_file)
    cmd.append("/XF")
    cmd.extend(list(set(all_xf)))

    return cmd

def run_mirror(
    origem: str,
    destino: str,
    log_dir: Path,
    threads: int = 16,
    retries: int = 2,
    wait: int = 3,
    dry_run: bool = False,
    excludes_dir: Optional[List[str]] = None,
    excludes_file: Optional[List[str]] = None,
) -> Dict:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"sync_{timestamp}.log"

    cmd = build_command(
        origem=origem,
        destino=destino,
        log_path=log_path,
        threads=threads,
        retries=retries,
        wait=wait,
        dry_run=dry_run,
        excludes_dir=excludes_dir,
        excludes_file=excludes_file,
    )

    # Execução com streaming em tempo real: o terminal não trava durante o processo
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    for line in iter(proc.stdout.readline, ''):
        clean = line.strip()
        if clean and not clean.startswith("-------------------------------------------------------------------------------"):
            print(f"  [ROBOCOPY] {clean}")
            sys.stdout.flush()

    proc.stdout.close()
    return_code = proc.wait()

    return {
        "exit_code": return_code,
        "success": return_code < 8,
        "description": describe_exit_code(return_code),
        "log_path": str(log_path),
        "cmd": " ".join(cmd),
        "dry_run": dry_run,
    }
