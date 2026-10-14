# leap_sys/cli/cmd_leap.py
"""
Interface CLI para o LeapSys KVM (Input Leap / Barrier / Deskflow).
Suporta auto-elevação UAC, detecção universal de binários (Server/Client) e Doxly.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
import click

from syncdiag.core import network_connect

STATE_FILE = Path.home() / ".doxoade" / "leap_state.json"


# ═══════════════════════════════════════════════════════════════
# AUTO-ELEVAÇÃO UAC E INTEGRAÇÃO DOXLY
# ═══════════════════════════════════════════════════════════════
def is_admin() -> bool:
    """Verifica se o processo possui privilégios de Administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_elevation():
    """Solicita elevação de privilégios via UAC do Windows e relança o comando."""
    if is_admin():
        return

    click.secho("\n[*] Privilégios de Administrador necessários para o KVM.", fg="yellow")
    click.echo("[*] Solicitando elevação via UAC do Windows...")

    # Monta os argumentos para relançar
    params = " ".join([f'"{arg}"' if " " in arg else arg for arg in sys.argv])

    # Dispara a caixa do UAC
    hinstance = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )

    if hinstance > 32:
        sys.exit(0)  # Relançado com sucesso no terminal elevado
    else:
        click.secho("[ERRO] Elevação UAC cancelada pelo usuário.", fg="red")


