# syncdiag/core/robocopy_engine.py
from __future__ import annotations
import subprocess
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Zonas do Sistema que NUNCA podem ser destino de sincronização
CRITICAL_ZONES = [
    r"C:\\", r"C:", r"C:\WINDOWS", r"C:\PROGRAM FILES",
    r"C:\PROGRAM FILES (x86)", r"C:\USERS", r"C:\PROGRAMDATA"
]

DEFAULT_EXCLUDE_DIRS = [
    "venv", ".venv", "__pycache__", ".git", "node_modules",
    ".doxoade", ".doxoade_cache", ".pytest_cache", "build", "dist",
    "$RECYCLE.BIN", "System Volume Information", ".sync_trash"
]

DEFAULT_EXCLUDE_FILES = [
    "*.pyc", "*.pyo", "*.tmp", "*.bak", "*.swp", "*.lock",
    "thumbs.db", "desktop.ini", "*.db-wal", "*.db-shm"
]

_BIT_MEANINGS = {
    1: "arquivos copiados com sucesso",
    2: "arquivos extras processados no destino",
    4: "mismatches detectados",
}

def describe_exit_code(code: int) -> str:
    if code >= 16:
        return "ERRO FATAL: Robocopy não conseguiu acessar origem ou destino."
    if code >= 8:
        return "FALHA: Um ou mais arquivos não puderam ser copiados. Verifique permissões."
    if code == 0:
        return "Tudo atualizado: Origem e destino já estão 100% idênticos."
    parts = [msg for bit, msg in _BIT_MEANINGS.items() if code & bit]
    return "; ".join(parts) if parts else f"Sincronização finalizada (Código {code})."

def validate_safe_paths(origem: str, destino: str) -> tuple[bool, str]:
    """Impede espelhamentos acidentais em pastas de sistema do Windows."""
    dest_norm = os.path.abspath(destino).upper().rstrip("\\")
    orig_norm = os.path.abspath(origem).upper().rstrip("\\")

    for zone in CRITICAL_ZONES:
        zone_norm = zone.upper().rstrip("\\")
        if dest_norm == zone_norm:
            return False, f"ZONA CRÍTICA: O destino '{destino}' é uma pasta do sistema. Operação bloqueada!"
        if orig_norm == zone_norm:
            return False, f"ZONA CRÍTICA: A origem '{origem}' é uma raiz do sistema. Operação bloqueada!"

    return True, "Caminhos validados com segurança."

def preflight_check(origem: str, destino: str, dry_run: bool) -> tuple[bool, str]:
    """Testa permissão de escrita e acessibilidade real."""
    safe, msg = validate_safe_paths(origem, destino)
    if not safe:
        return False, msg

    origem_p = Path(origem)
    if not origem_p.exists() or not origem_p.is_dir():
        return False, f"Origem inválida ou inacessível: {origem}"

    # Garante que a origem não está vazia (proteção contra deleção acidental)
    try:
        sample = next(origem_p.iterdir(), None)
        if sample is None:
            return False, "Origem VAZIA! Abortando para evitar apagar arquivos no destino."
    except Exception as e:
        return False, f"Falha ao checar origem: {e}"

    # Teste de Escrita no Destino
    if not dry_run:
        destino_p = Path(destino)
        handshake_file = destino_p / ".dox_handshake.tmp"
        try:
            with open(handshake_file, "w", encoding="utf-8") as f:
                f.write("ok")
            if handshake_file.exists():
                handshake_file.unlink()
        except PermissionError:
            return False, f"ACESSO NEGADO no destino '{destino}'. Rode o icacls no Bluebaby."
        except Exception as e:
            return False, f"Destino inacessível na rede '{destino}': {e}"

    return True, "Preflight OK."

