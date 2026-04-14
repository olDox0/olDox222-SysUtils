# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

# ramdiag/cli/commands.py

import click
from ramdiag.core import monitor

def format_bytes(n):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024: return f"{n:.2f} {unit}"
        n /= 1024

@click.group()
def cli():
    """RamDiag — Diagnóstico e Monitoramento de Memória RAM."""
    pass

@cli.command()
def status():
    """Exibe o status atual da memória global."""
    data = monitor.get_ram_usage()
    click.echo("\n--- STATUS DA MEMÓRIA RAM ---")
    click.echo(f"  Total:     {format_bytes(data['total'])}")
    click.echo(f"  Em Uso:    {format_bytes(data['used'])} ({data['percent']}%)")
    click.echo(f"  Disponível: {format_bytes(data['available'])}")
    
    # Barra visual simples
    bar_len = 20
    filled = int(data['percent'] / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    click.echo(f"  Progresso: [{bar}]")

@cli.command()
@click.option("--limit", default=10, help="Número de processos.")
@click.option("--verbose", "-v", is_flag=True, help="Mostra linha de comando e parentesco.")
def top(limit, verbose):
    """Exibe os processos com detalhes de hierarquia."""
    click.echo(f"\n--- MONITOR DE PROCESSOS (TOP {limit}) ---")
    
    procs = monitor.get_detailed_processes(limit)
    
    if not verbose:
        click.echo(f"  {'PID':>8} | {'MEMÓRIA':>12} | {'PROCESSO'}")
        click.echo("-" * 50)
        for p in procs:
            click.echo(f"  {p['pid']:>8} | {format_bytes(p['memory']):>12} | {p['name']}")
    else:
        # Modo Detalhado
        for p in procs:
            click.secho(f"\n▶ {p['name']} (PID: {p['pid']})", fg="cyan", bold=True)
            click.echo(f"  └─ Memória:   {format_bytes(p['memory'])}")
            click.echo(f"  └─ Pai:       {p['parent_name']} (PPID: {p['ppid']})")
            click.echo(f"  └─ Filhos:    {p['children_count']} processos ativos")
            
            # Formata a linha de comando para não quebrar o terminal
            cmd = p['cmdline']
            if len(cmd) > 80: cmd = cmd[:77] + "..."
            click.echo(f"  └─ Comando:   {cmd}")
            click.echo("-" * 30)
        
@cli.command()
@click.option("--limit", default=10)
def summary(limit):
    """Resumo de consumo agrupado por aplicativo."""
    click.echo(f"\n--- RESUMO DE CONSUMO POR APP (TOP {limit}) ---")
    click.echo(f"  {'INSTÂNCIAS':>10} | {'MEMÓRIA TOTAL':>15} | {'APLICATIVO'}")
    click.echo("-" * 55)
    
    summary_data = monitor.get_aggregated_usage()
    for item in summary_data[:limit]:
        mem_str = format_bytes(item['total_memory'])
        click.echo(f"  {item['instances']:>10} | {mem_str:>15} | {item['name']}")