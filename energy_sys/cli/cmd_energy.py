# energy_sys/cli/cmd_energy.py
from __future__ import annotations
import click
from pathlib import Path
from energy_sys.platform.windows import win_power
from energy_sys.core import power_estimator, process_impact, cost_calculator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = PROJECT_ROOT / "data" / "energy_reports"

@click.group(name="energy")
def cli():
    """EnergySys — Telemetria de Potência Elétrica, Bateria e Custo de Energia."""
    pass

@cli.command("config")
@click.option("--tariff", type=float, help="Define a tarifa padrão em R$/kWh.")
@click.option("--provider", type=str, help="Apelido da fornecedora de energia.")
def cmd_config(tariff: float | None, provider: str | None):
    """Configura permanentemente a concessionária de energia e tarifa."""
    cfg = cost_calculator.load_energy_config()
    t = tariff if tariff is not None else cfg.get("tariff_kwh", 0.9543)
    p = provider if provider is not None else cfg.get("provider", "Elderbarry")
    
    cost_calculator.save_energy_config(tariff_kwh=t, provider=p)
    click.secho(f"\n[OK] Configuração de energia salva com sucesso!", fg="green", bold=True)
    click.echo(f"  Concessionária : {p}")
    click.echo(f"  Tarifa Fixada  : R$ {t:.4f} / kWh\n")

@cli.command("status")
@click.option("--tariff", type=float, default=None, help="Sobrescrever tarifa pontualmente.")
def cmd_status(tariff: float | None):
    """Exibe o consumo elétrico instantâneo em Watts e o custo em R$."""
    click.secho("\n--- TELEMETRIA ENERGÉTICA (ENERGY SYS) ---", fg="cyan", bold=True)
    
    p_status = win_power.get_system_power_status()
    if p_status:
        click.echo(f"  Fonte de Alimentação : {click.style(p_status['ac_status'], bold=True)}")
        if p_status['has_battery']:
            pct = p_status['percent']
            cor = "green" if pct > 40 else "yellow" if pct > 20 else "red"
            click.echo(f"  Carga da Bateria     : {click.style(f'{pct}%', fg=cor, bold=True)}")

    reading = power_estimator.estimate_instant_watts()
    watts = reading["watts"]
    
    click.echo(f"\n  Consumo Instantâneo  : {click.style(f'{watts:.2f} W', fg='yellow', bold=True)}")
    click.echo(f"  Método de Leitura    : {reading['method']}")

    # Cálculo de Autonomia Dinâmica Real para Bateria
    wmi_data = reading.get("details")
    if p_status and p_status['has_battery'] and not p_status['ac_connected'] and watts > 0:
        rem_mwh = (wmi_data or {}).get("remaining_mwh")
        if rem_mwh:
            hours_left = (rem_mwh / 1000.0) / watts
            h = int(hours_left)
            m = int((hours_left - h) * 60)
            cor_autonomia = "green" if hours_left > 3.0 else "yellow" if hours_left > 1.5 else "red"
            click.echo(f"  Autonomia Estimada   : {click.style(f'{h}h {m:02d}min', fg=cor_autonomia, bold=True)} (com a carga atual)")

    costs = cost_calculator.calculate_energy_cost(watts, tariff_kwh=tariff)
    click.secho(f"\n--- PROJEÇÃO DE CUSTO ({costs['provider'].upper()}: R$ {costs['tariff_kwh']:.4f}/kWh) ---", fg="green", bold=True)
    click.echo(f"  • Por Hora (Uso Contínuo)  : R$ {costs['cost_hour']:.4f}")
    click.echo(f"  • Por Dia (Jornada de 8h)  : R$ {costs['cost_day_8h']:.2f}")
    click.echo(f"  • Por Mês (Trabalho 8h/dia): R$ {costs['cost_month_8h']:.2f}")
    click.echo(f"  • Por Mês (Ligado 24h/dia) : R$ {costs['cost_month_24h']:.2f}")
    click.echo("----------------------------------------------------------\n")

@cli.command("top")
@click.option("--limit", default=8, show_default=True, help="Quantidade de itens a listar.")
@click.option("--raw", is_flag=True, help="Exibe processos isolados por PID em vez de agrupar.")
def cmd_top(limit: int, raw: bool):
    """Lista os processos ou aplicativos que mais drenam energia."""
    reading = power_estimator.estimate_instant_watts()
    watts = reading["watts"]
    
    modo = "Processos Individuais (RAW)" if raw else "Famílias de Aplicativos (Agrupado)"
    click.secho(f"\n[*] Mapeando impacto de energia [{modo}] (Total: {watts:.1f} W)...", fg="cyan")
    consumers = process_impact.get_top_energy_consumers(limit=limit, instant_watts=watts, aggregate=not raw)
    
    if not consumers:
        click.echo("Nenhum processo consumindo carga expressiva no momento.")
        return

    if not raw:
        click.echo(f"\n  {'INSTÂNCIAS':>10} | {'CPU% TOTAL':>10} | {'MEMÓRIA':>10} | {'WATTS EST.':>11} | APLICATIVO")
        click.echo("  " + "-" * 66)
        for p in consumers:
            click.echo(
                f"  {p['instances']:>10} | "
                f"{p['cpu_percent']:>9}% | "
                f"{p['memory_mb']:>7} MB | "
                f"{click.style(f'{p["estimated_watts"]:>9.2f} W', fg='yellow')} | "
                f"{p['name']}"
            )
        click.echo("  " + "-" * 66 + "\n")
    else:
        click.echo(f"\n  {'PID':>8} | {'CPU%':>6} | {'MEMÓRIA':>10} | {'WATTS EST.':>11} | PROCESSO")
        click.echo("  " + "-" * 62)
        for p in consumers:
            click.echo(
                f"  {p['pid']:>8} | "
                f"{p['cpu_percent']:>5}% | "
                f"{p['memory_mb']:>7} MB | "
                f"{click.style(f'{p["estimated_watts"]:>9.2f} W', fg='yellow')} | "
                f"{p['name']}"
            )
        click.echo("  " + "-" * 62 + "\n")

@cli.command("report")
def cmd_report():
    """Gera auditoria detalhada de saúde de bateria e eficiência do Windows."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_DIR / "battery_report.html"
    
    click.secho("[*] Solicitando auditoria de eficiência energética ao Windows...", fg="cyan")
    if win_power.generate_powercfg_battery_report(report_file):
        click.secho(f"[OK] Relatório oficial gerado com sucesso!", fg="green", bold=True)
        click.echo(f"Arquivo: {report_file}")
        import os
        os.startfile(str(report_file))
    else:
        click.secho("[FALHA] Relatório de bateria indisponível neste equipamento.", fg="yellow")

