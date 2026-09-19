# syncdiag/cli/commands.py
"""
Comando `sync` do SysUtils.

Sincronização one-way (mirror) entre uma pasta local e um destino
(compartilhamento de rede do outro PC), via Robocopy.

Segue ProDeNov 5.3: comandos que manipulam algo irreversível (mirror
pode apagar arquivos no destino) rodam em --dry-run por padrão; a
execução real exige a flag --apply e uma confirmação explícita.

Registrar no cli/main.py, dentro de SysUtilsLazyGroup._lazy_map:
    'sync': 'syncdiag.cli.commands:cli'
"""
import os
import socket
from pathlib import Path

import click

from syncdiag.core import profiles as profile_store
from syncdiag.core import robocopy_engine as engine
from syncdiag.core import discovery
from syncdiag.core import smb_share

LOG_DIR = Path("data") / "sync_logs"


@click.group()
def cli():
    """Sincronização de pastas entre computadores (mirror via Robocopy)."""
    pass


def _wizard_pick_destino() -> str:
    """
    Ajuda a identificar 'a outra parte' (PC + compartilhamento) na rede,
    em vez de exigir que o usuário digite o caminho UNC de cabeça.
    """
    click.secho("[*] Procurando computadores na rede local...", fg="cyan")
    computers = discovery.list_network_computers()

    if not computers:
        click.secho("[!] Nenhum computador encontrado automaticamente na rede.", fg="yellow")
        return click.prompt("Digite o caminho de destino manualmente (\\\\PC\\share)")

    click.echo("Computadores encontrados na rede:")
    for i, pc in enumerate(computers, start=1):
        click.echo(f"  {i}. {pc}")
    manual_idx = len(computers) + 1
    click.echo(f"  {manual_idx}. Digitar manualmente")

    escolha = click.prompt("Selecione o computador de destino", type=click.IntRange(1, manual_idx))
    if escolha == manual_idx:
        return click.prompt("Digite o caminho de destino manualmente (\\\\PC\\share)")

    pc = computers[escolha - 1]
    click.secho(f"[*] Procurando compartilhamentos em \\\\{pc}...", fg="cyan")
    shares = discovery.list_shares(pc)

    if not shares:
        click.secho(f"[!] Nenhum compartilhamento visível em \\\\{pc}.", fg="yellow")
        pasta = click.prompt(f"Digite o nome do compartilhamento em \\\\{pc}\\")
        return f"\\\\{pc}\\{pasta}"

    click.echo(f"Compartilhamentos em \\\\{pc}:")
    for i, share in enumerate(shares, start=1):
        click.echo(f"  {i}. {share}")
    manual_idx2 = len(shares) + 1
    click.echo(f"  {manual_idx2}. Digitar manualmente")

    escolha2 = click.prompt("Selecione o compartilhamento", type=click.IntRange(1, manual_idx2))
    if escolha2 == manual_idx2:
        pasta = click.prompt(f"Digite o nome do compartilhamento em \\\\{pc}\\")
        return f"\\\\{pc}\\{pasta}"

    return f"\\\\{pc}\\{shares[escolha2 - 1]}"


@cli.command("add")
@click.argument("name", required=False)
@click.option("--from", "origem", default=None, help="Pasta de origem (emissor).")
@click.option("--to", "destino", default=None, help="Pasta/compartilhamento de destino (\\\\PC\\share).")
@click.option("--threads", default=16, show_default=True, help="Threads paralelas do Robocopy.")
@click.option("--exclude", "excludes", multiple=True, help="Pasta a excluir (repita a opção para várias).")
def add_profile(name, origem, destino, threads, excludes):
    """
    Cadastra um novo perfil de sincronização.

    Qualquer informação que faltar (nome, origem, destino) é perguntada
    de forma interativa — incluindo um wizard pra identificar e
    selecionar o PC/compartilhamento de destino na rede local.
    """
    if not name:
        name = click.prompt("Nome do perfil (ex: 'trabalho')")

    if not origem:
        while True:
            origem = click.prompt("Pasta de origem (emissor)")
            if Path(origem).is_dir():
                break
            click.secho(f"[!] '{origem}' não existe ou não é uma pasta. Tente novamente.", fg="yellow")

    if not destino:
        destino = _wizard_pick_destino()

    profile_store.add_profile(name, origem, destino, threads, list(excludes))
    click.secho(f"\n[OK] Perfil '{name}' salvo.", fg="green")
    click.echo(f"     {origem}  ->  {destino}")
    click.secho("     Rode 'sysutils sync run " + name + "' para simular (dry-run é o padrão).", fg="cyan")


@cli.command("list")
def list_profiles():
    """Lista os perfis de sincronização cadastrados."""
    data = profile_store.list_profiles()
    if not data:
        click.secho("Nenhum perfil cadastrado. Use 'sysutils sync add'.", fg="yellow")
        return
    for name, cfg in data.items():
        click.echo(f"- {name}: {cfg['origem']}  ->  {cfg['destino']}  (threads={cfg.get('threads', 16)})")


