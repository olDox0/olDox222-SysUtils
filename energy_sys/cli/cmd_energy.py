# energy_sys/cli/cmd_energy.py
from __future__ import annotations
import click
from pathlib import Path
from energy_sys.platform.windows import win_power
from energy_sys.core import power_estimator, process_impact, cost_calculator, power_strategies

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
    """Configura a concessionária de energia e a tarifa padrão."""
    cfg = cost_calculator.load_energy_config()
    t = tariff if tariff is not None else cfg.get("tariff_kwh", 0.9543)
    p = provider if provider is not None else cfg.get("provider", "Elderbarry")
    
    cost_calculator.save_energy_config(tariff_kwh=t, provider=p)
    click.secho(f"\n[OK] Configuração de energia salva!", fg="green", bold=True)
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

@cli.command("optimize")
@click.option("--list", "list_all", is_flag=True, help="Lista todas as estratégias, riscos e estado atual.")
@click.option("--enable", "enable_id", type=str, default=None, help="ID da estratégia a ser ATIVADA (ex: cpu-limit).")
@click.option("--disable", "disable_id", type=str, default=None, help="ID da estratégia a ser DESATIVADA.")
@click.option("--rollback", is_flag=True, help="Restaura os valores da linha de base de fábrica.")
@click.option("--apply", is_flag=True, help="Executa as alterações no Windows. Sem isto roda em Dry-Run.")
def cmd_optimize(list_all: bool, enable_id: str | None, disable_id: str | None, rollback: bool, apply: bool):
    """Gerenciador Tático de Eficiência Energética com Rollback Cirúrgico."""
    baseline = power_strategies.ensure_baseline_snapshot()

    if list_all or (not enable_id and not disable_id and not rollback):
        click.secho("\n" + "=" * 75, fg="cyan")
        click.secho(" 🛡️  CATÁLOGO DE ESTRATÉGIAS DE ENERGIA (SELEÇÃO CIRÚRGICA)", fg="cyan", bold=True)
        click.secho("=" * 75, fg="cyan")
        click.echo("  • Cada estratégia atua EXCLUSIVAMENTE quando o PC opera na BATERIA (DC).")
        click.echo("  • Na tomada (AC), todas as restrições são desarmadas automaticamente a 100%.\n")

        for s_id, s in power_strategies.STRATEGIES.items():
            current_val = power_strategies.query_current_dc_value(s["sub"], s["setting"])
            if current_val is None and "alt_sub" in s:
                current_val = power_strategies.query_current_dc_value(s["alt_sub"], s["alt_setting"])
                
            is_active = (current_val == s["eco_value"]) if current_val is not None else False
            status_text = click.style("[ATIVA]", fg="green", bold=True) if is_active else click.style("[DESATIVADA]", fg="yellow")
            
            risk_color = "red" if "ALTO" in s["risk"] else "yellow" if "MÉDIO" in s["risk"] else "green"
            risk_label = click.style(s["risk"], fg=risk_color, bold=True)

            click.echo(f"  ID: {click.style(s_id, fg='cyan', bold=True)}  {status_text}  (Risco: {risk_label})")
            click.echo(f"  └─ Nome    : {s['name']}")
            click.echo(f"  └─ Ganho   : {s['benefits']}")
            click.echo(f"  └─ Alerta  : {s['risk_details']}")
            click.echo("  " + "-" * 71)

        click.echo("\n👉 Como ativar:    sysutils energy optimize --enable <ID> --apply")
        click.echo("👉 Como desativar: sysutils energy optimize --disable <ID> --apply")
        click.echo("👉 Como reverter:  sysutils energy optimize --rollback --apply\n")
        return

    # MODO ROLLBACK BASELINE
    if rollback:
        click.secho("\n[ROLLBACK] Restaurando parâmetros para a linha de base original...", fg="yellow", bold=True)
        if not apply:
            click.secho("  [DRY-RUN] Valores da baseline que seriam restaurados:", fg="cyan")
            for s_id, base_val in baseline.items():
                click.echo(f"    • {s_id} -> valor original de fábrica: {base_val}")
            click.secho("\nExecute com --apply para efetivar.", fg="yellow")
            return

        for s_id, base_val in baseline.items():
            s = power_strategies.STRATEGIES.get(s_id)
            if s:
                alt_sub = s.get("alt_sub")
                alt_set = s.get("alt_setting")
                power_strategies.apply_power_setting(s["sub"], s["setting"], base_val, alt_sub, alt_set)
        click.secho("[SUCESSO] Sistema restaurado para os parâmetros de fábrica registrados no baseline!\n", fg="green", bold=True)
        return

    # MODO ENABLE
    if enable_id:
        if enable_id not in power_strategies.STRATEGIES:
            click.secho(f"[ERRO] Estratégia '{enable_id}' não encontrada. Use --list para verificar os IDs.", fg="red")
            return
        
        strat = power_strategies.STRATEGIES[enable_id]
        click.secho(f"\n[*] Estratégia: {strat['name']}", fg="cyan", bold=True)
        click.echo(f"    ID        : {enable_id}")
        click.echo(f"    Benefício : {strat['benefits']}")
        click.echo(f"    RISCO     : {strat['risk']} — {strat['risk_details']}")

        if not apply:
            click.secho("\n[DRY-RUN] Nenhuma alteração realizada. Para aplicar, execute:", fg="yellow")
            click.echo(f"   sysutils energy optimize --enable {enable_id} --apply\n")
            return

        if "ALTO" in strat["risk"]:
            if not click.confirm(click.style("\n⚠️  Esta estratégia altera a conduta térmica do hardware. Confirmar?", fg="red", bold=True), default=False):
                click.secho("[ABORTADO] Operação cancelada.", fg="yellow")
                return

        ok = power_strategies.apply_power_setting(
            strat["sub"], strat["setting"], strat["eco_value"],
            strat.get("alt_sub"), strat.get("alt_setting")
        )
        if ok:
            click.secho(f"\n✔ [SUCESSO] Estratégia '{enable_id}' ativada com sucesso!", fg="green", bold=True)
        else:
            click.secho(f"\n✘ [FALHA] Não suportado pelo hardware ou ACPI desta máquina.", fg="red")

    # MODO DISABLE
    if disable_id:
        if disable_id not in power_strategies.STRATEGIES:
            click.secho(f"[ERRO] Estratégia '{disable_id}' não encontrada.", fg="red")
            return
        strat = power_strategies.STRATEGIES[disable_id]
        base_val = baseline.get(disable_id, strat["default_value"])

        if not apply:
            click.secho(f"\n[DRY-RUN] A estratégia '{disable_id}' seria restaurada para o valor original: {base_val}.", fg="yellow")
            click.echo("Execute com --apply para efetivar.")
            return

        ok = power_strategies.apply_power_setting(
            strat["sub"], strat["setting"], base_val,
            strat.get("alt_sub"), strat.get("alt_setting")
        )
        if ok:
            click.secho(f"\n✔ [SUCESSO] Estratégia '{disable_id}' desativada (restaurada para o padrão {base_val}).", fg="green")
        else:
            click.secho(f"\n✘ [FALHA] Falha ao restaurar configuração no powercfg.", fg="red")

