# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

import click
from utils.error_handler import handle_cli_error

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
@click.option("--db", default="data/db/files.db", show_default=True)
def analyze(db):
    """Analisa os dados coletados."""
    try:
        from diskdiag.analysis.disk_analysis import run_analysis
        run_analysis(db)
    except Exception as e:
        handle_cli_error(e)