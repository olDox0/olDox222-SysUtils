# leap_sys/cli/cmd_leap.py
"""
Interface CLI para o LeapSys KVM (Input Leap / Barrier / Deskflow).
Suporta auto-instalação do Visual C++ Redistributable v14.50+, Deskflow e Doxly.
"""
from __future__ import annotations

import configparser
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
CLIENT_CONF_PATH = Path.home() / ".doxoade" / "deskflow_client.conf"
SERVER_CONF_PATH = Path.home() / ".doxoade" / "deskflow_server.conf"
DESKFLOW_TLS_CERT = Path(r"C:\ProgramData\Deskflow\tls\deskflow.pem")

# URLs Oficiais Microsoft e Deskflow
VCREDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
DESKFLOW_MSI_URL = "https://github.com/deskflow/deskflow/releases/download/v1.26.0/deskflow-1.26.0-win-x64.msi"


# ═══════════════════════════════════════════════════════════════
# AUTO-ELEVAÇÃO UAC E FIREWALL
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
        'netsh advfirewall firewall add rule name="Deskflow KVM In 24800" dir=in action=allow protocol=TCP localport=24800 profile=any',
        'netsh advfirewall firewall add rule name="Deskflow KVM Out 24800" dir=out action=allow protocol=TCP localport=24800 profile=any',
    ]
    for r in rules:
        subprocess.run(r, capture_output=True, shell=True)


def ensure_deskflow_tls_cert():
    r"""Garante a existência do certificado base em C:\ProgramData\Deskflow\tls\deskflow.pem."""
    if DESKFLOW_TLS_CERT.exists():
        return

    DESKFLOW_TLS_CERT.parent.mkdir(parents=True, exist_ok=True)
    openssl_bin = shutil.which("openssl")
    if not openssl_bin:
        for candidate in [
            r"C:\Program Files\Git\usr\bin\openssl.exe",
            r"C:\winlibs\mingw64\bin\openssl.exe",
        ]:
            if Path(candidate).exists():
                openssl_bin = candidate
                break

    if openssl_bin:
        cmd = [
            openssl_bin, "req", "-x509", "-nodes", "-days", "3650",
            "-subj", "//CN=Deskflow", "-newkey", "rsa:2048",
            "-keyout", str(DESKFLOW_TLS_CERT), "-out", str(DESKFLOW_TLS_CERT)
        ]
        subprocess.run(cmd, capture_output=True, shell=False)


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
    for target in ["deskflow-core.exe", "deskflow-server.exe", "barriers.exe", "input-leaps.exe"]:
        if target.lower() in proc.stdout.lower():
            return target
    return None


def write_deskflow_client_conf(server_ip: str, port: int = 24800) -> Path:
    CLIENT_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"[client]\n"
        f"remoteHost={server_ip}\n"
        f"port={port}\n\n"
        f"[security]\n"
        f"tlsEnabled=false\n"
        f"checkPeerFingerprints=false\n"
    )
    CLIENT_CONF_PATH.write_text(content, encoding="utf-8")

    appdata = os.environ.get("APPDATA")
    if appdata:
        try:
            user_conf = Path(appdata) / "Deskflow" / "Deskflow.conf"
            user_conf.parent.mkdir(parents=True, exist_ok=True)
            cfg = configparser.ConfigParser()
            if user_conf.exists():
                cfg.read(str(user_conf), encoding="utf-8")
            if not cfg.has_section("client"):
                cfg.add_section("client")
            if not cfg.has_section("security"):
                cfg.add_section("security")
            cfg.set("client", "remoteHost", server_ip)
            cfg.set("client", "port", str(port))
            cfg.set("security", "tlsEnabled", "false")
            cfg.set("security", "checkPeerFingerprints", "false")
            with open(user_conf, "w", encoding="utf-8") as f:
                cfg.write(f)
        except Exception:
            pass

    return CLIENT_CONF_PATH