@cli.command("cpu")
def cmd_cpu():
    """Exibe o diagnóstico de clock, throttling e impacto do teto de frequência."""
    click.secho("\n--- TELEMETRIA DA CPU & LIMITES ENERGÉTICOS ---", fg="cyan", bold=True)
    cpu_info = power_strategies.get_cpu_telemetry()
    click.echo(f"  Modelo         : {click.style(cpu_info['cpu_name'], bold=True)}")
    click.echo(f"  Topologia      : {cpu_info['cores_physical']} Núcleos Físicos | {cpu_info['cores_logical']} Threads")
    curr_mhz = cpu_info['current_mhz']
    click.echo(f"  Clock Atual    : {click.style(f'{curr_mhz} MHz', fg='yellow', bold=True)}")
    if cpu_info['max_mhz'] > 0:
        click.echo(f"  Clock Máximo   : {cpu_info['max_mhz']} MHz")

    # Verifica o teto ativo na bateria
    limit_val = power_strategies.query_current_dc_value("SUB_PROCESSOR", "PROCTHROTTLEMAX")
    limit_str = f"{limit_val}%" if limit_val is not None else "100% (Padrão)"
    color = "green" if (limit_val is not None and limit_val < 100) else "white"
    click.echo(f"  Teto na Bateria: {click.style(limit_str, fg=color, bold=True)}")

    click.echo("\n  Carga por Núcleo:")
    for idx, load in enumerate(cpu_info['load_per_core']):
        bar = "█" * int(load / 10) + "░" * (10 - int(load / 10))
        click.echo(f"    Core {idx} : [{bar}] {load:>5.1f}%")
    click.echo("-------------------------------------------------\n")


