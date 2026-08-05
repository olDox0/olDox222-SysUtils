# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]
# diskdiag/cli/commands.py

import click
from pathlib import Path

from utils.doxcolors import Fore, Style
from utils.error_handler import handle_cli_error
from utils.error_info import handle_error
from diskdiag.analysis.disk_analysis import _format_size

# --- LOCALIZAÇÃO ABSOLUTA DO PROJETO ---
# parents[2] sobe para .../Projeto SysUtils/
SYS_ROOT = Path(__file__).resolve().parents[2]

# Definimos os caminhos padrão como absolutos
DEFAULT_DB = str(SYS_ROOT / "data" / "db" / "files.db")
DEFAULT_IDX = str(SYS_ROOT / "data" / "vulcan_idx")
# ---------------------------------------


@click.group()
def cli():
    """DiskDiag - Diagnóstico de Uso de Disco."""
    pass


@cli.command()
@click.argument("path")
@click.option("--db", default=DEFAULT_DB, show_default=True) # Usando o caminho absoluto
@click.option("--prune", is_flag=True, help="Remove do banco arquivos que não existem mais no disco.")
def scan(path, db, prune):
    """Varre um diretório e indexa os arquivos."""
    from diskdiag.core.indexer import run_indexer, prune_database
    os.makedirs(os.path.dirname(db), exist_ok=True)
    run_indexer(path, db)
    
    # [NOVO] Se a flag for passada, faz a limpeza direcionada
    if prune:
        prune_database(db, root_filter=path)

@cli.command()
@click.argument("path", required=False)
@click.option("--db", default=DEFAULT_DB, show_default=True)
@click.option("--past", "-p", is_flag=True)
@click.option("--extension", "-e", is_flag=True)
def analyze(path, db, past, extension):
    from diskdiag.analysis.disk_analysis import run_analysis
    run_analysis(db, path_filter=path, analyze_folders=past, analyze_extensions=extension)

@cli.command()
@click.option("--db", default=DEFAULT_DB, show_default=True)
@click.option("--out", default=DEFAULT_IDX, show_default=True)
def optimize(db, out):
    from diskdiag.core.vulcan_index import compress_db_to_vulcan
    os.makedirs(out, exist_ok=True)
    compress_db_to_vulcan(db, out)

@cli.command()
@click.argument("query")
@click.option("--db", default=DEFAULT_DB)
def find(query, db):
    """Busca ultra-rápida via Vulcan Bitmap."""
    import sqlite3
    import time
    # Importação corrigida:
    from diskdiag.core.storage import search_files, _format_size

    conn = sqlite3.connect(db)
    t0 = time.perf_counter()
    
    results = search_files(conn, query)
    
    dur = (time.perf_counter() - t0) * 1000
    
    click.echo(f"\n--- RESULTADOS DA BUSCA ('{query}') [{dur:.2f}ms] ---")
    if not results:
        click.echo("[-] Nada encontrado.")
        return

    for path, size in results:
        click.echo(f"  {_format_size(size):>10} | {path}")
        
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

@cli.command()
@click.option("--db", default=DEFAULT_DB)
def vacuum(db):
    """Compactação profunda do banco usando Vulcan Dict."""
    from diskdiag.core.db_optimizer import compress_database_paths
    import os
    
    size_before = os.path.getsize(db) / 1024
    compress_database_paths(db)
    
    # Comando padrão do SQLite para reconstruir o arquivo e liberar espaço
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute("VACUUM")
    conn.close()
    
    size_after = os.path.getsize(db) / 1024
    click.echo(f"Economia: {size_before:.2f}KB -> {size_after:.2f}KB")
    
@cli.command()
@click.option("--db", default=DEFAULT_DB)
def optimize_db(db):
    """Compactação profunda Vulcan: reduz o tamanho do banco de dados existente."""
    import os
    import sqlite3
    from diskdiag.core import vulcan_dict
    # GARANTA QUE ESTE NOME BATA COM O ARQUIVO ACIMA
    from diskdiag.core.compression_presets import WINDOWS_STANDARD_DICT

    if not os.path.exists(db):
        click.secho(f"✘ Erro: Banco {db} não encontrado.", fg="red")
        return

    size_before = os.path.getsize(db)
    click.echo(f"[*] Iniciando compressão Vulcan em: {os.path.basename(db)}")
    click.echo(f"[*] Tamanho atual: {size_before / (1024*1024):.2f} MB")

    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    
    # 1. Busca caminhos planos (que não começam com V!)
    rows = cursor.execute("SELECT id, path FROM files WHERE path NOT LIKE 'V!%'").fetchall()
    
    click.echo(f"[*] Processando {len(rows)} entradas...")
    
    count = 0
    with click.progressbar(rows, label="Comprimindo") as bar:
        for file_id, path in bar:
            if len(path) > 30:
                comp = "V!" + vulcan_dict.compress_with_dict(path, WINDOWS_STANDARD_DICT)
                cursor.execute("UPDATE files SET path = ? WHERE id = ?", (comp, file_id))
                count += 1
    
    conn.commit()
    
    # 2. LIBERAÇÃO DE ESPAÇO FÍSICO
    # Sem o VACUUM, o arquivo .db continuará com 146MB mesmo após a compressão
    click.echo("[*] Executando VACUUM para reconstruir o banco...")
    conn.execute("VACUUM")
    conn.close()

    size_after = os.path.getsize(db)
    reduction = (1 - (size_after / size_before)) * 100
    
    click.secho(f"\n✅ Otimização concluída!", fg="green", bold=True)
    click.echo(f"   Entradas afetadas : {count}")
    click.echo(f"   Tamanho final     : {size_after / (1024*1024):.2f} MB")
    click.secho(f"   Economia de disco : {reduction:.2f}%", fg="cyan", bold=True)
    
@cli.command()
@click.option("--min-size", default=100, help="Tamanho mínimo em KB.")
@click.option("--db", default=DEFAULT_DB)
def dups(min_size, db):
    """Localiza duplicatas pesadas via Vulcan Bitmaps."""
    import sqlite3
    import time
    from diskdiag.core.storage import find_duplicates, _format_size

    conn = sqlite3.connect(db)
    t0 = time.perf_counter()
    
    clones_map = find_duplicates(conn, min_size)
    
    dur = (time.perf_counter() - t0) * 1000
    click.echo(f"[*] Escaneamento de assinaturas concluído em {dur:.2f}ms")

    if not clones_map:
        click.secho("✅ Nenhum clone detectado com este perfil.", fg="green")
        return

    for sig, paths in clones_map.items():
        size = int(sig.split('_')[0])
        click.echo(f"\n{Fore.RED}SINAL DE DUPLICATA: {_format_size(size)}{Style.RESET_ALL}")
        for p in paths:
            click.echo(f"  • {p}")
            
@cli.command()
@click.option("--db", default=DEFAULT_DB, show_default=True)
def prune(db):
    """Remove do banco TODOS os arquivos que não existem mais no disco."""
    from diskdiag.core.indexer import prune_database
    prune_database(db, root_filter=None)
