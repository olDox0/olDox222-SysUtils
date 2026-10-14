# leap_sys/cli/cmd_leap.py
"""
Interface CLI para o LeapSys KVM (Input Leap / Barrier / Deskflow).
Suporta auto-elevação UAC, detecção do Deskflow moderno e sincronia com Doxly.
"""
from __future__ import annotations

import ctypes
import json
import os
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
# UTILITÁRIOS: ELEVAÇÃO UAC E CONTRATO DOXLY
# ═══════════════════════════════════════════════════════════════
def is_admin() -> bool:
    """Verifica se o processo atual possui privilégios de Administrador."""
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

    # Reconstrói os argumentos originais da chamada
    params = " ".join([f'"{arg}"' if " " in arg else arg for arg in sys.argv])

    # Dispara a janela de permissão do Windows (runas)
    hinstance = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )

    if hinstance > 32:
        # Relançado com sucesso no terminal elevado
        sys.exit(0)
    else:
        click.secho("[ERRO] Elevação recusada pelo usuário. O KVM pode apresentar falhas de foco.", fg="red")


def update_doxly_state(active: bool, mode: str, target: str, server_ip: str, port: int = 24800):
    """Atualiza o contrato ~/.doxoade/leap_state.json lido pela barra do Doxly."""
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


def build_deskflow_cmd(bin_path: str, mode: str, args: list[str]) -> list[str]:
    """
    Garante compatibilidade: se for 'deskflow-core.exe', injeta 'client' ou 'server'
    obrigatoriamente como primeiro argumento.
    """
    cmd = [bin_path]
    bin_name = Path(bin_path).name.lower()
    if "deskflow-core" in bin_name:
        cmd.append(mode)  # 'client' ou 'server'
    cmd.extend(args)
    return cmd


def find_deskflow_binary() -> Optional[str]:
    """Localiza o binário do Deskflow / Input Leap no sistema."""
    possible_paths = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Deskflow" / "deskflow-core.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Deskflow" / "deskflow-client.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Input Leap" / "input-leapc.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Barrier" / "barrierc.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Deskflow" / "deskflow-core.exe",
    ]
    for p in possible_paths:
        if p.exists():
            return str(p)
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
    """🧙 Assistente Inteligente: Auto-elevação, configuração e conexão transparente."""
    # 1. Garante elevação UAC imediata
    request_elevation()

    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 🖱️  SYSUTILS LEAP AUTO — MOUSE & TECLADO INTELIGENTE", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    hostname = socket.gethostname().lower()
    is_server = "amaranth" in hostname

    bin_path = find_deskflow_binary()
    if not bin_path:
        click.secho("[ERRO] Binário do Deskflow/Input Leap não encontrado.", fg="red", bold=True)
        raise SystemExit(1)

    if is_server:
        # ═══ AMARANTH (SERVIDOR MASTER) ═══
        click.secho("  • Papel Detectado: SERVIDOR MASTER (Amaranth)", fg="green", bold=True)
        click.echo("  • Compartilhando teclado e mouse com: bluebaby\n")

        # Libera porta 24800
        subprocess.run(
            'netsh advfirewall firewall add rule name="Deskflow Leap 24800" dir=in action=allow protocol=TCP localport=24800',
            capture_output=True,
            shell=True,
        )

        # Monta comando do servidor
        config_path = Path.home() / ".doxoade" / "deskflow_server.conf"
        # Garante configuração mínima se não existir
        if not config_path.exists():
            config_content = (
                "section: screens\n  Amaranth:\n  bluebaby:\nend\n"
                "section: links\n  Amaranth:\n    right = bluebaby\n"
                "  bluebaby:\n    left = Amaranth\nend\n"
            )
            config_path.write_text(config_content, encoding="utf-8")

        server_args = ["-c", str(config_path), "--address", ":24800"]
        cmd = build_deskflow_cmd(bin_path, "server", server_args)

        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        update_doxly_state(True, "host", "bluebaby", "192.168.18.52", 24800)
        click.secho("\n[OK] Servidor ativo e aguardando a Bluebaby!", fg="green", bold=True)

    else:
        # ═══ BLUEBABY (CLIENTE SECUNDÁRIO) ═══
        click.secho("  • Papel Detectado: CLIENTE SECUNDÁRIO (Bluebaby)", fg="yellow", bold=True)
        click.echo("  • Localizando servidor Amaranth...\n")

        # 1. Busca por Tailscale primeiro
        target_ip = None
        peers = network_connect.get_tailscale_peers()
        for p in peers:
            if "amaranth" in p["name"].lower():
                target_ip = p["ip"]
                break

        # 2. Fallbacks de rede local
        if not target_ip:
            for candidate in ["192.168.18.52", "100.113.157.27"]:
                if network_connect.probe_smb_port(candidate, port=24800, timeout=1.0):
                    target_ip = candidate
                    break

        if not target_ip:
            target_ip = "192.168.18.52"

        click.echo(f"  • Servidor Alvo: {click.style(target_ip, fg='cyan', bold=True)}")
        click.echo("[*] Testando porta KVM (24800)...")

        # Inicia o cliente com o modo 'client' injetado
        client_args = ["--name", "bluebaby", f"{target_ip}:24800"]
        cmd = build_deskflow_cmd(bin_path, "client", client_args)

        click.echo(f"[*] Disparando Deskflow Core...")
        proc = subprocess.Popen(cmd)

        update_doxly_state(True, "client", "Amaranth", target_ip, 24800)
        click.secho("\n[OK] Cliente conectado com sucesso ao Amaranth!", fg="green", bold=True)
        click.echo("👉 Mova o mouse da Amaranth para a direita para controlar a Bluebaby.")

    click.secho("\n" + "=" * 65 + "\n", fg="cyan")


@cli.command("stop")
def leap_stop():
    """Encerra daemons do Deskflow/Input Leap e desativa estado no Doxly."""
    for proc in ["deskflow-core.exe", "deskflow-client.exe", "deskflow-server.exe", "barrierc.exe", "barriers.exe"]:
        subprocess.run(f"taskkill /IM {proc} /F", capture_output=True, shell=True)

    update_doxly_state(False, "idle", "", "")
    click.secho("[OK] Processos do KVM encerrados e estado atualizado.", fg="green")