def find_leap_binary(role: str = "any") -> Optional[str]:
    names_to_check = []
    if role in ("client", "any"):
        names_to_check.extend(["deskflow-core", "deskflow-client", "input-leapc", "barrierc"])
    if role in ("server", "any"):
        names_to_check.extend(["deskflow-core", "deskflow-server", "input-leaps", "barriers"])

    for name in names_to_check:
        found = shutil.which(name)
        if found:
            return found

    for name in names_to_check:
        cmd = f'powershell -NoProfile -Command "(Get-Process -Name \'{name}\' -ErrorAction SilentlyContinue).Path"'
        p = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        out = p.stdout.strip().splitlines()
        if out and out[0] and Path(out[0]).exists():
            return out[0]

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
    """LeapSys — Compartilhamento de Mouse & Teclado (Input Leap / Barrier / Deskflow)."""
    pass


@cli.command("setup")
@click.option("--force", is_flag=True, help="Força a reinstalação.")
def leap_setup(force):
    """Instala dependências do Visual C++ e o Deskflow oficial sob Administrador."""
    request_elevation()

    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 📦 SYSUTILS LEAP SETUP — INSTALAÇÃO AUTOMÁTICA COMPLETA", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    hostname = socket.gethostname()
    click.echo(f"  • Estação Atual : {click.style(hostname, bold=True, fg='green')}")

    # 1. PASSO CRÍTICO: Instalação do Visual C++ Redistributable v14.50+ (Pré-requisito do Deskflow)
    vcredist_exe = DOWNLOADS_DIR / "vc_redist.x64.exe"
    click.echo("\n[1/3] Verificando Microsoft Visual C++ Redistributable (v14.50+)...")
    if not vcredist_exe.exists() or force:
        success = download_with_progress(VCREDIST_URL, vcredist_exe, "[*] Baixando Visual C++ Redistributable")
        if not success:
            click.secho("[ERRO] Falha ao baixar o Visual C++ da Microsoft.", fg="red")
            raise SystemExit(1)
    else:
        click.echo("  ✔ Instalador do Visual C++ em cache.")

    click.echo("[*] Instalando bibliotecas do Visual C++ no Windows...")
    vc_cmd = [str(vcredist_exe), "/install", "/passive", "/norestart"]
    subprocess.run(vc_cmd, capture_output=True)
    click.secho("  ✔ Microsoft Visual C++ v14.50+ instalado com sucesso!", fg="green")

    # 2. Instalação do Deskflow
    click.echo("\n[2/3] Instalando Deskflow v1.26.0 (Protocolo 1.8)...")
    msi_path = DOWNLOADS_DIR / "deskflow-1.26.0-win-x64.msi"
    if not msi_path.exists() or force:
        success = download_with_progress(DESKFLOW_MSI_URL, msi_path, "[*] Baixando Deskflow (.msi)")
        if not success:
            click.secho("[ERRO] Falha ao baixar o Deskflow.", fg="red")
            raise SystemExit(1)
    else:
        click.echo("  ✔ Instalador do Deskflow em cache.")

    # Executa o MSI via PowerShell com RunAs para garantir permissão total
    ps_install = f'Start-Process msiexec.exe -ArgumentList \'/i "{msi_path}" /qb /norestart\' -Verb RunAs -Wait'
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_install], capture_output=True)

    time.sleep(2)
    installed_bin = find_leap_binary(role="any")
    if installed_bin:
        click.secho(f"  ✔ Deskflow instalado em: {installed_bin}", fg="green", bold=True)
    else:
        click.secho("  [AVISO] Se uma janela do instalador estiver aberta, clique para concluir.", fg="yellow")

    # 3. Configurações de Rede e Certificado
    click.echo("\n[3/3] Liberando porta TCP 24800 e gerando certificados...")
    open_firewall_rules()
    ensure_deskflow_tls_cert()
    click.secho("  ✔ Firewall e certificados configurados!", fg="green")

    click.secho("\n[SUCESSO] Todos os pré-requisitos e o Deskflow estão instalados!", fg="green", bold=True)
    click.echo("👉 Agora execute 'sysutils leap auto' para iniciar o KVM.")
    click.secho("\n" + "=" * 65 + "\n", fg="cyan")


