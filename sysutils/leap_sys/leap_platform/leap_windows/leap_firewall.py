# sysutils/leap_sys/leap_platform/leap_windows/leap_firewall.py
"""
Regras do Firewall do Windows 11 para o LeapSys / Barrier.
Registra regras de porta (24800) e regras diretas para os binários.
"""
from __future__ import annotations
import subprocess
from pathlib import Path
from sysutils.leap_sys.leap_engine import leap_installer

def authorize_firewall(port: int = 24800) -> tuple[bool, list[str]]:
    """
    Solicita ao Windows Firewall liberação completa para porta e binários.
    Requer terminal como Administrador.
    """
    logs = []
    cmds = [
        # 1. Regra de Entrada na Porta TCP 24800
        f'netsh advfirewall firewall add rule name="LeapSys_Port_In" dir=in action=allow protocol=TCP localport={port}',
        # 2. Regra de Saída na Porta TCP 24800
        f'netsh advfirewall firewall add rule name="LeapSys_Port_Out" dir=out action=allow protocol=TCP localport={port}',
    ]

    # 3. Liberação direta dos executáveis para evitar qualquer bloqueio de app no Win11
    srv_bin = leap_installer.find_server_binary()
    if srv_bin:
        cmds.append(f'netsh advfirewall firewall add rule name="LeapSys_Server_Bin" dir=in action=allow program="{str(srv_bin.resolve())}" enable=yes')
    
    cli_bin = leap_installer.find_client_binary()
    if cli_bin:
        cmds.append(f'netsh advfirewall firewall add rule name="LeapSys_Client_Bin" dir=in action=allow program="{str(cli_bin.resolve())}" enable=yes')
        cmds.append(f'netsh advfirewall firewall add rule name="LeapSys_Client_Out" dir=out action=allow program="{str(cli_bin.resolve())}" enable=yes')

    success = True
    for cmd in cmds:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            logs.append(f"[OK] {cmd.split('name=')[1].split(' ')[0]}")
        else:
            success = False
            logs.append(f"[FALHA] {res.stderr.strip() or 'Requer privilégios de Administrador'}")

    return success, logs

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