def update_doxly_state(active: bool, mode: str, target: str, server_ip: str, port: int = 24800):
    """Atualiza o contrato ~/.doxoade/leap_state.json lido pelo Doxly Toolbar."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "active": active,
            "mode": mode,
            "target": target,
            "server_ip": server_ip,
            "port": port,
            "updated_at": int(time.time()),
        }
        STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def find_leap_binary(role: str = "any") -> Optional[str]:
    """
    Localiza o binário correto (Server ou Client) para Deskflow, Input Leap ou Barrier.
    """
    names_to_check = []
    if role in ("client", "any"):
        names_to_check.extend(["deskflow-core", "deskflow-client", "input-leapc", "barrierc"])
    if role in ("server", "any"):
        names_to_check.extend(["deskflow-core", "deskflow-server", "input-leaps", "barriers"])

    # 1. Verifica no PATH do sistema
    for name in names_to_check:
        found = shutil.which(name)
        if found:
            return found

    # 2. Varre pastas padrões de instalação no Windows
    roots = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("LocalAppData", "")) / "Programs",
    ]
    subdirs = ["Deskflow", "Input Leap", "Barrier", "Synergy"]

    for root in roots:
        for sdir in subdirs:
            base = root / sdir
            if not base.exists():
                continue
            for name in names_to_check:
                candidate = base / f"{name}.exe"
                if candidate.exists():
                    return str(candidate)

    return None


# ═══════════════════════════════════════════════════════════════
# GRUPO CLI LEAP
# ═══════════════════════════════════════════════════════════════
@click.group()
def cli():
    """LeapSys — Compartilhamento de Mouse & Teclado (Input Leap / Barrier / Deskflow)."""
    pass


@cli.command("auto")
def leap_auto():
    """🧙 Assistente Inteligente: Auto-elevação, configuração e conexão KVM."""
    # 1. Solicita UAC automaticamente se não for Admin
    request_elevation()

    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 🖱️  SYSUTILS LEAP AUTO — MOUSE & TECLADO INTELIGENTE", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    hostname = socket.gethostname().lower()
    is_server = "amaranth" in hostname

    if is_server:
        # ═══ AMARANTH (SERVIDOR MASTER) ═══
        click.secho("  • Papel Detectado: SERVIDOR MASTER (Amaranth)", fg="green", bold=True)
        click.echo("  • Compartilhando teclado e mouse com: bluebaby\n")

        bin_path = find_leap_binary(role="server")
        if not bin_path:
            click.secho("[ERRO] Binário de Servidor (input-leaps / barriers / deskflow) não encontrado.", fg="red", bold=True)
            raise SystemExit(1)

        # Garante regra no Firewall
        click.echo("[*] Garantindo porta 24800 liberada no Firewall...")
        subprocess.run(
            'netsh advfirewall firewall add rule name="Leap KVM 24800" dir=in action=allow protocol=TCP localport=24800',
            capture_output=True,
            shell=True,
        )

        # Garante arquivo de topologia
        config_path = Path.home() / ".doxoade" / "deskflow_server.conf"
        config_content = (
            "section: screens\n  Amaranth:\n  bluebaby:\nend\n"
            "section: links\n  Amaranth:\n    right = bluebaby\n"
            "  bluebaby:\n    left = Amaranth\nend\n"
        )
        config_path.write_text(config_content, encoding="utf-8")

        bin_name = Path(bin_path).name.lower()
        if "deskflow-core" in bin_name:
            cmd = [bin_path, "server", "-s", str(config_path), "--address", ":24800"]
        else:
            cmd = [bin_path, "-f", "--config", str(config_path), "--address", ":24800"]

        click.echo(f"[*] Disparando Servidor KVM: {Path(bin_path).name}...")
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

        update_doxly_state(True, "host", "bluebaby", "192.168.18.52", 24800)
        click.secho("\n[OK] Servidor ativo e aguardando conexão da Bluebaby!", fg="green", bold=True)

    else:
        # ═══ BLUEBABY (CLIENTE SECUNDÁRIO) ═══
        click.secho("  • Papel Detectado: CLIENTE SECUNDÁRIO (Bluebaby)", fg="yellow", bold=True)
        click.echo("  • Localizando servidor Amaranth...\n")

        bin_path = find_leap_binary(role="client")
        if not bin_path:
            click.secho("[ERRO] Binário de Cliente (deskflow-core / input-leapc) não encontrado.", fg="red", bold=True)
            raise SystemExit(1)

        # 1. Busca IP da Amaranth via Tailscale ou Wi-Fi
        target_ip = None
        peers = network_connect.get_tailscale_peers()
        for p in peers:
            if "amaranth" in p["name"].lower():
                target_ip = p["ip"]
                break

        if not target_ip:
            for candidate in ["192.168.18.52", "100.113.157.27"]:
                if network_connect.probe_smb_port(candidate, port=24800, timeout=1.0):
                    target_ip = candidate
                    break

        if not target_ip:
            target_ip = "192.168.18.52"

        click.echo(f"  • Servidor Alvo : {click.style(target_ip, fg='cyan', bold=True)}")
        click.echo(f"  • Binário KVM   : {click.style(Path(bin_path).name, fg='green')}")
        click.echo("[*] Testando porta KVM (24800)...")

        # 2. Constrói o comando do cliente com a sintaxe precisa
        bin_name = Path(bin_path).name.lower()
        if "deskflow-core" in bin_name:
            # Deskflow moderno: NÃO aceita flag --name
            cmd = [bin_path, "client", target_ip]
        else:
            # Barrier / Input Leap legados
            cmd = [bin_path, "-f", "--name", "bluebaby", f"{target_ip}:24800"]

        click.echo("[*] Conectando ao servidor...")
        subprocess.Popen(cmd)

        update_doxly_state(True, "client", "Amaranth", target_ip, 24800)
        click.secho("\n[OK] Cliente conectado com sucesso ao Amaranth!", fg="green", bold=True)
        click.echo("👉 Mova o mouse da Amaranth para a borda direita para controlar a Bluebaby.")

    click.secho("\n" + "=" * 65 + "\n", fg="cyan")


@cli.command("stop")
def leap_stop():
    """Encerra todos os daemons do KVM e sincroniza com o Doxly."""
    for proc in ["deskflow-core.exe", "deskflow-client.exe", "deskflow-server.exe", "barrierc.exe", "barriers.exe", "input-leapc.exe", "input-leaps.exe"]:
        subprocess.run(f"taskkill /IM {proc} /F", capture_output=True, shell=True)

    update_doxly_state(False, "idle", "", "")
    click.secho("[OK] Processos do KVM encerrados.", fg="green")