@cli.command("auto")
def leap_auto():
    """🧙 Assistente Inteligente: Auto-elevação, compatibilidade TLS e conexão direta."""
    request_elevation()

    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 🖱️  SYSUTILS LEAP AUTO — MOUSE & TECLADO INTELIGENTE", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    hostname = socket.gethostname().lower()
    is_server = "amaranth" in hostname

    if is_server:
        click.secho("  • Papel Detectado: SERVIDOR MASTER (Amaranth)", fg="green", bold=True)
        click.echo("  • Compartilhando teclado e mouse com: bluebaby\n")

        running = get_running_kvm_process()
        if running and "deskflow" in running.lower():
            click.secho(f"  ✔ Servidor KVM Deskflow já está em execução ({running})!", fg="green", bold=True)
            update_doxly_state(True, "host", "bluebaby", "192.168.18.52", 24800)
            click.echo("👉 Aguardando movimentação do mouse para a Bluebaby.")
            click.secho("\n" + "=" * 65 + "\n", fg="cyan")
            return

        bin_path = find_leap_binary(role="server")
        if not bin_path:
            click.secho("[ERRO] Binário de Servidor não encontrado.", fg="red", bold=True)
            click.echo("💡 Execute 'sysutils leap setup' para instalar o Visual C++ e o Deskflow.")
            raise SystemExit(1)

        click.echo(f"  • Binário Servidor: {click.style(Path(bin_path).name, fg='green')}")
        open_firewall_rules()

        config_path = Path.home() / ".doxoade" / "deskflow_server.conf"
        config_path.parent.mkdir(parents=True, exist_ok=True)
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

        click.echo(f"[*] Disparando Servidor KVM...")
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

        update_doxly_state(True, "host", "bluebaby", "192.168.18.52", 24800)
        click.secho("\n[OK] Servidor ativo e aguardando conexão da Bluebaby!", fg="green", bold=True)

    else:
        click.secho("  • Papel Detectado: CLIENTE SECUNDÁRIO (Bluebaby)", fg="yellow", bold=True)
        click.echo("  • Localizando servidor Amaranth...\n")

        bin_path = find_leap_binary(role="client")
        if not bin_path:
            click.secho("[ERRO] Binário de Cliente não encontrado.", fg="red", bold=True)
            click.echo("💡 Execute 'sysutils leap setup' para instalar o Visual C++ e o Deskflow.")
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

        ensure_deskflow_tls_cert()
        conf_file = write_deskflow_client_conf(target_ip, port=24800)

        bin_name = Path(bin_path).name.lower()
        if "deskflow-core" in bin_name:
            cmd = [bin_path, "client", "-s", str(conf_file)]
        else:
            cmd = [bin_path, "-f", "--name", "bluebaby", f"{target_ip}:24800"]

        click.echo("[*] Conectando ao servidor KVM (Deskflow -> Amaranth)...")
        subprocess.Popen(cmd)

        update_doxly_state(True, "client", "Amaranth", target_ip, 24800)
        click.secho("\n[OK] Cliente conectado com sucesso ao Amaranth!", fg="green", bold=True)
        click.echo("👉 Mova o mouse da Amaranth para a borda direita para controlar a Bluebaby.")

    click.secho("\n" + "=" * 65 + "\n", fg="cyan")


@cli.command("stop")
def leap_stop():
    """Encerra daemons do KVM e sincroniza com o Doxly."""
    for proc in ["deskflow-core.exe", "deskflow-client.exe", "deskflow-server.exe", "barrierc.exe", "barriers.exe", "input-leapc.exe", "input-leaps.exe"]:
        subprocess.run(f"taskkill /IM {proc} /F", capture_output=True, shell=True)

    update_doxly_state(False, "idle", "", "")
    click.secho("[OK] Processos do KVM encerrados.", fg="green")
