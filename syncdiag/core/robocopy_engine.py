# syncdiag/core/robocopy_engine.py
"""
Motor de sincronização one-way (mirror) via Robocopy.

Encapsula a chamada ao Robocopy nativo do Windows, incluindo a
decodificação da tabela de exit codes (bitmask, não convencional).
"""
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Robocopy usa exit codes como soma de bits:
#   0  = nada copiado, origem e destino já batiam
#   1  = arquivo(s) copiado(s) com sucesso
#   2  = arquivos extras no destino foram removidos (efeito do /MIR)
#   4  = alguns arquivos/pastas com mismatch (não puderam ser copiados)
#   8  = falha ao copiar alguns arquivos — checar o log
#   16 = erro fatal, robocopy não conseguiu nem iniciar
_BIT_MEANINGS = {
    1: "arquivo(s) copiado(s) com sucesso",
    2: "arquivos extras removidos do destino (mirror)",
    4: "alguns itens não puderam ser copiados (mismatch)",
}


def describe_exit_code(code: int) -> str:
    """Traduz o exit code do Robocopy em uma descrição legível."""
    if code >= 16:
        return "ERRO FATAL: robocopy não conseguiu acessar origem/destino."
    if code >= 8:
        return "FALHA: um ou mais arquivos não puderam ser copiados. Veja o log."
    if code == 0:
        return "Nada a fazer: origem e destino já estavam sincronizados."
    parts = [msg for bit, msg in _BIT_MEANINGS.items() if code & bit]
    return "; ".join(parts) if parts else f"Código {code} (não mapeado)."


def build_command(
    origem: str,
    destino: str,
    log_path: Path,
    threads: int = 16,
    retries: int = 3,
    wait: int = 5,
    dry_run: bool = False,
    excludes: Optional[List[str]] = None,
) -> List[str]:
    """Monta a linha de comando do robocopy. Não executa nada."""
    cmd = [
        "robocopy", origem, destino,
        "/MIR", "/Z",
        f"/MT:{threads}",
        f"/R:{retries}", f"/W:{wait}",
        f"/LOG:{log_path}", "/TEE", "/NP",
    ]
    if dry_run:
        cmd.append("/L")
    if excludes:
        cmd.append("/XD")
        cmd.extend(excludes)
    return cmd


def run_mirror(
    origem: str,
    destino: str,
    log_dir: Path,
    threads: int = 16,
    retries: int = 3,
    wait: int = 5,
    dry_run: bool = False,
    excludes: Optional[List[str]] = None,
) -> Dict:
    """
    Executa o mirror via Robocopy e retorna um dicionário com o resultado.
    Nunca levanta exceção por falha do robocopy em si (exit code >= 8);
    quem chama decide o que fazer com `result["success"]`.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"sync_{timestamp}.log"

    cmd = build_command(origem, destino, log_path, threads, retries, wait, dry_run, excludes)

    proc = subprocess.run(cmd, capture_output=True, text=True)

    return {
        "exit_code": proc.returncode,
        "success": proc.returncode < 8,
        "description": describe_exit_code(proc.returncode),
        "log_path": str(log_path),
        "cmd": " ".join(cmd),
        "dry_run": dry_run,
        "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
    }