@cli.command("remove")
@click.argument("name")
def remove_profile(name):
    """Remove um perfil de sincronização cadastrado."""
    if profile_store.remove_profile(name):
        click.secho(f"[OK] Perfil '{name}' removido.", fg="green")
    else:
        click.secho(f"[ERRO] Perfil '{name}' não encontrado.", fg="red")


@cli.command("run")
@click.argument("name")
@click.option(
    "--apply", "apply_changes", is_flag=True,
    help="Executa de verdade. SEM esta flag, roda em --dry-run (padrão de segurança, ProDeNov 5.3).",
)
def run_profile(name, apply_changes):
    """Executa a sincronização de um perfil. Por padrão roda em dry-run."""
    cfg = profile_store.get_profile(name)
    if not cfg:
        click.secho(f"[ERRO] Perfil '{name}' não encontrado. Use 'sysutils sync list'.", fg="red")
        raise SystemExit(1)

    dry_run = not apply_changes
    modo = "DRY-RUN (simulação — nada será alterado)" if dry_run else "MIRROR (execução real)"
    click.secho(f"[*] Sincronizando '{name}' [{modo}]", fg="cyan", bold=True)
    click.echo(f"    {cfg['origem']}  ->  {cfg['destino']}")

    if not dry_run:
        click.secho(
            "\n[ATENÇÃO] Modo real: arquivos extras no destino serão APAGADOS (mirror).",
            fg="yellow", bold=True,
        )
        if not click.confirm("Confirma a execução real?", default=False):
            click.secho("[ABORTADO] Nenhuma alteração feita.", fg="yellow")
            raise SystemExit(0)

    result = engine.run_mirror(
        cfg["origem"],
        cfg["destino"],
        LOG_DIR,
        threads=cfg.get("threads", 16),
        dry_run=dry_run,
        excludes=cfg.get("excludes"),
    )

    cor = "green" if result["success"] else "red"
    status = "OK" if result["success"] else "FALHA"
    click.secho(f"[{status}] {result['description']}", fg=cor)
    click.echo(f"Log: {result['log_path']}")

    if dry_run and result["success"]:
        click.secho(f"Rode 'sysutils sync run {name} --apply' para executar de verdade.", fg="cyan")

    if not result["success"]:
        click.secho(f"Exit code: {result['exit_code']} — veja o log para detalhes.", fg="red")
        raise SystemExit(result["exit_code"])


# =====================================================================
# GRUPO: SHARE (configura o compartilhamento SMB da pasta de destino)
# =====================================================================
@cli.group("share")
def share_group():
    """
    Configura o compartilhamento de rede (SMB) da pasta de destino.

    Roda no PC RECEBEDOR: cria/lista/remove o compartilhamento que o
    PC emissor vai enxergar como \\\\ESTE-PC\\nome via Tailscale/LAN.
    Precisa ser executado como Administrador.
    """
    pass


@share_group.command("create")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--name", required=True, help="Nome do compartilhamento (vira \\\\ESTE-PC\\nome).")
@click.option("--user", default=None, help="Usuário do Windows com acesso total. Padrão: Everyone.")
def share_create(path, name, user):
    """Cria um compartilhamento SMB apontando para uma pasta local."""
    if not smb_share.is_admin():
        click.secho("[ERRO] Este comando precisa ser rodado como Administrador.", fg="red")
        click.echo("Abra o PowerShell/CMD com 'Executar como administrador' e tente de novo.")
        raise SystemExit(1)

    abs_path = os.path.abspath(path)
    result = smb_share.create_share(name, abs_path, user=user)

    if result["success"]:
        hostname = socket.gethostname()
        click.secho(f"[OK] Compartilhamento criado: \\\\{hostname}\\{name}", fg="green")
        click.echo(f"     Aponta para: {abs_path}")
        click.echo(f"     Acesso: {'usuário ' + user if user else 'Everyone (qualquer usuário autenticado)'}")
        click.secho(
            f"\nNo outro PC, use este caminho no 'sysutils sync add': \\\\<IP-Tailscale-deste-PC>\\{name}",
            fg="cyan",
        )
    else:
        click.secho("[ERRO] Falha ao criar compartilhamento.", fg="red")
        click.echo(result["stderr"] or result["stdout"])


@share_group.command("list")
def share_list():
    """Lista os compartilhamentos SMB ativos nesta máquina."""
    shares = smb_share.list_shares()
    if not shares:
        click.secho("Nenhum compartilhamento encontrado.", fg="yellow")
        return
    for s in shares:
        click.echo(f"- {s['name']}  ->  {s['path']}")


@share_group.command("remove")
@click.argument("name")
def share_remove(name):
    """Remove um compartilhamento SMB pelo nome."""
    if not smb_share.is_admin():
        click.secho("[ERRO] Este comando precisa ser rodado como Administrador.", fg="red")
        raise SystemExit(1)

    result = smb_share.remove_share(name)
    if result["success"]:
        click.secho(f"[OK] Compartilhamento '{name}' removido.", fg="green")
    else:
        click.secho("[ERRO] Falha ao remover.", fg="red")
        click.echo(result["stderr"] or result["stdout"])
