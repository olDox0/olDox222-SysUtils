# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

# cli/main.py
import click
import os
import sys
from pathlib import Path

# --- INJEÇÃO VULCAN ---
# Adiciona a raiz do projeto ao path para localizar 'bloatbreaker' e 'engine'
project_root = str(Path(__file__).parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ----------------------

from diskdiag.cli.commands     import cli as disk_commands
from ramdiag.cli.commands      import cli as ram_commands
from doxbackup.cli.commands    import cli as backup_commands
from bloatbreaker.cli.commands import cli as bloat_commands

@click.group()
def cli():
    """SysUtils — Suite de Diagnóstico de Sistema."""
    pass

# Adiciona o módulo diskdiag como um sub-comando 'disk'
cli.add_command(disk_commands,   name="disk"  )
cli.add_command(ram_commands,    name="ram"   )
cli.add_command(backup_commands, name="backup")
cli.add_command(bloat_commands,  name="bloat" )

# Atalho para rodar direto o diskdiag se o usuário preferir
@click.command()
@click.pass_context
def diskdiag(ctx):
    """Atalho para diagnóstico de disco."""
    ctx.invoke(disk_commands)

if __name__ == "__main__":
    cli()