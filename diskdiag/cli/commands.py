# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]
# diskdiag/cli/commands.py

import click
from utils.error_handler import handle_cli_error
from utils.error_info import handle_error
from diskdiag.analysis.disk_analysis import _format_size

@click.group()
def cli():
    """DiskDiag - Diagnóstico de Uso de Disco."""
    pass

@cli.command()
@click.argument("path")
@click.option("--db", default="data/db/files.db", show_default=True)
def scan(path, db):
    """Varre um diretório e indexa os arquivos."""
    try:
        from diskdiag.core.indexer import run_indexer
        run_indexer(path, db)
    except Exception as e:
        handle_cli_error(e)

@cli.command()
@click.argument("path", required=False) # Adicionado argumento opcional
@click.option("--db", default="data/db/files.db", show_default=True)
@click.option("--past", "-p", is_flag=True, help="Analisa tamanho por pastas.")
@click.option("--extension", "-e", is_flag=True, help="Analisa o peso por extensão.")
def analyze(path, db, past, extension):
    """Analisa os dados coletados (opcionalmente filtrando por PATH)."""
    try:
        from diskdiag.analysis.disk_analysis import run_analysis
        run_analysis(db, path_filter=path, analyze_folders=past, analyze_extensions=extension)
    except Exception as e:
        handle_cli_error(e)
        
@cli.command()
@click.option("--db", default="data/db/files.db")
@click.option("--out", default="data/vulcan_idx")
def optimize(db, out):
    """Comprime o banco SQLite para o formato binário Vulcan (OLINE Tech)."""
    try:
        from diskdiag.core.vulcan_index import compress_db_to_vulcan
        compress_db_to_vulcan(db, out)
    except Exception as e:
        handle_cli_error(e)
        
@cli.command()
@click.argument("query")
@click.option("--db", default="data/db/files.db")
@click.option("--idx", default="data/vulcan_idx")
@click.option("--limit", default=15)
def find(query, db, idx, limit):
    """Busca ultra-rápida usando o índice binário Vulcan."""
    try:
        from diskdiag.core.vulcan_search import run_vulcan_find
        run_vulcan_find(query, idx, db, limit)
    except Exception as e:
        handle_cli_error(e)
        
@cli.command()
@click.option("--db", default="data/db/files.db")
@click.option("--dry-run/--force", default=True, help="Por padrão apenas simula. Use --force para deletar.")
def cleanup(db, dry_run):
    """Limpeza de disco: --dry-run (padrão) ou --force."""
    try:
        from diskdiag.core.cleaner import run_safe_cleanup
        run_safe_cleanup(db, dry_run=dry_run)
    except Exception as e:
        handle_cli_error(e)
        
@cli.command()
def pip_check():
    """Analisa o lixo acumulado pelo pip global e user-site."""
    try:
        from diskdiag.core.pip_cleaner import scan_pip_junk
        junk, total = scan_pip_junk()
        
        if not junk:
            click.secho("[OK] Seu pip global está limpo.", fg="green")
            return

        click.echo("\n" + "="*70)
        click.echo(f"{'LOCALIZAÇÃO DO LIXO PIP':<55} | {'TAMANHO'}")
        click.echo("-" * 70)
        for path, size in sorted(junk, key=lambda x: x[1], reverse=True):
            click.echo(f"{path:<55} | {_format_size(size):>10}")
        
        click.echo("="*70)
        click.secho(f"TOTAL RECUPERÁVEL NO PIP: {_format_size(total)}", bold=True)
    except Exception as e:
        handle_error(e, context="pip-check", debug=True)

@cli.command()
def audit():
    """Auditoria geral: Peso de Pacotes Python e Caches de Aplicativos."""
    from diskdiag.core.pkg_auditor import audit_global_packages
    from diskdiag.core.system_bloat import audit_appdata_bloat
    
    click.secho("\n--- PEGADA DE DISCO: PACOTES PYTHON GLOBAIS ---", fg="cyan", bold=True)
    pkgs = audit_global_packages()
    if not pkgs:
        click.echo("Nenhum pacote pesado (>1MB) encontrado no global.")
    for name, size in pkgs[:15]:
        click.echo(f"  {_format_size(size):>10} | {name}")

    click.secho("\n--- PEGADA DE DISCO: CACHES DE APLICATIVOS (AppData) ---", fg="yellow", bold=True)
    bloat = audit_appdata_bloat()
    for name, size in bloat[:15]:
        click.echo(f"  {_format_size(size):>10} | {name}")

@cli.command()
@click.option("--force", is_flag=True, help="Executa a desinstalação real.")
def pip_purge(force):
    """Remove todos os pacotes Python globais (exceto os essenciais)."""
    from diskdiag.core.pip_purger import purge_global_packages
    
    dry_run = not force
    click.secho(f"\n[PIP-PURGE] {'SIMULANDO' if dry_run else 'EXECUTANDO'} LIMPEZA GLOBAL...", 
                fg="cyan" if dry_run else "red", bold=True)
    
    count, removed = purge_global_packages(dry_run=dry_run)
    
    if count == 0:
        click.echo("Nenhum pacote para remover.")
        return

    for pkg in removed:
        click.echo(f"  {'[CANDIDATO]' if dry_run else '[REMOVIDO]'} {pkg}")

    if dry_run:
        click.secho(f"\nTotal: {count} pacotes seriam removidos. Use --force para limpar.", fg="yellow")
    else:
        click.secho(f"\n[SUCESSO] {count} pacotes removidos do Python Global.", fg="green", bold=True)
