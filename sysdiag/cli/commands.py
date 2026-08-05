# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

# [VULCAN-SKIP] Proteção contra introspecção Click
# sysdiag/cli/commands.py
import click
import subprocess

from sysdiag.core import os_optimizer
from sysdiag.platform.windows import registry_tweaks
from utils.doxcolors import colors, NexusUI

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
    NexusUI.decode_effect("INICIANDO MANUTENÇÃO VULCAN", duration=1.0)
    
    # 1. Limpeza WinSxS (Base de componentes)
    click.echo(f"\n{colors.Fore.PRIMARY}[1/2] Analisando base de componentes (WinSxS)...{colors.Fore.RESET}")
    click.echo(f"{colors.Fore.DIM}Isso removerá versões obsoletas de atualizações do Windows.{colors.Fore.RESET}")
    
    # Rodamos o DISM (requer admin)
    # /StartComponentCleanup: limpa versões antigas
    # /ResetBase: torna a limpeza permanente (economiza mais espaço)
    cmd_dism = "dism /online /cleanup-image /startcomponentcleanup"
    try:
        subprocess.run(cmd_dism, shell=True, check=True)
        click.secho("  [OK] Componentes otimizados.", fg="green")
    except Exception as e:
        click.secho(f"  [FALHA] DISM requer privilégios de Administrador.", fg="red")

    # 2. Limpeza de Logs de Eventos
    click.echo(f"\n{colors.Fore.PRIMARY}[2/2] Limpando Logs de Eventos do Windows...{colors.Fore.RESET}")
    ps_cmd = 'wevtutil el | Foreach-Object {wevtutil cl "$_"}'
    try:
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, check=True)
        click.secho("  [OK] Logs de eventos limpos.", fg="green")
    except:
        click.secho("  [FALHA] Não foi possível limpar os logs.", fg="red")

    click.echo("\n" + "="*60)
    click.echo(NexusUI.gradient_text("MANUTENÇÃO DE SISTEMA CONCLUÍDA"))
    click.echo("="*60)