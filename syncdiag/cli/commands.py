# syncdiag/cli/commands.py
import os
import socket
from pathlib import Path
import click
from syncdiag.core import profiles as profile_store, robocopy_engine as engine, discovery, smb_share

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "data" / "sync_logs"

@click.group()
def cli():
    """SyncDiag — Sincronização e Espelhamento Ultra-Rápido via Robocopy/SMB."""
    pass

@cli.command("add")
@click.argument("name", required=False)
@click.option("--from", "origem", default=None, help="Pasta de origem local.")
@click.option("--to", "destino", default=None, help="Pasta/compartilhamento de destino (ex: \\\\192.168.18.52\\A20251122 ou \\\\bluebaby\\share).")
@click.option("--threads", default=16, show_default=True, help="Threads simultâneas de cópia.")
@click.option("--exclude-dir", "excludes_dir", multiple=True, help="Diretórios extras a ignorar.")
@click.option("--exclude-file", "excludes_file", multiple=True, help="Arquivos/extensões extras a ignorar.")
def add_profile(name, origem, destino, threads, excludes_dir, excludes_file):
    """Cadastra um perfil de sincronização permanente."""
    if not name:
        name = click.prompt("Nome do perfil (ex: 'sync_a2025')")

    if not origem:
        while True:
            origem = click.prompt("Caminho absoluto da pasta de origem")
            if Path(origem).is_dir():
                break
            click.secho(f"[!] '{origem}' não é um diretório válido.", fg="yellow")

    if not destino:
        destino = click.prompt("Caminho UNC de destino (ex: \\\\bluebaby\\A20251122 ou \\\\IP\\A20251122)")

    profile_store.add_profile(
        name=name,
        origem=origem,
        destino=destino,
        threads=threads,
        excludes_dir=list(excludes_dir),
        excludes_file=list(excludes_file)
    )

    click.secho(f"\n[OK] Perfil '{name}' configurado com sucesso!", fg="green", bold=True)
    click.echo(f"  Origem : {origem}")
    click.echo(f"  Destino: {destino}")
    click.secho(f"  👉 Teste seguro: sysutils sync run {name}", fg="cyan")
    click.secho(f"  👉 Execução real: sysutils sync run {name} --apply\n", fg="yellow")

@cli.command("list")
def list_profiles():
    """Lista todos os perfis de sincronização cadastrados."""
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
    """Remove um perfil existente."""
    if profile_store.remove_profile(name):
        click.secho(f"[OK] Perfil '{name}' removido.", fg="green")
    else:
        click.secho(f"[ERRO] Perfil '{name}' não encontrado.", fg="red")

@cli.command("run")
@click.argument("name")
@click.option(
    "--apply", "apply_changes", is_flag=True,
    help="Executa a sincronização real. Sem esta flag, roda em DRY-RUN seguro.",
)
def run_profile(name, apply_changes):
    """Executa a sincronização de um perfil."""
    cfg = profile_store.get_profile(name)
    if not cfg:
        click.secho(f"[ERRO] Perfil '{name}' não encontrado. Use 'sysutils sync list'.", fg="red")
        raise SystemExit(1)

    dry_run = not apply_changes
    modo = "DRY-RUN (Simulação segura — nenhum arquivo alterado)" if dry_run else "EXECUÇÃO REAL (Mirroring)"
    click.secho(f"\n[*] Disparando perfil '{name}' [{modo}]", fg="cyan", bold=True)
    click.echo(f"    {cfg['origem']}  ===>  {cfg['destino']}\n")

    if not dry_run:
        click.secho("[ATENÇÃO] Modo Mirror: arquivos no destino que não existirem na origem serão expurgados.", fg="yellow", bold=True)
        if not click.confirm("Deseja realmente iniciar a transferência agora?", default=False):
            click.secho("[CANCELADO] Operação abortada pelo usuário.", fg="yellow")
            raise SystemExit(0)

    result = engine.run_mirror(
        origem=cfg["origem"],
        destino=cfg["destino"],
        log_dir=LOG_DIR,
        threads=cfg.get("threads", 16),
        dry_run=dry_run,
        excludes_dir=cfg.get("excludes_dir"),
        excludes_file=cfg.get("excludes_file"),
    )

    cor = "green" if result["success"] else "red"
    click.secho(f"\n[{'CONCLUÍDO' if result['success'] else 'FALHA'}] {result['description']}", fg=cor, bold=True)
    click.echo(f"Log detalhado: {result['log_path']}")

    if dry_run and result["success"]:
        click.secho(f"\n💡 Para efetivar as alterações, rode: sysutils sync run {name} --apply\n", fg="cyan", bold=True)

@cli.group("share")
def share_group():
    """Gerenciamento de Compartilhamento SMB Nativo do Windows."""
    pass

@share_group.command("create")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--name", required=True, help="Nome do compartilhamento (ex: A20251122).")
@click.option("--user", default=None, help="Usuário específico. Padrão: Everyone.")
def share_create(path, name, user):
    """Cria um compartilhamento de rede na máquina atual (Requer Admin)."""
    if not smb_share.is_admin():
        click.secho("[ERRO] Abra o terminal como Administrador para criar compartilhamentos de rede.", fg="red", bold=True)
        raise SystemExit(1)
    abs_path = os.path.abspath(path)
    result = smb_share.create_share(name, abs_path, user=user)
    if result["success"]:
        hostname = socket.gethostname()
        click.secho(f"[OK] Compartilhamento ativo: \\\\{hostname}\\{name}", fg="green", bold=True)
        click.echo(f"     Pasta local: {abs_path}")
        click.secho(f"     No outro computador, acesse via: \\\\{hostname}\\{name} ou \\\\<IP-Deste-PC>\\{name}", fg="cyan")
    else:
        click.secho("[ERRO] Falha ao registrar compartilhamento.", fg="red")
        click.echo(result["stderr"] or result["stdout"])

@share_group.command("list")
def share_list():
    """Lista compartilhamentos SMB ativos nesta máquina."""
    shares = smb_share.list_shares()
    if not shares:
        click.secho("[!] Nenhum compartilhamento localizado.", fg="yellow")
        return
    click.echo("\n--- COMPARTILHAMENTOS ATIVOS ---")
    for s in shares:
        click.echo(f"  • {s['name']:<20} -> {s['path']}")
    click.echo("--------------------------------\n")
