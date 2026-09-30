# sysutils/leap_sys/leap_platform/leap_windows/leap_firewall.py
"""
Regras do Firewall do Windows para o Input Leap via netsh.
"""
from __future__ import annotations
import subprocess

def is_port_open(port: int) -> bool:
    """Verifica se há regra de liberação de porta ativa."""
    try:
        cmd = f"netsh advfirewall firewall show rule name=all"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return str(port) in res.stdout
    except Exception:
        return False

def open_firewall_port(port: int, rule_name: str = "InputLeap_Port") -> bool:
    """Cria regra de entrada TCP no Windows Firewall."""
    try:
        cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port}'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.returncode == 0
    except Exception:
        return False
