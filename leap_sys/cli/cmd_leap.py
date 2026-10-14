# leap_sys/cli/cmd_leap.py
"""
Interface CLI para Gerenciamento de KVM (Barrier / Deskflow / Input Leap).
"""
from __future__ import annotations
import os
import socket
import click
import subprocess
import json
import time
import psutil
import shutil
from pathlib import Path
import winreg
from typing import Optional, Tuple, List

from leap_sys.leap_engine import (
    leap_installer,
    leap_orchestration,
    leap_daemon,
    leap_discovery
)
from leap_sys.leap_platform.leap_windows import leap_firewall, leap_elevation


def _get_installed_paths_from_registry() -> List[Path]:
    """Varre as chaves de Uninstall do Registro do Windows para achar pastas do Barrier/Deskflow."""
    found_dirs = []
    reg_roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for root, subkey in reg_roots:
        try:
            with winreg.OpenKey(root, subkey) as key:
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    try:
                        app_key_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, app_key_name) as app_key:
                            disp_name, _ = winreg.QueryValueEx(app_key, "DisplayName")
                            if any(tool in disp_name.lower() for tool in ["barrier", "deskflow", "input leap"]):
                                try:
                                    install_loc, _ = winreg.QueryValueEx(app_key, "InstallLocation")
                                    if install_loc:
                                        found_dirs.append(Path(install_loc))
                                except OSError:
                                    pass
                                try:
                                    icon_path, _ = winreg.QueryValueEx(app_key, "DisplayIcon")
                                    if icon_path:
                                        found_dirs.append(Path(icon_path).parent)
                                except OSError:
                                    pass
                    except OSError:
                        continue
        except OSError:
            continue

    return found_dirs


def find_kvm_binary(role: str = "server") -> Optional[str]:
    """Localiza qualquer binário KVM ativo (Barrier, Deskflow ou Input Leap)."""
    target_names = []
    if role == "server":
        target_names = ["barriers.exe", "deskflow-core.exe", "inputleaps.exe"]
    else:
        target_names = ["barrierc.exe", "deskflow-core.exe", "inputleapc.exe"]

    # 1. PATH do Sistema
    for name in target_names:
        in_path = shutil.which(name)
        if in_path:
            return in_path

    # 2. Varredura via Registro do Windows (Mais confiável)
    for reg_dir in _get_installed_paths_from_registry():
        for name in target_names:
            candidate = reg_dir / name
            if candidate.exists():
                return str(candidate)

    # 3. Varredura em pastas clássicas do sistema (x86 e x64)
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_appdata = os.environ.get("LocalAppData", "")
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")

    search_dirs = [
        Path(prog_files_x86) / "Barrier",
        Path(prog_files) / "Barrier",
        Path(prog_files_x86) / "Deskflow",
        Path(prog_files) / "Deskflow",
        Path(prog_files) / "Input Leap",
        Path(local_appdata) / "Programs" / "Barrier",
        Path(local_appdata) / "Programs" / "Deskflow",
        Path(program_data) / "Barrier",
    ]

    for directory in search_dirs:
        for name in target_names:
            candidate = directory / name
            if candidate.exists():
                return str(candidate)

    return 


