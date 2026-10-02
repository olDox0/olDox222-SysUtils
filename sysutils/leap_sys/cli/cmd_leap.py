# sysutils/leap_sys/cli/cmd_leap.py
"""
Interface de Linha de Comando (CLI) para LeapSys / Input Leap.
Comandos:
  - setup: Baixa/valida os binários portáteis headless (leaps/leapc).
  - host:  Inicia modo Servidor (computador onde o mouse/teclado físicos estão).
  - join:  Inicia modo Cliente (computador que recebe o cursor).
  - status: Verifica processos ativos e conectividade.
  - stop:  Encerra daemons do Input Leap.
"""
from __future__ import annotations
import os
import click
import socket
import psutil
from pathlib import Path
from sysutils.leap_sys.leap_engine import (
    leap_installer,
    leap_orchestration,
    leap_daemon,
    leap_discovery
)
from sysutils.leap_sys.leap_platform.leap_windows import leap_firewall, leap_elevation

@click.group(name="leap")
def cli():
    """LeapSys — Compartilhamento de Mouse & Teclado (Input Leap Engine)."""
    pass

@cli.command("setup")
@click.option("--force", is_flag=True, help="Força novo download mesmo se os binários existirem.")
def cmd_setup(force: bool):
    """Verifica e baixa os binários headless necessários."""
    click.secho("[*] Auditando binários do Input Leap...", fg="cyan")
    ok, msg = leap_installer.ensure_binaries(force=force)
    if ok:
        click.secho(f"[OK] {msg}", fg="green", bold=True)
    else:
        click.secho(f"[ERRO] {msg}", fg="red", bold=True)
        raise click.Abort()

    # ⚔️ ARES: Auto-Configuração de UX para o Editor (Zero-Touch)
    if os.name == 'nt':
        from sysutils.leap_sys.leap_platform.leap_windows import leap_elevation
        click.secho("\n[*] Configurando permissões de Hook para o Editor (Doxly/Lite XL)...", fg="cyan")
        ok_elev, msg_elev = leap_elevation.ensure_litexl_admin_elevation()
        if ok_elev:
            click.secho(f"✔ [ARES] {msg_elev}", fg="green")
            click.secho("  💡 O editor agora solicitará elevação (UAC) automaticamente ao abrir pelo ícone,", fg="yellow")
            click.secho("     garantindo que o Leap/KVM funcione sem travamentos de mouse/teclado.", fg="yellow")
        else:
            click.secho(f"⚠ [AVISO] {msg_elev}", fg="yellow")

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
        """Descobre interfaces de rede e seus IPs v4 ativos."""
        ips = []
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    ips.append((iface, addr.address))
        return ips

    # Validação dos binários
    if not leap_installer.is_installed():
        click.secho("[!] Binários não encontrados. Executando auto-setup...", fg="yellow")
        ok, msg = leap_installer.ensure_binaries()
        if not ok:
            click.secho(f"[ERRO] {msg}", fg="red")
            raise click.Abort()

    # Assistente caso client não tenha sido fornecido
    if not client:
        click.echo(f"Computador Servidor atual: {click.style(server_host, bold=True, fg='cyan')}")
        client = click.prompt("Nome do computador cliente de destino (ex: bluebaby)")

    # Firewall
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

    # 🛡️ BLINDAGEM: Força o nome 'bluebaby' se não for explicitado, garantindo match com o Host
    client_host = name or "bluebaby"
    
    # 🛡️ BLINDAGEM: Evita click.prompt em background. Se não houver IP, falha com instrução clara.
    if not server_target:
        click.secho("[ERRO] IP do servidor (Amaranth) é obrigatório para execução em background.", fg="red", bold=True)
        click.secho("Uso correto: sysutils leap join 192.168.18.52 --name bluebaby", fg="yellow")
        raise click.Abort()

    click.secho(f"[*] Conectando com nome de tela [{click.style(client_host, bold=True)}] ao servidor {server_target}:{port}...", fg="cyan")
    
    success, log = leap_orchestration.start_client(server_ip=server_target, client_name=client_host, port=port)
    
    if success:
        click.secho(f"[OK] Cliente Input Leap ativo em background com nome '{client_host}'!", fg="green", bold=True)
    else:
        click.secho(f"[FALHA] {log}", fg="red", bold=True)
        click.secho("💡 Dica: Verifique se o Firewall do Windows no Amaranth permite a porta 24800.", fg="yellow")

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
        click.secho(f"[OK] {killed} processo(s) do Input Leap finalizado(s).", fg="green")
    else:
        click.echo("[INFO] Nenhum processo ativo encontrado.")

@cli.command("firewall")
def cmd_firewall():
    """Autoriza e cadastra as regras do LeapSys no Firewall do Windows (Requer Admin)."""
    from sysutils.leap_sys.leap_platform.leap_windows import leap_firewall, leap_elevation
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
    """⚡ Configura a UX Soberana: Atalho com Elevação Automática para o Leap/KVM."""
    click.secho("[*] Forjando Atalho Soberano na Área de Trabalho...", fg="cyan")
    ok, msg = leap_elevation.create_sovereign_shortcut()
    if ok:
        click.secho(f"✔ [SUCESSO] {msg}", fg="green", bold=True)
        click.secho("💡 Fixe este atalho na sua Barra de Tarefas. O Windows pedirá UAC automaticamente.", fg="yellow")
        click.secho("   O Leap/KVM funcionará perfeitamente sem travamentos de mouse/teclado.", fg="yellow")
    else:
        click.secho(f"❌ [FALHA] {msg}", fg="red", bold=True)


