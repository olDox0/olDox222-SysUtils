# sysutils/leap_sys/leap_platform/leap_windows/leap_firewall.py
"""
Regras do Firewall do Windows para o Input Leap via netsh.
Blindado contra UnicodeDecodeError (cp1252 / UTF-8).
"""
from __future__ import annotations
import subprocess

def is_port_open(port: int, rule_name: str = "InputLeap_Port") -> bool:
    """Verifica se a regra do Firewall já existe de forma instantânea."""
    try:
        cmd = f'netsh advfirewall firewall show rule name="{rule_name}"'
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return res.returncode == 0
    except Exception:
        return False

def open_firewall_port(port: int, rule_name: str = "InputLeap_Port") -> bool:
    """Cria regra de entrada TCP no Windows Firewall de forma segura."""
    try:
        cmd = f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport={port}'
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return res.returncode == 0
    except Exception:
        return False
