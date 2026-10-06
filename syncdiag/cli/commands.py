# syncdiag/cli/commands.py
import os
import socket
from pathlib import Path
import click
from syncdiag.core import profiles as profile_store, robocopy_engine as engine, smb_share

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "data" / "sync_logs"

@click.group()
def cli():
    """SyncDiag — Sincronização Inteligente e Segura entre Computadores."""
    pass

@cli.command("add")
@click.argument("name", required=False)
@click.option("--from", "origem", default=None, help="Pasta de origem local.")
@click.option("--to", "destino", default=None, help="Pasta/compartilhamento de destino.")
@click.option("--threads", default=16, show_default=True, help="Threads simultâneas de cópia.")
@click.option("--exclude-dir", "excludes_dir", multiple=True, help="Diretórios extras a ignorar.")
@click.option("--exclude-file", "excludes_file", multiple=True, help="Arquivos extras a ignorar.")
def add_profile(name, origem, destino, threads, excludes_dir, excludes_file):
    """Cadastra um perfil de sincronização permanente."""
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
        excludes_file=list(excludes_file)
    )

    click.secho(f"\n[OK] Perfil '{name}' configurado!", fg="green", bold=True)
    click.echo(f"  Origem : {origem}")
    click.echo(f"  Destino: {destino}")
    click.secho(f"  👉 Simulação Segura: sysutils sync run {name}", fg="cyan")
    click.secho(f"  👉 Cópia Aditiva Segura: sysutils sync run {name} --apply\n", fg="yellow")

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
    help="Executa a sincronização real em disco.",
)
@click.option(
    "--mirror", "mirror_mode", is_flag=True,
    help="Ativa modo espelho estrito (remove arquivos extras no destino). Padrão é SEGURO (aditivo).",
)
def run_profile(name, apply_changes, mirror_mode):
    """Executa a sincronização com prévia tática e validação de segurança."""
    cfg = profile_store.get_profile(name)
    if not cfg:
        click.secho(f"[ERRO] Perfil '{name}' não encontrado. Use 'sysutils sync list'.", fg="red")
        raise SystemExit(1)

    origem = cfg["origem"]
    destino = cfg["destino"]
    threads = cfg.get("threads", 16)

    # 1. EXIBIÇÃO DA PRÉVIA TÁTICA (AUDIT)
    click.secho("\n" + "=" * 70, fg="cyan")
    click.secho(f" 🛡️  AUDITORIA PRÉVIA DE SINCRONIZAÇÃO: {name.upper()}", fg="cyan", bold=True)
    click.secho("=" * 70, fg="cyan")
    click.echo(f"  Origem Local : {origem}")
    click.echo(f"  Destino Rede : {destino}")
    click.echo(f"  Estratégia   : {click.style('ESPELHAMENTO ESTRITO (/MIR)' if mirror_mode else 'CÓPIA ADITIVA SEGURA (Sem deleções)', bold=True, fg='red' if mirror_mode else 'green')}")

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

    if preview['extra_files'] == 0:
        click.secho("  • Arquivos Deletados no Destino  : ZERO (Destino 100% seguro contra exclusões)", fg="green", bold=True)
    else:
        cor = "red" if mirror_mode else "green"
        aviso = "SERÃO DELETADOS no destino" if mirror_mode else "SERÃO PRESERVADOS (Modo Seguro)"
        click.secho(f"  • Arquivos Extras no Destino     : {preview['extra_files']} ({aviso})", fg=cor, bold=True)

    click.echo("=" * 70 + "\n")

    if not apply_changes:
        click.secho("[MODO SIMULAÇÃO] Nenhum dado foi alterado.", fg="cyan")
        click.secho(f"👉 Para sincronizar de verdade sem deletar nada: sysutils sync run {name} --apply", fg="green", bold=True)
        if not mirror_mode:
            click.echo("💡 Se quiser espelhamento idêntico com exclusão de órfãos: use --mirror --apply")
        return

    # Confirmação do Usuário
    if mirror_mode:
        click.secho("⚠️  ATENÇÃO: Você ativou --mirror. Arquivos órfãos no destino serão expurgados.", fg="red", bold=True)
    if not click.confirm("Deseja iniciar a transferência de dados agora?", default=True):
        click.secho("[CANCELADO] Operação abortada com segurança.", fg="yellow")
        return

    click.secho(f"\n[*] Transferindo arquivos em tempo real via Robocopy...\n", fg="cyan")
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

@cli.group("share")
def share_group():
    """Gerenciamento de Compartilhamento SMB Nativo do Windows."""
    pass

@share_group.command("create")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--name", required=True, help="Nome do compartilhamento.")
@click.option("--user", default=None, help="Usuário específico. Padrão: Everyone/Todos.")
def share_create(path, name, user):
    """Cria um compartilhamento de rede na máquina atual (Requer Admin)."""
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
    """Lista compartilhamentos SMB ativos nesta máquina."""
    shares = smb_share.list_shares()
    if not shares:
        click.secho("[!] Nenhum compartilhamento localizado.", fg="yellow")
        return
    click.echo("\n--- COMPARTILHAMENTOS ATIVOS ---")
    for s in shares:
        click.echo(f"  • {s['name']:<20} -> {s['path']}")
    click.echo("--------------------------------\n")