def build_command(
    origem: str,
    destino: str,
    log_path: Path,
    threads: int = 16,
    retries: int = 2,
    wait: int = 3,
    dry_run: bool = False,
    mirror_mode: bool = False,
    excludes_dir: Optional[List[str]] = None,
    excludes_file: Optional[List[str]] = None,
) -> List[str]:
    cmd = [
        "robocopy",
        origem,
        destino,
        "/FFT",           # Tolerância de timestamp para rede SMB
        f"/MT:{threads}", # Multi-threading
        f"/R:{retries}",
        f"/W:{wait}",
        f"/LOG:{log_path}",
        "/TEE",
        "/NP",
    ]

    # SE mirror_mode=True: Espelhamento com remoção de órfãos (/MIR)
    # SE mirror_mode=False (Padrão Seguro): Apenas cópia aditiva (/E), NUNCA DELETA
    if mirror_mode:
        cmd.append("/MIR")
    else:
        cmd.append("/E")

    if dry_run:
        cmd.append("/L")

    all_xd = list(DEFAULT_EXCLUDE_DIRS)
    if excludes_dir:
        all_xd.extend(excludes_dir)
    cmd.append("/XD")
    cmd.extend(list(set(all_xd)))

    all_xf = list(DEFAULT_EXCLUDE_FILES)
    if excludes_file:
        all_xf.extend(excludes_file)
    cmd.append("/XF")
    cmd.extend(list(set(all_xf)))

    return cmd

def get_sync_preview(
    origem: str,
    destino: str,
    log_dir: Path,
    threads: int = 16,
    mirror_mode: bool = False,
    excludes_dir: Optional[List[str]] = None,
    excludes_file: Optional[List[str]] = None,
) -> Dict:
    """Gera um diagnóstico prévio exato do que será copiado e do que seria deletado."""
    log_dir.mkdir(parents=True, exist_ok=True)
    preview_log = log_dir / "preview_dryrun.log"

    cmd = build_command(
        origem=origem,
        destino=destino,
        log_path=preview_log,
        threads=threads,
        dry_run=True,
        mirror_mode=mirror_mode,
        excludes_dir=excludes_dir,
        excludes_file=excludes_file,
    )

    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    # Analisa o sumário do Robocopy
    copied_files = 0
    copied_bytes = "0 B"
    extra_files = 0
    extras_list = []

    if preview_log.exists():
        lines = preview_log.read_text(encoding="utf-8", errors="replace").splitlines()
        for l in lines:
            if "*EXTRA File" in l or "*EXTRA Arquivo" in l:
                extra_files += 1
                extras_list.append(l.split()[-1])
            if "Arquivos:" in l or "Files :" in l:
                parts = l.split()
                if len(parts) >= 3:
                    try: copied_files = int(parts[2])
                    except: pass
                if len(parts) >= 6:
                    try: extra_files = int(parts[5])
                    except: pass
            if "Bytes :" in l or "Bytes:" in l:
                parts = l.split()
                if len(parts) >= 3:
                    copied_bytes = f"{parts[2]} {parts[3]}" if len(parts) >= 4 else parts[2]

    return {
        "success": res.returncode < 8,
        "copied_files": copied_files,
        "copied_bytes": copied_bytes,
        "extra_files": extra_files,
        "extras_list": extras_list[:10],
    }

def run_mirror(
    origem: str,
    destino: str,
    log_dir: Path,
    threads: int = 16,
    retries: int = 2,
    wait: int = 3,
    dry_run: bool = False,
    mirror_mode: bool = False,
    excludes_dir: Optional[List[str]] = None,
    excludes_file: Optional[List[str]] = None,
) -> Dict:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"sync_{timestamp}.log"

    ok, msg = preflight_check(origem, destino, dry_run=dry_run)
    if not ok:
        print(f"\033[31m\n[PRE-FLIGHT FALHOU] {msg}\033[0m")
        return {
            "exit_code": 16,
            "success": False,
            "description": msg,
            "log_path": str(log_path),
            "cmd": "",
            "dry_run": dry_run,
        }

    cmd = build_command(
        origem=origem,
        destino=destino,
        log_path=log_path,
        threads=threads,
        retries=retries,
        wait=wait,
        dry_run=dry_run,
        mirror_mode=mirror_mode,
        excludes_dir=excludes_dir,
        excludes_file=excludes_file,
    )

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
        if clean and not clean.startswith("----"):
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
