# leap_sys/cli/cmd_leap.py
"""
Interface CLI para Gerenciamento de KVM (Barrier / Deskflow / Input Leap).
Suporte a telemetria em tempo real, auditoria de socket TCP e logging estruturado.
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
from datetime import datetime
import winreg
from typing import Dict, Optional, Tuple, List

from leap_sys.leap_engine import (
    leap_installer,
    leap_orchestration,
    leap_daemon,
    leap_discovery
)
from leap_sys.leap_platform.leap_windows import leap_firewall, leap_elevation

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "data" / "leap_logs"

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


def probe_kvm_socket(host: str, port: int = 24800, timeout: float = 1.5) -> Tuple[bool, float]:
    """Testa a conectividade da porta 24800 e mede a latência em milissegundos."""
    start_time = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = (time.perf_counter() - start_time) * 1000
            return True, latency_ms
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False, 0.0

def find_kvm_binary(role: str = "server") -> Optional[str]:
    """
    Localiza o binário KVM com prioridade absoluta para a versão Barrier portátil.
    """
    target_barrier = "barriers.exe" if role == "server" else "barrierc.exe"
    target_deskflow = "deskflow-core.exe"

    # 1. PRIORIDADE MÁXIMA: Binários portáteis no próprio repositório
    local_bin = PROJECT_ROOT / "bin" / "input-leap" / target_barrier
    if local_bin.exists():
        return str(local_bin)

    # 2. SEGUNDA PRIORIDADE: Barrier instalado no Windows (Program Files x86 / x64)
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_appdata = os.environ.get("LocalAppData", "")

    barrier_dirs = [
        Path(prog_files_x86) / "Barrier",
        Path(prog_files) / "Barrier",
        Path(local_appdata) / "Programs" / "Barrier",
    ]
    for directory in barrier_dirs:
        candidate = directory / target_barrier
        if candidate.exists():
            return str(candidate)

    # 3. TERCEIRA PRIORIDADE: Barrier no PATH
    in_path_barrier = shutil.which(target_barrier)
    if in_path_barrier:
        return in_path_barrier

    # 4. FALLBACK: Deskflow (se Barrier não estiver instalado)
    deskflow_dirs = [
        Path(prog_files) / "Deskflow",
        Path(prog_files_x86) / "Deskflow",
        Path(local_appdata) / "Programs" / "Deskflow",
    ]
    for directory in deskflow_dirs:
        candidate = directory / target_deskflow
        if candidate.exists():
            return str(candidate)

    in_path_deskflow = shutil.which(target_deskflow)
    if in_path_deskflow:
        return in_path_deskflow

    return None


def run_kvm_client(bin_path: str, server_address: str, client_name: str = "bluebaby") -> subprocess.Popen:
    """
    Executa o cliente KVM montando a linha de comando exata para Barrier ou Deskflow.
    """
    cmd = [bin_path]

    if "deskflow-core" in bin_path.lower():
        # Sintaxe do Deskflow 1.24+
        cmd.extend(["client", "-f", "--name", client_name, server_address])
    else:
        # Sintaxe do Barrier v2.4 (Estável)
        cmd.extend(["--no-daemon", "--name", client_name, server_address])

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


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
@click.argument("server", required=False)
@click.option("--name", default="bluebaby", help="Nome de tela deste cliente.")
@click.option("--port", default=24800, help="Porta do servidor KVM.")
def cmd_join(server, name, port):
    """Conecta este PC como CLIENTE ao Servidor KVM."""
    if not server:
        click.secho("[ERRO] Informe o IP do Servidor (ex: 100.113.157.27).", fg="red", bold=True)
        return

    client_bin = find_kvm_binary("client")
    if not client_bin:
        click.secho("[ERRO] Nenhum executável de cliente (barrierc.exe) localizado.", fg="red", bold=True)
        return

    server_address = f"{server}:{port}"
    click.echo(f"  • Binário Resolvido : {click.style(client_bin, fg='cyan')}")
    click.echo(f"  • Servidor Destino  : {click.style(server_address, bold=True, fg='yellow')}")
    click.echo(f"  • Nome de Tela      : {click.style(name, bold=True, fg='green')}")

    click.echo("\n[*] Conectando ao servidor KVM...")
    result = execute_kvm_client(client_bin, server_address, client_name=name)

    if result["success"]:
        click.secho(f"\n[SUCESSO] Cliente KVM ativo em segundo plano! (PID: {result['pid']})", fg="green", bold=True)
        click.echo(f"  • Log de Telemetria : {result['log_path']}")
        click.secho("👉 Mova o mouse da Amaranth além da borda direita para controlar esta tela!\n", fg="yellow")
    else:
        click.secho(f"\n[FALHA] O cliente KVM encerrou prematuramente (Código: {result['exit_code']}).", fg="red", bold=True)
        click.echo(f"  • Log detalhado gravado em: {result['log_path']}\n")
        click.secho("--- ÚLTIMAS LINHAS DO LOG DO CLIENTE ---", fg="red")
        lines = result["output"].splitlines()
        for line in lines[-12:]:
            click.echo(f"  {line}")
        click.secho("----------------------------------------\n", fg="red")

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

def build_client_command(bin_path: str, server_address: str, client_name: str = "bluebaby") -> List[str]:
    """Monta a linha de comando compatível e sem atrito de certificados SSL."""
    cmd = [bin_path]
    if "deskflow-core" in bin_path.lower():
        # Deskflow moderno
        cmd.extend(["client", "-f", "--disable-crypto", "--name", client_name, server_address])
    else:
        # Barrier v2.4 estável (Sem SSL, protegido pelo túnel Tailscale)
        cmd.extend(["--no-daemon", "--disable-crypto", "--name", client_name, server_address])
    return cmd

def execute_kvm_client(bin_path: str, server_address: str, client_name: str = "bluebaby") -> Dict:
    """Executa o cliente KVM com captura forense de logs e monitoramento."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"client_{timestamp}.log"

    cmd = build_client_command(bin_path, server_address, client_name)
    cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)

    header = (
        f"=====================================================\n"
        f"SYSUTILS KVM CLIENT TELEMETRY LOG\n"
        f"Data/Hora : {datetime.now().isoformat()}\n"
        f"Binário   : {bin_path}\n"
        f"Alvo      : {server_address}\n"
        f"Tela      : {client_name}\n"
        f"Comando   : {cmd_str}\n"
        f"=====================================================\n\n"
    )
    log_file.write_text(header, encoding="utf-8")

    try:
        # Redireciona stdout e stderr para o arquivo de log persistente
        with open(log_file, "a", encoding="utf-8", errors="replace") as f_log:
            proc = subprocess.Popen(
                cmd,
                stdout=f_log,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

        # Aguarda brevemente para checar se o processo continuou ativo
        time.sleep(1.2)
        exit_code = proc.poll()

        is_running = exit_code is None
        log_content = log_file.read_text(encoding="utf-8", errors="replace")

        return {
            "success": is_running,
            "pid": proc.pid if is_running else None,
            "exit_code": exit_code,
            "log_path": str(log_file),
            "cmd_str": cmd_str,
            "output": log_content,
        }
    except Exception as e:
        return {
            "success": False,
            "pid": None,
            "exit_code": -1,
            "log_path": str(log_file),
            "cmd_str": cmd_str,
            "output": f"Falha catastrófica ao iniciar subprocesso: {e}",
        }

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
    """🧙 Assistente Inteligente KVM: Conecta Amaranth e Bluebaby com telemetria."""
    hostname = socket.gethostname().lower()
    is_amaranth = "amaranth" in hostname

    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 🖱️  SYSUTILS LEAP AUTO — MOUSE & TECLADO COMPARTILHADOS", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    # 1. ESTAÇÃO AMARANTH (SERVIDOR / HOST)
    if is_amaranth:
        click.echo(f"  • Papel Detectado : {click.style('SERVIDOR MASTER (Amaranth)', bold=True, fg='green')}")
        click.echo("  • Função          : Compartilhar mouse e teclado físicos com a Bluebaby.")

        bin_server = find_kvm_binary("server")
        if not bin_server:
            click.secho("\n[ERRO] Nenhum binário de Servidor (barriers.exe) localizado.", fg="red", bold=True)
            raise SystemExit(1)

        click.echo(f"  • Motor KVM       : {click.style(bin_server, fg='cyan')}")
        click.echo("\n[*] Iniciando servidor KVM na porta 24800...")

        host_cmd = cli.commands.get("host")
        if host_cmd:
            ctx.invoke(host_cmd, client="bluebaby", port=24800)
        return

    # 2. ESTAÇÃO BLUEBABY (CLIENTE / RECEPTOR)
    click.echo(f"  • Papel Detectado : {click.style('CLIENTE RECEPTOR (Bluebaby)', bold=True, fg='yellow')}")
    click.echo("  • Função          : Receber comandos de mouse e teclado da Amaranth.")

    bin_client = find_kvm_binary("client")
    if not bin_client:
        click.secho("\n[ERRO] Nenhum binário de Cliente (barrierc.exe) localizado.", fg="red", bold=True)
        raise SystemExit(1)

    click.echo(f"  • Motor KVM       : {click.style(bin_client, fg='cyan')}")

    candidate_ips = ["100.113.157.27", "192.168.18.52"]
    server_ip = None

    click.echo("\n[*] Auditando porta 24800 no Servidor Amaranth...")
    for ip in candidate_ips:
        click.echo(f"    • Testando {ip}:24800...", nl=False)
        alive, latency = probe_kvm_socket(ip, port=24800, timeout=1.5)
        if alive:
            click.secho(f" [RESPONDENDO! Latência: {latency:.1f}ms]", fg="green", bold=True)
            server_ip = ip
            break
        else:
            click.secho(" [fechada]", fg="yellow")

    if not server_ip:
        click.secho("\n[AVISO] Amaranth não respondeu na porta 24800.", fg="yellow")
        server_ip = click.prompt("Digite o IP do servidor manualmente", default="100.113.157.27")

    # Invocação unificada e segura do comando join
    join_cmd = cli.commands.get("join")
    if join_cmd:
        ctx.invoke(join_cmd, server=server_ip, name="bluebaby", port=24800)