def probe_kvm_port(host: str, port: int = 24800, timeout: float = 1.5) -> bool:
    """Verifica se a porta KVM está respondendo."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

@click.group(name="leap")
def cli():
    """LeapSys — Compartilhamento de Mouse & Teclado (Input Leap / Barrier / Deskflow)."""
    pass

@cli.command("setup")
def leap_setup():
    """Baixa e instala o Barrier v2.4 oficial com elevação UAC garantida."""
    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 📦 SYSUTILS LEAP SETUP — INSTALADOR OFICIAL DO BARRIER", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    installer_url = "https://github.com/debauchee/barrier/releases/download/v2.4.0/BarrierSetup-2.4.0-Release.exe"
    temp_dir = Path(os.environ.get("TEMP", "C:/Windows/Temp"))
    installer_path = temp_dir / "BarrierSetup-2.4.0.exe"

    click.echo("[*] Baixando instalador oficial do Barrier...")
    import urllib.request
    try:
        urllib.request.urlretrieve(installer_url, installer_path)
        click.secho("  ✔ Download concluído com sucesso!", fg="green")
    except Exception as e:
        click.secho(f"[ERRO] Falha ao baixar instalador: {e}", fg="red")
        return

    click.echo("\n[*] Solicitando permissão de Administrador para instalar...")
    click.echo("👉 Clique em 'SIM' na caixa do Windows que aparecer na tela!")

    # Executa com RunAs no PowerShell para garantir gravação em C:\Program Files
    ps_cmd = (
        f"Start-Process -FilePath '{installer_path}' "
        f"-ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-' "
        f"-Verb RunAs -Wait"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd])

    # Libera porta no Firewall
    click.echo("\n[*] Liberando porta TCP 24800 no Firewall do Windows...")
    fw_cmd = (
        'netsh advfirewall firewall add rule name="Barrier KVM 24800" '
        'dir=in action=allow protocol=TCP localport=24800'
    )
    subprocess.run(["powershell", "-Command", f"Start-Process cmd -ArgumentList '/c {fw_cmd}' -Verb RunAs -Wait"])

    bin_server = find_kvm_binary("server")
    if bin_server:
        click.secho(f"\n[SUCESSO] Barrier detectado em: {bin_server}", fg="green", bold=True)
        click.secho("👉 Agora execute 'sysutils leap auto' nesta máquina!\n", fg="yellow")
    else:
        click.secho("\n[AVISO] Verifique se o instalador concluiu em 'C:\\Program Files\\Barrier'.", fg="yellow")


@cli.command("host")
@click.option("--client", default=None, help="Hostname ou apelido do computador cliente (ex: bluebaby).")
@click.option("--pos", type=click.Choice(["right", "left", "above", "below"]), default="right", show_default=True,
              help="Posição física do cliente em relação a este servidor.")
@click.option("--port", default=24800, show_default=True, help="Porta de escuta TCP.")
@click.option("--no-firewall", is_flag=True, help="Pula verificação de regra no Windows Firewall.")
def cmd_host(client: str | None, pos: str, port: int, no_firewall: bool):
    """Inicia este PC como SERVIDOR (onde mouse e teclado estão conectados fisicamente)."""
    server_host = socket.gethostname()

    def _get_local_ips() -> list[tuple[str, str]]:
        ips = []
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    ips.append((iface, addr.address))
        return ips

    if not leap_installer.is_installed():
        click.secho("[!] Binários não encontrados. Executando auto-setup...", fg="yellow")
        ok, msg = leap_installer.ensure_binaries()
        if not ok:
            click.secho(f"[ERRO] {msg}", fg="red")
            raise click.Abort()

    if not client:
        click.echo(f"Computador Servidor atual: {click.style(server_host, bold=True, fg='cyan')}")
        client = click.prompt("Nome do computador cliente de destino (ex: bluebaby)")

    if not no_firewall:
        if not leap_firewall.is_port_open(port):
            click.secho(f"[*] Porta {port} fechada no Firewall do Windows. Solicitando liberação...", fg="yellow")
            if leap_elevation.is_admin():
                leap_firewall.open_firewall_port(port, "InputLeap_Server")
                click.secho(f"[OK] Porta {port} liberada no Firewall.", fg="green")
            else:
                click.secho("[AVISO] Rode o terminal como Administrador ou use '--no-firewall' se a porta já estiver aberta.", fg="yellow")

    click.secho(f"[*] Montando topologia: [{server_host}] ===({pos.upper()})===> [{client}]", fg="cyan")
    success, log = leap_orchestration.start_host(server_name=server_host, client_name=client, position=pos, port=port)
    if success:
        click.secho(f"\n[OK] Servidor KVM ativo em segundo plano na porta {port}!", fg="green", bold=True)
        click.echo("\n--- ENDEREÇOS DO SERVIDOR (AMARANTH) ---")
        for iface, ip in _get_local_ips():
            click.echo(f"  • {iface:<25} : {click.style(ip, fg='cyan', bold=True)}")
        click.echo("----------------------------------------")
        click.echo(f"👉 No outro computador ({client}), execute:")
        click.secho(f"   sysutils leap join <IP_ESCOLHIDO_ACIMA> --port {port}\n", fg="yellow", bold=True)
        _update_leap_state(
          active=True, 
          mode="host", 
          target=client, 
          server_ip="192.168.18.52", 
          port=port
        )
    else:
        click.secho(f"[FALHA] {log}", fg="red")

@cli.command("join")
@click.argument("server_target", required=False)
@click.option("--name", default=None, help="Nome de tela registrado no servidor (ex: bluebaby).")
@click.option("--port", default=24800, show_default=True, help="Porta do servidor.")
def cmd_join(server_target: str | None, name: str | None, port: int):
    """Conecta este PC como CLIENTE (receberá os comandos de mouse/teclado)."""
    if not leap_installer.is_installed():
        click.secho("[!] Binários não encontrados. Executando auto-setup...", fg="yellow")
        ok, msg = leap_installer.ensure_binaries()
        if not ok:
            click.secho(f"[ERRO] {msg}", fg="red")
            raise click.Abort()

    client_host = name or "bluebaby"

    if not server_target:
        click.secho("[ERRO] IP do servidor (Amaranth) é obrigatório para execução em background.", fg="red", bold=True)
        click.secho("Uso correto: sysutils leap join 192.168.18.52 --name bluebaby", fg="yellow")
        raise click.Abort()

    click.secho(f"[*] Conectando com nome de tela [{click.style(client_host, bold=True)}] ao servidor {server_target}:{port}...", fg="cyan")
    success, log = leap_orchestration.start_client(server_ip=server_target, client_name=client_host, port=port)
    if success:
        click.secho(f"[OK] Cliente Input Leap ativo em background com nome '{client_host}'!", fg="green", bold=True)
        _update_leap_state(
          active=True, 
          mode="client", 
          target=server_target, 
          server_ip=server_target, 
          port=port
        )
    else:
        click.secho(f"[FALHA] {log}", fg="red", bold=True)
        click.secho("💡 Dica: Verifique se o Firewall do Windows no Servidor permite a porta 24800.", fg="yellow")

@cli.command("status")
def cmd_status():
    """Verifica se os daemons do Input Leap estão rodando."""
    status = leap_daemon.get_running_status()
    click.echo("\n--- STATUS DO LEAP SYS ---")
    if status["server_running"]:
        click.secho(f"  ● Servidor: ATIVO (PID: {status['server_pids']})", fg="green", bold=True)
    else:
        click.echo("  ○ Servidor: Inativo")
    if status["client_running"]:
        click.secho(f"  ● Cliente:  ATIVO (PID: {status['client_pids']})", fg="green", bold=True)
    else:
        click.echo("  ○ Cliente:  Inativo")
    click.echo("--------------------------\n")

@cli.command("stop")
def cmd_stop():
    """Encerra todos os processos do Input Leap (Server e Client)."""
    killed = leap_daemon.stop_all()
    if killed > 0:
        _update_leap_state(active=False, mode="idle")
        click.secho(f"[OK] {killed} processo(s) do Input Leap finalizado(s).", fg="green")
    else:
        click.echo("[INFO] Nenhum processo ativo encontrado.")

@cli.command("firewall")
def cmd_firewall():
    """Cadastra regras de liberação de porta e executáveis no Firewall do Windows."""
    if not leap_elevation.is_admin():
        click.secho("[AVISO] Abra o terminal como Administrador para aplicar as regras no Firewall.", fg="yellow", bold=True)
    click.secho("[*] Cadastrando regras de liberação no Firewall do Windows...", fg="cyan")
    ok, logs = leap_firewall.authorize_firewall()
    for l in logs:
        click.echo(f"  {l}")
    if ok:
        click.secho("[SUCESSO] Firewall do Windows totalmente autorizado para o LeapSys.", fg="green", bold=True)

@cli.command("setup-ux")
def cmd_setup_ux():
    """Forja atalho soberano com permissão de Administrador."""
    click.secho("[*] Forjando Atalho Soberano na Área de Trabalho...", fg="cyan")
    ok, msg = leap_elevation.create_sovereign_shortcut()
    if ok:
        click.secho(f"✔ [SUCESSO] {msg}", fg="green", bold=True)
        click.secho("💡 Fixe este atalho na sua Barra de Tarefas. O Windows pedirá UAC automaticamente.", fg="yellow")
        click.secho("   O Leap/KVM funcionará perfeitamente sem travamentos de mouse/teclado.", fg="yellow")
    else:
        click.secho(f"❌ [FALHA] {msg}", fg="red", bold=True)

def _update_leap_state(active: bool, mode: str = "idle", target: str = "", server_ip: str = "", port: int = 24800):
    """Sincroniza o contrato soberano com o Doxly/Lite XL HUD em ~/.doxoade/leap_state.json."""
    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".")
    dox_dir = home / ".doxoade"
    dox_dir.mkdir(parents=True, exist_ok=True)
    state_file = dox_dir / "leap_state.json"
    
    data = {
        "active": active,
        "mode": mode,
        "target": target,
        "server_ip": server_ip,
        "port": port,
        "updated_at": time.time()
    }
    state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

def build_client_command(bin_path: str, server_ip: str, port: int = 24800, client_name: str = "bluebaby") -> list[str]:
    """Monta a linha de comando compatível com Deskflow moderno e Barrier/InputLeap."""
    cmd = [bin_path]

    # Se o executável for o deskflow-core unificado, o primeiro argumento TEM que ser 'client'
    if "deskflow-core" in bin_path.lower():
        cmd.append("client")
        cmd.extend(["-f", "--name", client_name, f"{server_ip}:{port}"])
    else:
        # Padrão legado (barrierc / inputleapc)
        cmd.extend(["--no-daemon", "--name", client_name, f"{server_ip}:{port}"])

    return cmd

def _probe_port(host: str, port: int = 24800, timeout: float = 1.5) -> bool:
    """Testa se o servidor KVM está aceitando conexões na porta."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


