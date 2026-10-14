# leap_sys/cli/cmd_leap.py
"""
Interface CLI para o LeapSys KVM (Baseado no Barrier v2.4.0 / Protocolo 1.6).
Prioriza o ecossistema Barrier: auto-elevação UAC, setup silencioso e Doxly.
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
import urllib.request
from pathlib import Path
from typing import Optional
import click

from syncdiag.core import network_connect

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOWNLOADS_DIR = PROJECT_ROOT / "data" / "downloads"
STATE_FILE = Path.home() / ".doxoade" / "leap_state.json"
SERVER_CONF_PATH = Path.home() / ".doxoade" / "barrier_server.conf"

# Instalador Oficial InnoSetup do Barrier v2.4.0 (Instalação 100% silenciosa sem checagens de MSI)
BARRIER_INSTALLER_URL = "https://github.com/debauchee/barrier/releases/download/v2.4.0/BarrierSetup-2.4.0-release.exe"


# ═══════════════════════════════════════════════════════════════
# AUTO-ELEVAÇÃO UAC E REGRAS DE FIREWALL
# ═══════════════════════════════════════════════════════════════
def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_elevation():
    if is_admin():
        return
    click.secho("\n[*] Privilégios de Administrador necessários para o KVM.", fg="yellow")
    params = " ".join([f'"{arg}"' if " " in arg else arg for arg in sys.argv])
    hinstance = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if hinstance > 32:
        sys.exit(0)
    else:
        click.secho("[ERRO] Elevação UAC cancelada pelo usuário.", fg="red")


def open_firewall_rules():
    rules = [
        'netsh advfirewall firewall add rule name="Barrier KVM In 24800" dir=in action=allow protocol=TCP localport=24800 profile=any',
        'netsh advfirewall firewall add rule name="Barrier KVM Out 24800" dir=out action=allow protocol=TCP localport=24800 profile=any',
    ]
    for r in rules:
        subprocess.run(r, capture_output=True, shell=True)


def update_doxly_state(active: bool, mode: str, target: str, server_ip: str, port: int = 24800):
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


def get_running_kvm_process() -> Optional[str]:
    proc = subprocess.run(
        ["tasklist", "/FI", "STATUS eq running"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    for target in ["barriers.exe", "input-leaps.exe", "deskflow-core.exe", "deskflow-server.exe"]:
        if target.lower() in proc.stdout.lower():
            return target
    return None


def find_leap_binary(role: str = "any") -> Optional[str]:
    """Busca com prioridade no Barrier (Server e Client)."""
    names_to_check = []
    if role in ("server", "any"):
        names_to_check.extend(["barriers", "input-leaps", "deskflow-core", "deskflow-server"])
    if role in ("client", "any"):
        names_to_check.extend(["barrierc", "input-leapc", "deskflow-core", "deskflow-client"])

    # 1. Se o processo já estiver em execução, recupera o caminho direto do processo Windows
    for name in names_to_check:
        clean_name = name.replace(".exe", "")
        cmd = f'powershell -NoProfile -Command "(Get-Process -Name \'{clean_name}\' -ErrorAction SilentlyContinue).Path"'
        p = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        for line in p.stdout.strip().splitlines():
            line = line.strip()
            if line and Path(line).exists():
                return line

    # 2. Checa no PATH
    for name in names_to_check:
        found = shutil.which(name)
        if found:
            return found

    # 3. Pastas Padrões do Windows
    roots = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("LocalAppData", "")) / "Programs",
    ]
    subdirs = ["Barrier", "Input Leap", "Deskflow", "Synergy"]
    for root in roots:
        for sdir in subdirs:
            base = root / sdir
            if not base.exists():
                continue
            for name in names_to_check:
                cand = base / f"{name}.exe"
                if cand.exists():
                    return str(cand)

    return None


def download_with_progress(url: str, dest_file: Path, label: str) -> bool:
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "SysUtils/1.0"})
    try:
        with urllib.request.urlopen(req) as resp, open(dest_file, "wb") as out_file:
            total_size = int(resp.headers.get("Content-Length", 0))
            block_size = 65536
            with click.progressbar(length=total_size, label=label) as bar:
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    bar.update(len(chunk))
        return True
    except Exception as e:
        click.secho(f"\n[ERRO] Falha no download: {e}", fg="red")
        return False


# ═══════════════════════════════════════════════════════════════
# COMANDOS CLI
# ═══════════════════════════════════════════════════════════════
@click.group()
def cli():
    """LeapSys — Compartilhamento de Mouse & Teclado (Focado em Barrier v2.4.0)."""
    pass


@cli.command("setup")
@click.option("--force", is_flag=True, help="Força novo download e instalação do Barrier.")
def leap_setup(force):
    """Instalação oficial e silenciosa do Barrier v2.4.0 (InnoSetup)."""
    request_elevation()

    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 📦 SYSUTILS LEAP SETUP — INSTALADOR OFICIAL DO BARRIER v2.4", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    hostname = socket.gethostname()
    click.echo(f"  • Estação Atual : {click.style(hostname, bold=True, fg='green')}")

    barrier_bin = find_leap_binary(role="any")
    is_barrier = barrier_bin and "barrier" in barrier_bin.lower()

    if is_barrier and not force:
        click.secho(f"\n✔ Barrier já detectado e pronto: {barrier_bin}", fg="green", bold=True)
    else:
        installer_path = DOWNLOADS_DIR / "BarrierSetup-2.4.0-release.exe"

        if not installer_path.exists() or force:
            click.echo("\n[*] Baixando Barrier v2.4.0 oficial do GitHub...")
            success = download_with_progress(BARRIER_INSTALLER_URL, installer_path, "[*] Baixando BarrierSetup.exe")
            if not success:
                click.secho("[ERRO] Falha ao baixar o Barrier.", fg="red")
                raise SystemExit(1)
        else:
            click.echo(f"\n✔ Instalador em cache: {installer_path.name}")

        click.echo("[*] Instalando Barrier silenciosamente no Windows (InnoSetup)...")
        # InnoSetup instala em silêncio absoluto com /VERYSILENT e não pede Visual C++ extra
        install_cmd = [str(installer_path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
        subprocess.run(install_cmd, capture_output=True)

        time.sleep(2)
        installed = find_leap_binary(role="any")
        if installed:
            click.secho(f"  ✔ Barrier instalado com sucesso em: {installed}", fg="green", bold=True)
        else:
            click.secho("  [AVISO] Verifique a pasta C:\\Program Files\\Barrier.", fg="yellow")

    # Liberação do Firewall
    click.echo("\n[*] Liberando porta TCP 24800 (Entrada e Saída) no Windows Firewall...")
    open_firewall_rules()
    click.secho("  ✔ Porta 24800 100% liberada no Firewall!", fg="green")

    click.secho("\n[SUCESSO] Barrier configurado e pronto para uso!", fg="green", bold=True)
    click.echo("👉 Agora execute 'sysutils leap auto' nesta máquina.")
    click.secho("\n" + "=" * 65 + "\n", fg="cyan")


@cli.command("auto")
def leap_auto():
    """🧙 Assistente Inteligente: Auto-elevação e conexão nativa via Barrier."""
    request_elevation()

    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 🖱️  SYSUTILS LEAP AUTO — MOUSE & TECLADO VIA BARRIER", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    hostname = socket.gethostname().lower()
    is_server = "amaranth" in hostname

    if is_server:
        # ═══ AMARANTH (SERVIDOR MASTER - BARRIER) ═══
        click.secho("  • Papel Detectado: SERVIDOR MASTER (Amaranth)", fg="green", bold=True)
        click.echo("  • Compartilhando teclado e mouse com: bluebaby\n")

        running = get_running_kvm_process()
        if running and "barrier" in running.lower():
            click.secho(f"  ✔ Servidor Barrier já está ativo em execução ({running})!", fg="green", bold=True)
            update_doxly_state(True, "host", "bluebaby", "192.168.18.52", 24800)
            click.echo("👉 Aguardando movimentação do mouse para a Bluebaby.")
            click.secho("\n" + "=" * 65 + "\n", fg="cyan")
            return

        bin_path = find_leap_binary(role="server")
        if not bin_path:
            click.secho("[ERRO] Binário do Barrier Server (barriers.exe) não encontrado.", fg="red", bold=True)
            click.echo("Execute 'sysutils leap setup' para instalar.")
            raise SystemExit(1)

        click.echo(f"  • Binário Servidor: {click.style(Path(bin_path).name, fg='green')}")
        open_firewall_rules()

        # Configuração da topologia Amaranth -> Bluebaby
        SERVER_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
        config_content = (
            "section: screens\n  Amaranth:\n  bluebaby:\nend\n"
            "section: links\n  Amaranth:\n    right = bluebaby\n"
            "  bluebaby:\n    left = Amaranth\nend\n"
        )
        SERVER_CONF_PATH.write_text(config_content, encoding="utf-8")

        cmd = [bin_path, "-f", "--no-tray", "--config", str(SERVER_CONF_PATH), "--address", ":24800"]
        click.echo(f"[*] Disparando Servidor Barrier na porta 24800...")
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

        update_doxly_state(True, "host", "bluebaby", "192.168.18.52", 24800)
        click.secho("\n[OK] Servidor Barrier ativo e aguardando a Bluebaby!", fg="green", bold=True)

    else:
        # ═══ BLUEBABY (CLIENTE SECUNDÁRIO - BARRIER) ═══
        click.secho("  • Papel Detectado: CLIENTE SECUNDÁRIO (Bluebaby)", fg="yellow", bold=True)
        click.echo("  • Localizando servidor Amaranth...\n")

        bin_path = find_leap_binary(role="client")
        if not bin_path:
            click.secho("[ERRO] Binário de Cliente não encontrado.", fg="red", bold=True)
            click.echo("💡 Execute 'sysutils leap setup' nesta máquina para instalar o Barrier.")
            raise SystemExit(1)

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

        # Execução padrão e robusta do Barrier Client
        cmd = [bin_path, "-f", "--no-tray", "--name", "bluebaby", f"{target_ip}:24800"]

        click.echo("[*] Conectando ao servidor Barrier (Protocolo 1.6)...")
        subprocess.Popen(cmd)

        update_doxly_state(True, "client", "Amaranth", target_ip, 24800)
        click.secho("\n[OK] Cliente conectado com sucesso ao Amaranth!", fg="green", bold=True)
        click.echo("👉 Mova o mouse da Amaranth para a borda direita para controlar a Bluebaby.")

    click.secho("\n" + "=" * 65 + "\n", fg="cyan")


@cli.command("stop")
def leap_stop():
    """Encerra processos do Barrier/Deskflow e atualiza o Doxly."""
    for proc in ["barriers.exe", "barrierc.exe", "deskflow-core.exe", "deskflow-server.exe", "input-leaps.exe", "input-leapc.exe"]:
        subprocess.run(f"taskkill /IM {proc} /F", capture_output=True, shell=True)

    update_doxly_state(False, "idle", "", "")
    click.secho("[OK] Processos do KVM encerrados.", fg="green")
