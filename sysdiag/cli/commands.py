# sysdiag/cli/commands.py
import click
from sysdiag.core import os_optimizer
from sysdiag.platform.windows import registry_tweaks

@click.group()
def cli():
    """WinDiag — Otimização do Sistema Operacional Windows."""
    pass

@cli.command()
@click.option("--force", is_flag=True, help="Executa sem avisos.")
def optimize(force):
    """Aplica o Perfil Vulcan de Otimização do Windows."""
    if not force:
        click.confirm("Isso aplicará tweaks de registro e desativará serviços de telemetria. Continuar?", abort=True)

    click.secho("[VULCAN] Iniciando Otimização do Windows...", fg="cyan", bold=True)

    # 1. Registro
    registry_tweaks.apply_responsiveness_tweaks()
    click.echo("  [OK] Tweaks de responsividade do Kernel aplicados.")

    # 2. Serviços
    os_optimizer.disable_telemetry_services()
    click.echo("  [OK] Telemetria e rastreamento desativados.")

    # 3. Performance
    os_optimizer.set_high_performance_power()
    click.echo("  [OK] Plano de Energia configurado para 'Alto Desempenho'.")

    # 4. Efeitos Visuais
    os_optimizer.optimize_visual_effects()
    click.echo("  [OK] Efeitos visuais simplificados (Foco em performance).")

    registry_tweaks.apply_ntfs_optimizations()
    click.echo("  [OK] Otimizações de I/O e NTFS aplicadas (DDR3 Focus).")
    
    registry_tweaks.apply_io_priority_tweaks()
    click.echo("  [OK] Prioridade de Scheduling ajustada para High.")

    click.secho("\n[SUCESSO] Sistema Windows Otimizado.", fg="green", bold=True)
    click.echo("Recomendado reiniciar para aplicar todas as mudanças de Kernel.")

# sysdiag/cli/commands.py (Adições)

@cli.command()
def startup():
    """Auditoria de aplicativos que iniciam com o sistema."""
    from sysdiag.core.startup_manager import list_startup_apps
    click.secho("\n--- APLICATIVOS DE INICIALIZAÇÃO ---", fg="yellow", bold=True)
    apps = list_startup_apps()
    
    if not apps:
        click.echo("Nenhum aplicativo encontrado nos registros de inicialização.")
        return

    click.echo(f"{'NOME':<20} | {'ORIGEM':<10} | {'COMANDO'}")
    click.echo("-" * 75)
    for app in apps:
        cmd = app['path'] if len(app['path']) < 40 else app['path'][:37] + "..."
        click.echo(f"{app['name']:<20} | {app['root']:<10} | {cmd}")
    
    click.secho("\n[DICA] Use o Gerenciador de Tarefas para desativar os desnecessários.", fg="cyan")

@cli.command()
def maintenance():
    """Limpeza profunda de componentes do Windows (WinSxS e Logs)."""
    import subprocess
    click.secho("[VULCAN] Iniciando Manutenção de Componentes...", fg="cyan")
    
    # 1. Limpeza da pasta WinSxS (Onde o Windows guarda atualizações velhas)
    click.echo("  -> Limpando base de componentes (DISM)...")
    subprocess.run("dism /online /cleanup-image /startcomponentcleanup", shell=True)
    
    # 2. Limpeza de Logs de Eventos do Windows
    click.echo("  -> Limpando logs de eventos acumulados...")
    ps_cmd = 'wevtutil el | Foreach-Object {wevtutil cl "$_"}'
    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
    
    click.secho("[SUCESSO] Espaço em disco e performance de I/O recuperados.", fg="green", bold=True)