@cli.command("auto")
@click.pass_context
def leap_auto(ctx):
    """🧙 Assistente Inteligente KVM: Conecta Amaranth e Bluebaby automaticamente."""
    hostname = socket.gethostname().lower()
    is_amaranth = "amaranth" in hostname

    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 🖱️  SYSUTILS LEAP AUTO — MOUSE & TECLADO COMPARTILHADOS", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    # ═══════════════════════════════════════════════════════════
    # ESTAÇÃO 1: AMARANTH (SERVIDOR / HOST)
    # ═══════════════════════════════════════════════════════════
    if is_amaranth:
        click.echo(f"  • Papel Detectado : {click.style('SERVIDOR MASTER (Amaranth)', bold=True, fg='green')}")
        click.echo("  • Função          : Compartilhar mouse e teclado físicos com a Bluebaby.")

        bin_server = find_kvm_binary("server")
        if not bin_server:
            click.secho("\n[ERRO] Nenhum binário de Servidor (barriers.exe / deskflow-core.exe) localizado.", fg="red", bold=True)
            click.echo("👉 Execute: sysutils leap setup")
            raise SystemExit(1)

        click.echo(f"  • Motor KVM       : {click.style(bin_server, fg='cyan')}")
        click.echo("\n[*] Iniciando servidor KVM na porta 24800...")

        # Invocação segura via dicionário de comandos do Click (elimina NameError)
        host_cmd = cli.commands.get("host")
        if host_cmd:
            ctx.invoke(host_cmd, client="bluebaby", port=24800)
        else:
            click.secho("[ERRO] Subcomando 'host' não registrado no grupo CLI.", fg="red")
        return

    # ═══════════════════════════════════════════════════════════
    # ESTAÇÃO 2: BLUEBABY (CLIENTE / JOIN)
    # ═══════════════════════════════════════════════════════════
    click.echo(f"  • Papel Detectado : {click.style('CLIENTE RECEPTOR (Bluebaby)', bold=True, fg='yellow')}")
    click.echo("  • Função          : Receber comandos de mouse e teclado da Amaranth.")

    bin_client = find_kvm_binary("client")
    if not bin_client:
        click.secho("\n[ERRO] Nenhum binário de Cliente (barrierc.exe / deskflow-core.exe) localizado.", fg="red", bold=True)
        click.echo("👉 Execute: sysutils leap setup")
        raise SystemExit(1)

    click.echo(f"  • Motor KVM       : {click.style(bin_client, fg='cyan')}")

    # Prioriza o IP estável do Tailscale, depois IP local
    candidate_ips = ["100.113.157.27", "192.168.18.52"]
    server_ip = None

    click.echo("\n[*] Buscando Servidor Amaranth ativo na porta 24800...")
    for ip in candidate_ips:
        click.echo(f"    • Testando {ip}:24800...", nl=False)
        if probe_kvm_port(ip, port=24800, timeout=1.5):
            click.secho(" [RESPONDENDO!]", fg="green", bold=True)
            server_ip = ip
            break
        else:
            click.secho(" [fechada]", fg="yellow")

    if not server_ip:
        click.secho("\n[AVISO] Amaranth não respondeu nas portas habituais.", fg="yellow")
        click.echo("👉 Certifique-se de que rodou 'sysutils leap auto' na Amaranth primeiro.")
        server_ip = click.prompt("Digite o IP do servidor manualmente", default="100.113.157.27")

    click.secho(f"\n[*] Conectando Bluebaby ao Servidor em {server_ip}:24800...", fg="cyan")

    # Invocação segura via dicionário de comandos do Click (elimina NameError)
    join_cmd = cli.commands.get("join")
    if join_cmd:
        ctx.invoke(join_cmd, server_ip=server_ip, name="bluebaby", port=24800)
    else:
        click.secho("[ERRO] Subcomando 'join' não registrado no grupo CLI.", fg="red")
