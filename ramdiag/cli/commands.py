# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

# ramdiag/cli/commands.py

import click
import psutil
from ramdiag.core import monitor as ram_monitor

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
    # Uso do nome renomeado
    data = ram_monitor.get_ram_usage() 
    click.echo("\n--- STATUS DA MEMÓRIA RAM ---")
    click.echo(f"  Total:     {format_bytes(data['total'])}")
    click.echo(f"  Em Uso:    {format_bytes(data['used'])} ({data['percent']}%)")
    click.echo(f"  Disponível: {format_bytes(data['available'])}")
    
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
    
    # Uso do nome renomeado
    procs = ram_monitor.get_detailed_processes(limit)
    
    if not verbose:
        click.echo(f"  {'PID':>8} | {'MEMÓRIA':>12} | {'PROCESSO'}")
        click.echo("-" * 50)
        for p in procs:
            click.echo(f"  {p['pid']:>8} | {format_bytes(p['memory']):>12} | {p['name']}")
    else:
        for p in procs:
            click.secho(f"\n▶ {p['name']} (PID: {p['pid']})", fg="cyan", bold=True)
            click.echo(f"  └─ Memória:   {format_bytes(p['memory'])}")
            click.echo(f"  └─ Pai:       {p['parent_name']} (PPID: {p['ppid']})")
            click.echo(f"  └─ Filhos:    {p['children_count']} processos ativos")
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
    
    # Uso do nome renomeado
    summary_data = ram_monitor.get_aggregated_usage()
    for item in summary_data[:limit]:
        mem_str = format_bytes(item['total_memory'])
        click.echo(f"  {item['instances']:>10} | {mem_str:>15} | {item['name']}")

@cli.command()
def trim():
    """Libera RAM forçando processos a devolverem memória não utilizada."""
    click.secho("[VULCAN] Iniciando RAM Trim (EmptyWorkingSet)...", fg="cyan")
    from ramdiag.core.monitor import trim_memory
    
    count = trim_memory()
    click.secho(f"[SUCESSO] Memória otimizada em {count} processos.", fg="green", bold=True)
    click.echo("Verifique o 'ram summary' para ver a queda no consumo.")

# ramdiag/cli/commands.py (Adição)

@cli.command()
@click.option("--aggressive", is_flag=True, help="Desativa compressão de memória para reduzir latência.")
@click.option("--force", is_flag=True, help="Executa sem confirmação (requer Admin).")
def optimize(aggressive, force):
    """Aplica o Perfil Vulcan de Otimização DDR3."""
    if not force:
        click.confirm("Isso alterará chaves de registro do sistema. Continuar?", abort=True)
    
    click.secho("[VULCAN] Iniciando Otimização de Arquitetura DDR3...", fg="cyan", bold=True)
    
    from ramdiag.core.optimizer import apply_ddr3_optimization_profile, manage_memory_compression
    
    # Aplica Tweaks de Kernel
    logs = apply_ddr3_optimization_profile()
    for log in logs:
        click.echo(f"  {log}")
        
    # Gerencia Compressão
    if aggressive:
        click.echo("  [!] Desativando Memory Compression (Modo Aggressive)...", nl=False)
        if manage_memory_compression(False):
            click.secho(" [OK]", fg="green")
        else:
            click.secho(" [FALHA]", fg="red")
            
    click.secho("\n[SUCESSO] Otimizações aplicadas. Reinicie para efeito total.", fg="green", bold=True)

# ramdiag/cli/commands.py (Adição)

@cli.command()
@click.option("--apply", is_flag=True, help="Aplica as configurações calculadas.")
def pagefile(apply):
    """Analisa e configura o arquivo de paginação (Smart Pagefile)."""
    from ramdiag.core.pagefile import calculate_smart_pagefile, apply_pagefile_settings
    
    click.secho("[VULCAN] Analisando Perfil de Paginação...", fg="cyan")
    config = calculate_smart_pagefile()
    
    click.echo(f"  Tipo de Disco Detectado: {click.style(config['drive_type'], bold=True)}")
    click.echo(f"  RAM Total Detectada:     {psutil.virtual_memory().total // (1024**2)} MB")
    click.echo("-" * 45)
    click.echo(f"  Proposta Vulcan:")
    click.echo(f"    Tamanho Mínimo: {config['min_size']} MB")
    click.echo(f"    Tamanho Máximo: {config['max_size']} MB")
    click.echo(f"    Estratégia:     {'TAMANHO FIXO (Anti-Fragmentação)' if config['is_fixed'] else 'DINÂMICA (Otimizada para SSD)'}")

    if apply:
        if click.confirm("\nDeseja aplicar essas configurações agora? (Requer reinicialização)"):
            if apply_pagefile_settings(config['min_size'], config['max_size']):
                click.secho("[SUCESSO] Smart Pagefile configurado.", fg="green", bold=True)
            else:
                click.secho("[FALHA] Não foi possível aplicar. Verifique se é Administrador.", fg="red")
    else:
        click.echo("\nUse --apply para executar as mudanças.")
        
@cli.command()
@click.option("--limit", default=80, help="Porcentagem de uso para disparar a limpeza.")
@click.option("--freq", default=5, help="Frequência de checagem em segundos.")
def monitor(limit, freq):
    """Ativa o monitoramento inteligente e automático da RAM (Autopilot)."""
    from ramdiag.core.autopilot import run_autopilot
    
    click.secho(f"--- VULCAN RAM AUTOPILOT ---", fg="magenta", bold=True)
    click.echo(f"Ideal para sistemas DDR3 com pouca memória.")
    click.echo(f"Pressione CTRL+C para encerrar.")
    click.echo("-" * 30)
    
    run_autopilot(threshold_percent=limit, interval=freq)
