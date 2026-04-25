# netdiag/cli/commands.py
import click
from netdiag.core import net_optimizer
from netdiag.platform.windows import net_tweaks

@click.group()
def cli():
    """NetDiag — Otimização de Conexão e Redução de Overhead de Rede."""
    pass

@cli.command()
def optimize():
    """Aplica o Perfil Vulcan de Internet (Baixa Latência)."""
    click.secho("[VULCAN] Otimizando Stack de Rede...", fg="cyan", bold=True)
    
    # 1. Registro (Latência e Parâmetros Globais)
    net_tweaks.apply_tcp_latency_tweaks()
    net_tweaks.optimize_global_net_params() # <--- Certifique-se que esta linha está aqui
    click.echo("  [OK] Parâmetros TCP/IP otimizados para baixa latência.")
    
    # 2. Serviços (RAM Saver)
    net_optimizer.disable_delivery_optimization()
    click.echo("  [OK] Delivery Optimization desativado (Foco em economia de RAM).")
    
    # 3. DNS e Stack
    net_optimizer.set_fast_dns()
    net_optimizer.flush_dns_and_reset_stack()
    click.echo("  [OK] Stack TCP/IP reiniciado e DNS Cloudflare configurado.")
    
    click.secho("\n[SUCESSO] Rede Otimizada.", fg="green", bold=True)