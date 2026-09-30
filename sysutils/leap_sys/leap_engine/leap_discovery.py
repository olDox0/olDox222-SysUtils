# sysutils/leap_sys/leap_engine/leap_discovery.py
"""
Anúbis: Sondagem rápida de socket TCP na rede local para detectar
instâncias do Input Leap ativas na porta padrão.
"""
from __future__ import annotations
import socket
import subprocess
import re

def test_tcp_connection(host: str, port: int, timeout: float = 0.8) -> bool:
    """Retorna True se conseguir conectar via socket TCP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def discover_server(port: int = 24800) -> str | None:
    """
    Sonda computadores conhecidos no ARP/Net View para ver quem está com a porta 24800 aberta.
    """
    candidates = []
    try:
        # Pega a tabela ARP local
        out = subprocess.check_output("arp -a", text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                ip = m.group(1)
                if not ip.startswith("255.") and not ip.startswith("224.") and not ip.endswith(".255"):
                    candidates.append(ip)
    except Exception:
        pass

    for ip in set(candidates):
        if test_tcp_connection(ip, port, timeout=0.3):
            return ip
    return None
