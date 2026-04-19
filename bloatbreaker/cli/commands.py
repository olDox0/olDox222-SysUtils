# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

# [VULCAN-SKIP] Proteção contra introspecção Click
# bloatbreaker/cli/commands.py
import click
from bloatbreaker.core import scanner

@click.group()
def cli():
    """BloatBreaker — Identifica e analisa lixo sistêmico do Windows."""
    pass

@cli.command()
def analyze():
    """Analisa o sistema em busca de bloatware e impacto na RAM/Pagefile."""
    click.secho("[BLOAT-BREAKER] Iniciando análise profunda...", fg="cyan")
    
    impact = scanner.get_pagefile_usage()
    click.echo(f"\n--- IMPACTO NA MEMÓRIA ---")
    click.echo(f"  RAM em uso:      {impact['ram_used_percent']}%")
    click.echo(f"  Pagefile em uso: {impact['pagefile_used_mb']:.2f} MB / {impact['pagefile_total_mb']:.2f} MB")
    
    apps = scanner.get_installed_bloatware()
    click.echo(f"\n--- APLICATIVOS (UWP) IDENTIFICADOS ({len(apps)}) ---")
    for app in apps:
        click.echo(f"  [!] {app}")
        
    services = scanner.get_active_bloat_services()
    click.echo(f"\n--- SERVIÇOS DE TELEMETRIA ATIVOS ({len(services)}) ---")
    for svc in services:
        click.secho(f"  [X] {svc}", fg="red")

    if not apps and not services:
        click.secho("\n[PARABÉNS] Nenhum bloatware óbvio detectado!", fg="green")
        
    apps = scanner.get_installed_bloatware() 
    click.echo(f"\n--- APLICATIVOS IDENTIFICADOS ({len(apps)}) ---")
    for app in apps:
        click.echo(f"  [!] {app} (Ainda presente no Sistema)")
        
@cli.command(name="break")
@click.option("--force", is_flag=True, help="Executa a remoção agressiva.")
def break_bloat(force):
    if not force:
        click.secho("[AVISO] Use --force para execução real.", fg="yellow")
        return

    apps = scanner.get_installed_bloatware()
    services = scanner.get_active_bloat_services()

    click.secho("\n[VULCAN-AGGRESSIVE] Iniciando limpeza de Camada 2...", fg="red", bold=True)

    # 1. Apps (Provisioned)
    for app in apps:
        click.echo(f"  Expurgando matriz de {app}...", nl=False)
        if scanner.remove_bloatware_aggressive(app):
            click.secho(" [DELETADO]", fg="green")
        else:
            click.secho(" [FALHA - RODOU COMO ADMIN?]", fg="red")

    # 2. Serviços (WSearch, etc)
    for svc in services:
        click.echo(f"  Desativando serviço {svc}...", nl=False)
        if scanner.disable_service(svc):
            click.secho(" [DESATIVADO]", fg="green")
        else:
            click.secho(" [FALHA]", fg="red")

    click.secho("\n[FINISH] Bloatware expurgado. Verifique a RAM agora.", bold=True)
