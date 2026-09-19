# syncdiag/core/smb_share.py
"""
Gerencia compartilhamentos SMB (pasta de rede) no Windows via `net share`.

Usado pelo comando `sysutils sync share`, para permitir configurar o
compartilhamento da pasta de destino direto pelo terminal, sem precisar
navegar pelas telas de Propriedades > Compartilhamento do Windows.

Requer privilégios de Administrador — Windows recusa `net share`
sem elevação.
"""
import ctypes
import subprocess
from typing import Optional, List, Dict


def is_admin() -> bool:
    """Verifica se o processo atual está rodando com privilégios de Administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def create_share(name: str, path: str, user: Optional[str] = None) -> Dict:
    """
    Cria um compartilhamento SMB apontando para `path`, acessível como
    \\\\NOME-DO-PC\\name.

    Se `user` não for informado, concede acesso total a 'Everyone'
    (qualquer usuário que autentique na máquina via rede) — mais simples
    para um cenário de dois PCs pessoais atrás de uma VPN privada (Tailscale).
    """
    grant = f"{user},FULL" if user else "Everyone,FULL"
    cmd = ["net", "share", f"{name}={path}", f"/GRANT:{grant}"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "success": proc.returncode == 0,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "cmd": " ".join(cmd),
    }


def remove_share(name: str) -> Dict:
    """Remove um compartilhamento SMB pelo nome."""
    cmd = ["net", "share", name, "/DELETE", "/YES"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "success": proc.returncode == 0,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def list_shares() -> List[Dict]:
    """Lista os compartilhamentos SMB ativos na máquina local."""
    proc = subprocess.run(["net", "share"], capture_output=True, text=True)
    shares = []
    started = False
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("---"):
            started = True
            continue
        if not started or not stripped:
            continue
        low = stripped.lower()
        if low.startswith("o comando") or low.startswith("the command"):
            break
        parts = stripped.split(None, 2)
        if parts:
            shares.append({
                "name": parts[0],
                "path": parts[1] if len(parts) > 1 else "",
                "remark": parts[2] if len(parts) > 2 else "",
            })
    return shares
