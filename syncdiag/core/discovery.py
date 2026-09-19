# syncdiag/core/discovery.py
"""
Descoberta de computadores e compartilhamentos na rede local (Windows).

Usado pelo wizard interativo de 'sync add' para ajudar a identificar
"a outra parte" (PC + share de destino) sem o usuário precisar
digitar caminhos UNC de cabeça.
"""
import re
import subprocess
from typing import List


def list_network_computers() -> List[str]:
    """Lista computadores visíveis no domínio/workgroup via `net view`."""
    try:
        proc = subprocess.run(
            ["net", "view"], capture_output=True, text=True, timeout=15
        )
    except Exception:
        return []

    computers = []
    for line in proc.stdout.splitlines():
        m = re.match(r"\\\\(\S+)", line.strip())
        if m:
            computers.append(m.group(1))
    return computers


def list_shares(computer: str) -> List[str]:
    """Lista compartilhamentos de um computador via `net view \\\\COMPUTADOR`."""
    try:
        proc = subprocess.run(
            ["net", "view", f"\\\\{computer}"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return []

    shares = []
    capture = False
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("---"):
            capture = True
            continue
        if not capture or not stripped:
            continue
        if stripped.lower().startswith("o comando") or stripped.lower().startswith("the command"):
            break
        first_token = stripped.split()[0]
        shares.append(first_token)
    return shares
