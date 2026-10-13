# syncdiag/cli/commands.py
"""
Interface CLI para Perfis de Sincronização e Compartilhamento de Rede SMB.
"""
import os
import socket
from pathlib import Path
import click

from syncdiag.core import (
    profiles as profile_store,
    robocopy_engine as engine,
    smb_share,
    network_connect,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "data" / "sync_logs"


@click.group()
def cli():
    """Comandos de sincronização e diagnóstico de arquivos."""
    pass


@cli.command("add")
@click.argument("name", required=False)
@click.option("--from", "origem", default=None, help="Pasta de origem local.")
@click.option("--to", "destino", default=None, help="Pasta/compartilhamento de destino.")
@click.option("--threads", default=16, show_default=True, help="Threads simultâneas de cópia.")
@click.option("--exclude-dir", "excludes_dir", multiple=True, help="Diretórios extras a ignorar.")
@click.option("--exclude-file", "excludes_file", multiple=True, help="Arquivos extras a ignorar.")
def add_profile(name, origem, destino, threads, excludes_dir, excludes_file):
    if not name:
        name = click.prompt("Nome do perfil (ex: 'a2025')")
    if not origem:
        while True:
            origem = click.prompt("Caminho absoluto da pasta de origem")
            if Path(origem).is_dir():
                break
            click.secho(f"[!] '{origem}' não é um diretório válido.", fg="yellow")
    if not destino:
        destino = click.prompt("Caminho UNC de destino (ex: \\\\192.168.18.52\\A20251122)")

    profile_store.add_profile(
        name=name,
        origem=origem,
        destino=destino,
        threads=threads,
        excludes_dir=list(excludes_dir),
        excludes_file=list(excludes_file),
    )
    click.secho(f"\n[OK] Perfil '{name}' configurado!", fg="green", bold=True)
    click.echo(f"  Origem : {origem}")
    click.echo(f"  Destino: {destino}")
    click.secho(f"  👉 Simulação Segura: sysutils sync run {name}", fg="cyan")
    click.secho(f"  👉 Cópia Aditiva Segura: sysutils sync run {name} --apply\n", fg="yellow")


@cli.command("list")
def list_profiles():
    data = profile_store.list_profiles()
    if not data:
        click.secho("[!] Nenhum perfil cadastrado. Use 'sysutils sync add'.", fg="yellow")
        return
    click.echo("\n--- PERFIS DE SINCRONIZAÇÃO ATIVOS ---")
    for name, cfg in data.items():
        click.echo(f"  • {click.style(name, bold=True, fg='cyan')}")
        click.echo(f"    Origem : {cfg['origem']}")
        click.echo(f"    Destino: {cfg['destino']}")
        click.echo(f"    Threads: {cfg.get('threads', 16)}")
    click.echo("--------------------------------------\n")


@cli.command("remove")
@click.argument("name")
def remove_profile(name):
    if profile_store.remove_profile(name):
        click.secho(f"[OK] Perfil '{name}' removido.", fg="green")
    else:
        click.secho(f"[ERRO] Perfil '{name}' não encontrado.", fg="red")


@cli.command("run")
@click.argument("name")
@click.option("--apply", "apply_changes", is_flag=True, help="Executa a sincronização real em disco.")
@click.option("--mirror", "mirror_mode", is_flag=True, help="Ativa modo espelho estrito (/MIR).")
def run_profile(name, apply_changes, mirror_mode):
    cfg = profile_store.get_profile(name)
    if not cfg:
        click.secho(f"[ERRO] Perfil '{name}' não encontrado. Use 'sysutils sync list'.", fg="red")
        raise SystemExit(1)
    origem = cfg["origem"]
    destino = cfg["destino"]
    threads = cfg.get("threads", 16)
    click.secho("\n" + "=" * 70, fg="cyan")
    click.secho(f" 🛡️  AUDITORIA PRÉVIA DE SINCRONIZAÇÃO: {name.upper()}", fg="cyan", bold=True)
    click.secho("=" * 70, fg="cyan")
    click.echo(f"  Origem Local : {origem}")
    click.echo(f"  Destino Rede : {destino}")
    click.echo(f"  Estratégia   : {click.style('ESPELHAMENTO ESTRITO (/MIR)' if mirror_mode else 'CÓPIA ADITIVA SEGURA', bold=True, fg='red' if mirror_mode else 'green')}")

    click.echo("\n[*] Coletando diagnóstico da rede...")
    preview = engine.get_sync_preview(
        origem=origem,
        destino=destino,
        log_dir=LOG_DIR,
        threads=threads,
        mirror_mode=mirror_mode,
        excludes_dir=cfg.get("excludes_dir"),
        excludes_file=cfg.get("excludes_file"),
    )
    click.echo(f"  • Arquivos a Transferir/Atualizar : {click.style(str(preview['copied_files']), bold=True, fg='yellow')}")
    click.echo(f"  • Volume Estimado                : {click.style(str(preview['copied_bytes']), bold=True, fg='yellow')}")
    if preview["extra_files"] == 0:
        click.secho("  • Arquivos Deletados no Destino  : ZERO (Destino 100% seguro)", fg="green", bold=True)
    else:
        cor = "red" if mirror_mode else "green"
        aviso = "SERÃO DELETADOS no destino" if mirror_mode else "SERÃO PRESERVADOS (Modo Seguro)"
        click.secho(f"  • Arquivos Extras no Destino     : {preview['extra_files']} ({aviso})", fg=cor, bold=True)
    click.echo("=" * 70 + "\n")

    if not apply_changes:
        click.secho("[MODO SIMULAÇÃO] Nenhum dado foi alterado.", fg="cyan")
        click.secho(f"👉 Para sincronizar: sysutils sync run {name} --apply", fg="green", bold=True)
        return

    if mirror_mode:
        click.secho("⚠️  ATENÇÃO: Modo --mirror ativado. Arquivos órfãos no destino serão expurgados.", fg="red", bold=True)
    if not click.confirm("Deseja iniciar a transferência agora?", default=True):
        click.secho("[CANCELADO] Operação abortada com segurança.", fg="yellow")
        return

    click.secho("\n[*] Transferindo arquivos em tempo real via Robocopy...\n", fg="cyan")
    result = engine.run_mirror(
        origem=origem,
        destino=destino,
        log_dir=LOG_DIR,
        threads=threads,
        dry_run=False,
        mirror_mode=mirror_mode,
        excludes_dir=cfg.get("excludes_dir"),
        excludes_file=cfg.get("excludes_file"),
    )
    cor = "green" if result["success"] else "red"
    click.secho(f"\n[{'SUCESSO' if result['success'] else 'FALHA'}] {result['description']}", fg=cor, bold=True)
    click.echo(f"Log gravado em: {result['log_path']}")


# ═══════════════════════════════════════════════════════════════
# GRUPO DE COMPARTILHAMENTO E REDE REMOTA (SHARE)
# ═══════════════════════════════════════════════════════════════
@cli.group("share")
def share_group():
    """Gerenciamento de compartilhamentos SMB e conexões remotas."""
    pass


@share_group.command("create")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--name", required=True, help="Nome do compartilhamento.")
@click.option("--user", default=None, help="Usuário específico. Padrão: Everyone/Todos.")
def share_create(path, name, user):
    """Cria um compartilhamento SMB nesta máquina."""
    if not smb_share.is_admin():
        click.secho("[ERRO] Abra o terminal como Administrador para criar compartilhamentos.", fg="red", bold=True)
        raise SystemExit(1)
    abs_path = os.path.abspath(path)
    result = smb_share.create_share(name, abs_path, user=user)
    if result["success"]:
        hostname = socket.gethostname()
        click.secho(f"[OK] Compartilhamento ativo: \\\\{hostname}\\{name}", fg="green", bold=True)
        click.echo(f"     Pasta local: {abs_path}")
    else:
        click.secho("[ERRO] Falha ao registrar compartilhamento.", fg="red")
        click.echo(result["stderr"] or result["stdout"])


@share_group.command("list")
def share_list():
    """Lista compartilhamentos locais desta máquina."""
    shares = smb_share.list_shares()
    if not shares:
        click.secho("[!] Nenhum compartilhamento localizado.", fg="yellow")
        return
    click.echo("\n--- COMPARTILHAMENTOS LOCAIS ATIVOS ---")
    for s in shares:
        click.echo(f"  • {s['name']:<20} -> {s['path']}")
    click.echo("---------------------------------------\n")


@share_group.command("peers")
def share_peers():
    """Lista computadores na malha Tailscale (Amaranth, Bluebaby, etc)."""
    peers = network_connect.get_tailscale_peers()
    if not peers:
        click.secho("[!] Nenhuma máquina Tailscale encontrada ou CLI indisponível.", fg="yellow")
        return
    click.echo("\n--- COMPUTADORES TAILSCALE DETECTADOS ---")
    for p in peers:
        color = "green" if p["status"] == "active" else "red"
        click.echo(f"  • {p['name']:<20} ({click.style(p['ip'], fg='cyan')}) - {click.style(p['status'], fg=color)}")
    click.echo("-----------------------------------------\n")


@share_group.command("pair")
@click.argument("host")
@click.option("--user", prompt="Usuário do Windows remoto", help="Nome do usuário do PC remoto.")
@click.option("--password", prompt=True, hide_input=True, help="Senha do usuário remoto.")
def share_pair(host, user, password):
    """Pareia e salva as credenciais de um PC (executar apenas 1 vez)."""
    network_connect.save_host_credentials(host, user, password)
    network_connect.register_credentials(host, user, password)
    click.secho(f"\n[OK] Pareamento com '{host}' configurado com sucesso!", fg="green", bold=True)
    click.echo(f"Agora você pode conectar sem digitar senhas:")
    click.secho(f"👉 sysutils share connect {host} NOME_DA_PASTA\n", fg="cyan")


@share_group.command("connect")
@click.argument("host")
@click.argument("share_name")
@click.option("--drive", "-d", default="Z:", show_default=True, help="Letra da unidade para mapear.")
@click.option("--user", "-u", default=None, help="Usuário do Windows remoto.")
@click.option("--password", "-p", default=None, help="Senha do usuário remoto.")
@click.option("--open-dir/--no-open", default=True, help="Abre no Windows Explorer ao conectar.")
def share_connect(host, share_name, drive, user, password, open_dir):
    """Conecta e mapeia pasta remota para copiar e colar via Explorer."""
    unc_path = f"\\\\{host}\\{share_name}"
    click.secho(f"\n[*] Testando conectividade SMB com '{host}' (Porta 445)...", fg="cyan")

    if not network_connect.probe_smb_port(host, timeout=2.0):
        click.secho(f"[ERRO] A porta SMB (445) em '{host}' não respondeu.", fg="red", bold=True)
        raise SystemExit(1)

    click.secho("    ✔ Porta 445 ativa e respondendo!", fg="green")

    # 1. Recupera credenciais salvas se não foram passadas na linha de comando
    if not user:
        saved_user, saved_pass = network_connect.get_saved_credentials(host)
        if saved_user:
            user = saved_user
            password = saved_pass
            click.echo(f"[*] Usando credenciais salvas para '{user}'...")
        else:
            # Fallback interativo para evitar erro 1223 silencioso
            click.secho(f"\n[!] Nenhuma credencial encontrada para '{host}'.", fg="yellow")
            if click.confirm("Deseja inserir o usuário e senha agora?", default=True):
                user = click.prompt("Usuário do Windows remoto")
                password = click.prompt("Senha", hide_input=True)
                if click.confirm("Deseja salvar estas credenciais para os próximos acessos?", default=True):
                    network_connect.save_host_credentials(host, user, password)

    if user:
        network_connect.register_credentials(host, user, password)

    click.echo(f"[*] Mapeando '{unc_path}' como '{drive}'...")
    success, msg = network_connect.mount_network_drive(
        unc_path=unc_path,
        drive_letter=drive,
        user=user,
        password=password,
        persistent=True,
        host=host, # <-- Garante a resolução correta do domínio
    )

    if success:
        click.secho(f"[OK] {msg}", fg="green", bold=True)
        click.secho(f"👉 Acesse a unidade '{drive}' no Windows Explorer para copiar/colar!", fg="yellow")
        if open_dir:
            network_connect.open_in_explorer(drive)
    else:
        click.secho(f"[AVISO] Mapeamento falhou: {msg}", fg="yellow")
        if open_dir:
            network_connect.open_in_explorer(unc_path)


@share_group.command("disconnect")
@click.argument("target", default="Z:")
def share_disconnect(target):
    """Desconecta uma unidade mapeada (ex: Z:) ou link de rede."""
    success, msg = network_connect.unmount_network_drive(target)
    if success:
        click.secho(f"[OK] {msg}", fg="green")
    else:
        click.secho(f"[ERRO] {msg}", fg="red")

@share_group.command("auto")
def share_auto():
    """🧙 Assistente Inteligente: Configura pastas, permissões e conecta ao outro PC."""
    click.secho("\n" + "=" * 65, fg="cyan")
    click.secho(" 🚀 SYSUTILS SHARE AUTO — ASSISTENTE DE CONEXÃO DIRETA", fg="cyan", bold=True)
    click.secho("=" * 65 + "\n", fg="cyan")

    # 1. Ativa correção de UAC (evita pop-up de 'Z:\ não disponível')
    network_connect.fix_uac_linked_connections()

    # 2. Identifica estação atual
    station_key, profile = network_connect.identify_current_station()
    hostname = socket.gethostname()
    click.echo(f"  • Estação Local : {click.style(hostname, bold=True, fg='green')} ({station_key.upper()})")
    click.echo(f"  • Alvo Remoto   : {click.style(profile['peer_name'].upper(), bold=True, fg='yellow')}")

    # 3. Garante que a pasta local pré-estabelecida existe
    local_dir = Path(profile["local_folder_path"])
    local_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"  • Pasta Local   : {local_dir}")

    # 4. Garante permissão física NTFS de escrita total
    subprocess.run(
        ["icacls", str(local_dir), "/grant", "Todos:(OI)(CI)F", "/T", "/C", "/Q"],
        capture_output=True,
        text=True,
    )

    # 5. Garante que a pasta local está compartilhada na rede
    share_name = profile["local_share_name"]
    smb_share.create_share(share_name, str(local_dir))
    click.secho(f"  ✔ Compartilhamento local ativo: \\\\{hostname}\\{share_name}", fg="green")

    # 6. Localiza o outro computador via Tailscale
    click.echo(f"\n[*] Procurando {profile['peer_name'].upper()} na rede Tailscale...")
    peers = network_connect.get_tailscale_peers()
    remote_ip = None

    for p in peers:
        p_name = p["name"].lower()
        if any(hint in p_name for hint in profile["peer_hostname_hints"]):
            remote_ip = p["ip"]
            break

    if not remote_ip:
        click.secho(f"[!] Não foi possível detectar o IP de {profile['peer_name']} automaticamente.", fg="yellow")
        remote_ip = click.prompt("Digite o IP Tailscale da outra máquina (ex: 100.x.y.z)")
    else:
        click.secho(f"  ✔ {profile['peer_name'].upper()} localizado: {remote_ip}", fg="green", bold=True)

    # 7. Teste de porta 445
    if not network_connect.probe_smb_port(remote_ip, timeout=2.0):
        click.secho(f"\n[ERRO] A porta SMB em {remote_ip} não respondeu.", fg="red", bold=True)
        click.echo("Certifique-se de que o Tailscale está ligado na outra máquina.")
        raise SystemExit(1)

    # 8. Recuperação/Solicitação de Credenciais
    saved_user, saved_pass = network_connect.get_saved_credentials(remote_ip)
    user = saved_user
    password = saved_pass

    if not user:
        click.secho(f"\n[!] Configure o acesso ao computador {profile['peer_name'].upper()}:", fg="yellow")
        user = click.prompt("Nome do usuário do Windows no outro PC")
        password = click.prompt("Senha (aperte ENTER se não tiver senha)", default="", hide_input=True)
        network_connect.save_host_credentials(remote_ip, user, password)

    # 9. Escolhe a melhor letra de unidade livre (evita Erro 85)
    drive_letter = network_connect.get_available_drive_letter()
    remote_share = profile["remote_share_name"]
    unc_path = f"\\\\{remote_ip}\\{remote_share}"

    click.echo(f"\n[*] Conectando à pasta remota '{unc_path}' na unidade {drive_letter}...")
    success, msg = network_connect.mount_network_drive(
        unc_path=unc_path,
        drive_letter=drive_letter,
        user=user,
        password=password,
        persistent=True,
        host=remote_ip,
    )

    if success:
        click.secho(f"\n[SUCESSO] Conectado à outra máquina com sucesso!", fg="green", bold=True)
        click.secho(f"👉 Abrindo unidade '{drive_letter}' e pasta de rede no Windows Explorer...", fg="cyan")
        network_connect.open_in_explorer(drive_letter)
        # Abre também o UNC direto caso o UAC demore a atualizar
        network_connect.open_in_explorer(unc_path)
    else:
        click.secho(f"\n[AVISO] {msg}", fg="yellow")
        click.echo("[*] Abrindo acesso direto via UNC no Windows Explorer...")
        network_connect.open_in_explorer(unc_path)

    click.secho("\n" + "=" * 65 + "\n", fg="cyan")

