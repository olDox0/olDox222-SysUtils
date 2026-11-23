# energy_sys/cli/cmd_energy.py
from __future__ import annotations
import click
import subprocess
import time
import json
import winreg
from pathlib import Path
from energy_sys.platform.windows import win_power
from energy_sys.core import (
    power_estimator,
    process_impact,
    cost_calculator,
    power_strategies,
    services_impact,
    scheduled_tasks,
    report_parser,
    system_tweaks
)
from energy_sys.core import program_analyzer

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
    
    # ADICIONE ESTA LINHA:
    if "accuracy" in reading:
        cor_acc = "green" if "ALTA" in reading["accuracy"] else "yellow"
        click.echo(f"  Precisão da Leitura  : {click.style(reading['accuracy'], fg=cor_acc)}")

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
@click.option("--monitor", is_flag=True, help="Monitora o consumo em tempo real (Ctrl+C para parar).")
def cmd_top(limit: int, raw: bool, monitor: bool):
    """Lista os processos ou aplicativos que mais drenam energia."""
    if monitor:
        click.secho("\n--- MONITOR DE CPU EM TEMPO REAL (Ctrl+C para parar) ---", fg="cyan", bold=True)
        try:
            while True:
                reading = power_estimator.estimate_instant_watts()
                watts = reading["watts"]
                consumers = process_impact.get_top_energy_consumers(limit=3, instant_watts=watts, aggregate=True)
                
                click.echo("\033[H\033[J", nl=False)
                click.secho(f"⚡ Consumo Instantâneo: {watts:.2f} W", fg="yellow", bold=True)
                for p in consumers:
                    click.echo(f"  • {p['name']:<20} | CPU: {p['cpu_percent']:>5}% | Watts: {p['estimated_watts']:.2f}W")
                time.sleep(3)
        except KeyboardInterrupt:
            click.secho("\n[PARADO] Monitor encerrado.", fg="yellow")
        return

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
            # Formatação segura dos Watts (sem f-string aninhada)
            watts_str = f"{p['estimated_watts']:>9.2f} W"
            watts_colored = click.style(watts_str, fg='yellow')
            click.echo(
                f"  {p['instances']:>10} | "
                f"{p['cpu_percent']:>9}% | "
                f"{p['memory_mb']:>7} MB | "
                f"{watts_colored} | "
                f"{p['name']}"
            )
        click.echo("  " + "-" * 66 + "\n")
    else:
        click.echo(f"\n  {'PID':>8} | {'CPU%':>6} | {'MEMÓRIA':>10} | {'WATTS EST.':>11} | PROCESSO")
        click.echo("  " + "-" * 62)
        for p in consumers:
            watts_str = f"{p['estimated_watts']:>9.2f} W"
            watts_colored = click.style(watts_str, fg='yellow')
            click.echo(
                f"  {p['pid']:>8} | "
                f"{p['cpu_percent']:>5}% | "
                f"{p['memory_mb']:>7} MB | "
                f"{watts_colored} | "
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
    """Exibe telemetria de clock, carga e separação de núcleos P-Core vs E-Core."""
    click.secho("\n--- TELEMETRIA DA CPU & ARQUITETURA DE NÚCLEOS ---", fg="cyan", bold=True)
    cpu_info = power_strategies.get_cpu_telemetry()
    click.echo(f"  Modelo         : {click.style(cpu_info['cpu_name'], bold=True)}")
    
    tipo_arq = "Híbrida (Intel Performance + Efficiency)" if cpu_info['is_hybrid'] else "Simétrica Tradicional"
    click.echo(f"  Arquitetura    : {click.style(tipo_arq, fg='green' if cpu_info['is_hybrid'] else 'white', bold=True)}")
    click.echo(f"  Topologia      : {cpu_info['cores_physical']} Núcleos Físicos | {cpu_info['cores_logical']} Threads")
    
    curr_mhz = cpu_info['current_mhz']
    click.echo(f"  Clock Atual    : {click.style(f'{curr_mhz} MHz', fg='yellow', bold=True)}")
    if cpu_info['max_mhz'] > 0:
        click.echo(f"  Clock Máximo   : {cpu_info['max_mhz']} MHz")

    limit_val = power_strategies.query_current_dc_value("SUB_PROCESSOR", "PROCTHROTTLEMAX")
    limit_str = f"{limit_val}%" if limit_val is not None else "100% (Padrão)"
    color = "green" if (limit_val is not None and limit_val < 100) else "white"
    click.echo(f"  Teto na Bateria: {click.style(limit_str, fg=color, bold=True)}")

    click.echo("\n  Distribuição de Carga por Núcleo:")
    for idx, load in enumerate(cpu_info['load_per_core']):
        label = cpu_info['core_labels'].get(idx, "Core")
        is_p = "P-Core" in label
        is_e = "E-Core" in label
        
        tag_color = "cyan" if is_p else "magenta" if is_e else "white"
        tag = click.style(f"[{label}]", fg=tag_color, bold=True) if (is_p or is_e) else ""
        
        bar = "█" * int(load / 10) + "░" * (10 - int(load / 10))
        click.echo(f"    Thread {idx:>2} {tag:<28} : [{bar}] {load:>5.1f}%")
    click.echo("--------------------------------------------------\n")

@cli.command("audit")
@click.option("--duration", default=60, show_default=True, help="Duração do trace do powercfg /energy.")
@click.option("--deep", is_flag=True, help="Executa auditoria profunda (S0, Intel DTT, Drivers).")
def cmd_audit(duration: int, deep: bool):
    """Executa uma auditoria completa de energia (powercfg, serviços, tarefas)."""
    click.secho("\n--- AUDITORIA PROFUNDA DE ENERGIA (ENERGY SYS) ---", fg="cyan", bold=True)

    # 1. Powercfg /energy (normal)
    click.secho("\n[*] Executando 'powercfg /energy'...", fg="cyan")
    report_path = PROJECT_ROOT / "data" / "energy_reports" / "energy-report.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = f'powercfg /energy /duration {duration} /output "{report_path}"'
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            click.secho(f"  ✔ Relatório de energia gerado: {report_path.name}", fg="green")
        else:
            click.secho(f"  ✘ Falha ao gerar o relatório de energia.", fg="red")
    except Exception as e:
        click.secho(f"  ✘ Erro ao executar powercfg: {e}", fg="red")

    # 2. Serviços
    click.secho("\n[*] Auditando serviços em execução...", fg="cyan")
    try:
        service_report = services_impact.audit_service_impact()
        hogs = [s for s in service_report if s["is_known_power_hog"]]
        if hogs:
            click.secho(f"  ⚠ {len(hogs)} serviço(s) conhecidos por consumir bateria estão ativos:", fg="yellow")
            for s in hogs[:5]: # Limita a 5 para não poluir
                click.echo(f"    • {s['display_name']} ({s['name']})")
        else:
            click.secho("  ✔ Nenhum serviço conhecido por alto consumo está ativo.", fg="green")
    except Exception as e:
        click.secho(f"  ✘ Erro ao auditar serviços: {e}", fg="red")

    if deep:
        # 3. Intel DTT
        click.secho("\n[*] Verificando Intel Dynamic Tuning / IPF...", fg="cyan")
        dtt_info = system_tweaks.get_intel_dtt_version()
        if dtt_info:
            click.secho("  ✔ Driver Intel DTT/IPF encontrado:", fg="green")
            for line in dtt_info.splitlines():
                if line.strip():
                    click.echo(f"    {line.strip()}")
        else:
            click.secho("  ⚠ Intel DTT/IPF não encontrado ou não instalado.", fg="yellow")
            click.secho("    💡 Instale via Dell Command Update (sysutils win drivers --update).", fg="yellow")

        # 4. S0 Report Automático
        click.secho("\n[*] Gerando e analisando relatório de S0 (Modern Standby)...", fg="cyan")
        s0_path = PROJECT_ROOT / "data" / "energy_reports" / "s0_report.html"
        subprocess.run(f'powercfg /systempowerreport /output "{s0_path}"', shell=True, capture_output=True)
        if s0_path.exists():
            results = report_parser.parse_powercfg_report(s0_path)
            if results:
                click.secho("  🚨 Top 5 culpados do S0:", fg="red", bold=True)
                for r in results[:5]:
                    icon = "🚨" if r["is_known_culprit"] else "⚠️"
                    color = "red" if r["is_known_culprit"] else "yellow"
                    drain_str = f"({r['drain_mw']:.0f} mW)" if r.get("drain_mw") else ""
                    click.secho(f"    {icon} {r['percent_str']:>6} | {r['name']} {drain_str}", fg=color)
            else:
                click.secho("  ✔ Nenhum culpado encontrado no S0.", fg="green")

    click.echo("\n" + "="*60 + "\n")

@cli.command("services")
def cmd_services():
    """Lista serviços ativos e sinaliza os que podem ser desativados para economizar bateria."""
    click.secho("\n--- AUDITORIA DE SERVIÇOS DO WINDOWS ---", fg="cyan", bold=True)
    report = services_impact.audit_service_impact()
    if not report:
        click.echo("Nenhum serviço em execução detectado.")
        return
    click.echo(f"  {'STATUS':<12} | {'TIPO DE INÍCIO':<18} | SERVIÇO")
    click.echo("  " + "-" * 70)
    for s in report:
        if s["is_known_power_hog"]:
            status = click.style("⚠ ATIVO", fg="yellow", bold=True)
        else:
            status = click.style("  ok  ", fg="green")
        start_type = s.get("start_type", "unknown").split(".")[-1].upper()
        click.echo(f"  {status:<20} | {start_type:<18} | {s['display_name']} ({s['name']})")
    click.echo("  " + "-" * 70)
    click.secho("\n💡 Serviços com '⚠ ATIVO' são candidatos à desativação se você não usar a funcionalidade correspondente.", fg="yellow")
    click.echo("   Para desativar: services.msc > localize o serviço > Pare > Tipo de inicialização: Desativado.\n")

@cli.command("analyze")
@click.argument("report_file", type=click.Path(exists=True, dir_okay=False), required=False)
def cmd_analyze(report_file: str | None):
    """Analisa um relatório HTML do powercfg (/energy ou /sleepstudy) e extrai os culpados."""
    click.secho("\n--- ANALISADOR DE RELATÓRIOS POWERCFG ---", fg="cyan", bold=True)
    
    target_file = None
    if report_file:
        target_file = Path(report_file)
    else:
        default_energy = PROJECT_ROOT / "data" / "energy_reports" / "energy-report.html"
        user_home = Path.home()
        sleep_study = user_home / "Desktop" / "sleepstudy.html"
        
        if default_energy.exists():
            target_file = default_energy
        elif sleep_study.exists():
            target_file = sleep_study
        else:
            click.secho("✘ Nenhum relatório fornecido e nenhum relatório padrão encontrado.", fg="red")
            click.echo("Use: sysutils energy analyze caminho/para/relatorio.html")
            return

    click.echo(f"[*] Analisando arquivo: {target_file.name}")
    results = report_parser.parse_powercfg_report(target_file)
    
    if not results:
        click.secho("  ⚠ Nenhum dado de consumo de energia encontrado no arquivo. (É um HTML do powercfg?)", fg="yellow")
        return

    click.secho("\n  TOP CONSUMIDORES DE ENERGIA:", fg="white", bold=True)
    click.echo(f"  {'%':>8} | {'TIPO':<15} | {'NOME':<40}")
    click.echo("  " + "-" * 68)
    
    for r in results:
        if r["is_known_culprit"]:
            color = "red"
            icon = "🚨"
        elif r["percent"] > 5.0:
            color = "yellow"
            icon = "⚠️"
        else:
            color = "green"
            icon = "  "

        name_str = f"{icon} {r['name']}"
        
        click.echo(
            f"  {r['percent_str']:>8} | "
            f"{r['type']:<15} | "
            f"{click.style(name_str, fg=color)}"
        )
        
        if r["is_known_culprit"]:
            click.echo(f"           └─ 🚨 ALVO CONHECIDO: {report_parser.KNOWN_CULPRITS.get(r['name'].split('.')[0] + '.exe', 'Processo de alto consumo')}")

    click.echo("  " + "-" * 68)
    click.secho("\n💡 Dica: Processos em vermelho são os 'suspeitos de sempre' (Copilot, IPF, etc).", fg="yellow")
    click.echo("   Tente desativar os serviços associados ou agendar a tarefa para rodar apenas na tomada.")

@cli.command("blockers")
def cmd_blockers():
    """Mostra o que está impedindo o Windows de dormir (sleep requests)."""
    from energy_sys.core.report_parser import find_sleep_blockers
    click.secho("\n--- O QUE ESTÁ IMPEDINDO O SONO DO WINDOWS? ---", fg="cyan", bold=True)
    blockers = find_sleep_blockers()
    if not blockers:
        click.secho("  ✔ Nenhum bloqueio ativo. O Windows pode dormir.", fg="green")
    else:
        for b in blockers:
            click.secho(f"  🚨 {b}", fg="red")
    click.secho("\n💡 Dica: Se o Spotify aparecer aqui, execute 'taskkill /F /IM Spotify.exe' como Administrador.", fg="yellow")

@cli.command("events")
@click.option("--limit", default=10, show_default=True, help="Número de eventos a listar.")
def cmd_events(limit: int):
    """Mostra os últimos eventos de energia (Kernel-Power) do Windows."""
    click.secho("\n--- HISTÓRICO DE ENERGIA (KERNEL-POWER) ---", fg="cyan", bold=True)
    
    ps_cmd = (
        f"Get-WinEvent -LogName System | Where-Object {{ $_.Id -in 42, 107, 131 }} | "
        f"Select-Object -First {limit} @{{Name='Time';Expression={{$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}}}}, Id, @{{Name='Message';Expression={{$_.Message -replace '\\r?\\n', ' '}}}} | "
        f"ConvertTo-Json -Compress"
    )
    
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=20)
        if not res.stdout.strip():
            click.secho("Nenhum evento encontrado.", fg="yellow")
            return
            
        events = json.loads(res.stdout)
        if isinstance(events, dict): events = [events]
        
        for e in events:
            time_str = e.get("Time", "")
            ev_id = e.get("Id")
            msg = e.get("Message", "")
            
            if ev_id == 42:
                click.secho(f"  💤 [{time_str}] SUSPENSOU (ID 42)", fg="blue")
            elif ev_id == 107:
                click.secho(f"  ⏰ [{time_str}] ACORDOU (ID 107)", fg="green")
            elif ev_id == 131:
                click.secho(f"  🚨 [{time_str}] BLOQUEIO (ID 131)", fg="red")
                click.echo(f"       {msg[:200]}...")
                
    except Exception as e:
        click.secho(f"[ERRO] Falha ao ler eventos: {e}", fg="red")

@cli.command("lastwake")
def cmd_lastwake():
    """Mostra qual dispositivo ou software acordou o PC pela última vez."""
    click.secho("\n--- O QUE ACORDOU O PC PELA ÚLTIMA VEZ? ---", fg="cyan", bold=True)
    try:
        res = subprocess.run(["powercfg", "/lastwake"], capture_output=True, text=True, encoding="cp850", errors="ignore")
        lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
        for line in lines:
            if "Wake History Count" in line:
                click.secho(f"  {line}", fg="white", bold=True)
            elif "Type" in line or "Instance" in line or "Friendly Name" in line:
                click.echo(f"    {line}")
            else:
                click.echo(f"  {line}")
    except Exception as e:
        click.secho(f"[ERRO] {e}", fg="red")

@cli.command("kill-spotify")
def cmd_kill_spotify():
    """Força a parada de QUALQUER processo do Spotify (inclusive de outros usuários)."""
    click.secho("\n[*] Caçando processos do Spotify via PowerShell...", fg="cyan")
    ps_cmd = "Get-Process -Name 'Spotify' -ErrorAction SilentlyContinue | Stop-Process -Force"
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        click.secho("  ✔ Todos os processos do Spotify foram encerrados.", fg="green", bold=True)
    except Exception as e:
        click.secho(f"[ERRO] {e}", fg="red")


@cli.command("programs")
@click.option("--kill-pid", type=click.IntRange(min=1), default=None, help="Encerra um processo específico pelo PID.")
@click.option("--pid", type=click.IntRange(min=1), default=None, help="PID individual para alterar/restaurar afinidade.")
@click.option("--normal", "normal", is_flag=True, help="Restaura a afinidade original registrada para o PID.")
@click.option("--eco", "eco", is_flag=True, help="Restringe o PID aos E-cores.")
@click.option("--perf", "perf", is_flag=True, help="Restringe o PID aos P-cores.")
@click.option("--history", is_flag=True, help="Exibe o histórico de alterações de afinidade.")
@click.option("--history-limit", type=click.IntRange(min=1, max=500), default=20, show_default=True, help="Quantidade de eventos exibidos com --history.")
def cmd_programs(
    kill_pid: int | None,
    pid: int | None,
    normal: bool,
    eco: bool,
    perf: bool,
    history: bool,
    history_limit: int,
):
    """Analisa programas e controla a afinidade de um PID específico."""
    modes = [name for name, enabled in (("normal", normal), ("eco", eco), ("perf", perf)) if enabled]

    if history:
        if kill_pid is not None or pid is not None or modes:
            raise click.UsageError("--history não pode ser combinado com --kill-pid, --pid ou modos de afinidade.")
        from energy_sys.core import process_tuner
        try:
            events = process_tuner.get_affinity_history(history_limit)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

        click.secho("\n--- HISTÓRICO DE AFINIDADE DE CPU ---", fg="cyan", bold=True)
        if not events:
            click.secho("Nenhuma operação de afinidade registrada.", fg="yellow")
            return
        for event in events:
            timestamp = event.get("timestamp", "sem data")
            event_pid = event.get("pid", "?")
            process_name = event.get("name", "processo desconhecido")
            action = event.get("action", "?")
            mode = event.get("mode", "?")
            result = event.get("result", "?")
            previous = event.get("previous_affinity")
            current = event.get("current_affinity")
            click.echo(
                f"[{timestamp}] PID {event_pid} {process_name} | "
                f"{action}/{mode} | {result}"
            )
            if previous is not None or current is not None:
                click.echo(f"    Afinidade: {previous} -> {current}")
            details = event.get("details")
            if details:
                click.echo(f"    Detalhes: {details}")
        click.echo(f"\nArquivo: {process_tuner.HISTORY_FILE}")
        return

    if kill_pid is not None:
        if pid is not None or modes:
            raise click.UsageError("--kill-pid é independente; não combine com --pid ou modos de afinidade.")
        click.secho(f"[*] Tentando encerrar o processo PID {kill_pid}...", fg="yellow")
        if program_analyzer.kill_process_by_pid(kill_pid):
            click.secho(f"✔ Processo {kill_pid} encerrado.", fg="green")
        else:
            click.secho(f"✘ Falha ao encerrar PID {kill_pid} (talvez precise de Admin).", fg="red")
        return

    if pid is not None or modes:
        if pid is None:
            raise click.UsageError("Informe --pid <PID> junto com --normal, --eco ou --perf.")
        if len(modes) != 1:
            raise click.UsageError("Escolha exatamente um modo: --normal, --eco ou --perf.")

        from energy_sys.core import process_tuner
        mode = modes[0]
        if mode == "normal":
            ok, message, _ = process_tuner.restore_process_affinity(pid)
        else:
            ok, message, _ = process_tuner.apply_process_affinity(pid, mode)

        color = "green" if ok else "red"
        click.secho(f"\n[{'OK' if ok else 'FALHA'}] {message}", fg=color, bold=True)
        click.echo(f"Registro de estado: {process_tuner.STATE_FILE}")
        click.echo(f"Histórico: {process_tuner.HISTORY_FILE}")
        return

    click.secho("\n--- ANÁLISE DE PROGRAMAS & PROCESSOS ---", fg="cyan", bold=True)
    click.secho("\n[*] Programas que iniciam com o Windows:", fg="cyan")
    startups = program_analyzer.get_startup_programs()
    if not startups:
        click.secho("  (Nenhum detectado)", fg="yellow")
    else:
        for item in startups:
            name = item.get("Name", "Desconhecido")
            location = item.get("Location", "").split("\\")[-1]
            click.echo(f"  • {name:<35} [{location}]")

    click.secho("\n[*] Processos 'Zumbis' rodando agora:", fg="cyan")
    zombies = program_analyzer.get_zombie_processes()
    if not zombies:
        click.secho("  ✔ Nenhum processo zumbi ativo.", fg="green")
    else:
        click.echo(f"  {'PID':>8} | {'CPU%':>6} | {'USUÁRIO':<25} | PROCESSO")
        click.echo("  " + "-" * 60)
        for zombie in zombies:
            click.secho(
                f"  {zombie['pid']:>8} | {zombie['cpu']:>5}% | "
                f"{zombie['user']:<25} | {zombie['name']}",
                fg="red",
            )
        click.secho(
            "\nUse 'sysutils energy programs --pid <PID> --perf/--eco' "
            "para alterar um processo específico.",
            fg="yellow",
        )
        click.secho(
            "Use '--normal' para restaurar a afinidade original e '--history' para auditar.",
            fg="yellow",
        )

@cli.group("startup")
def startup_group():
    """Gerencia os programas de inicialização do Windows."""
    pass

@startup_group.command("manage")
def cmd_startup_manage():
    """Modo interativo: pergunta item por item se deseja desativar."""
    click.secho("\n--- GERENCIADOR INTERATIVO DE INICIALIZAÇÃO ---", fg="cyan", bold=True)
    startups = program_analyzer.get_startup_programs()
    
    if not startups:
        click.secho("Nenhum programa de inicialização encontrado.", fg="yellow")
        return

    click.echo("Pressione 's' para desativar, ou 'n' para manter.\n")
    
    for s in startups:
        name = s.get("Name")
        cmd = s.get("Command", "")
        
        click.secho(f"• {name}", fg="white", bold=True)
        click.echo(f"  Comando: {cmd[:80]}...")
        
        if click.confirm("  Desativar este item?", default=False):
            ok, msg = program_analyzer.disable_startup_item(name)
            if ok:
                click.secho(f"  ✔ {msg}", fg="green")
            else:
                click.secho(f"  ✘ {msg}", fg="red")
        else:
            click.echo("  ○ Mantido.")
        click.echo()

@startup_group.command("disable")
@click.argument("name")
def cmd_startup_disable(name: str):
    """Desativa um programa de inicialização pelo nome exato."""
    ok, msg = program_analyzer.disable_startup_item(name)
    cor = "green" if ok else "red"
    click.secho(f"\n[{ 'OK' if ok else 'FALHA' }] {msg}\n", fg=cor, bold=True)

@cli.command("energy-report")
def cmd_energy_report():
    """Gera e analisa o powercfg /energy (bloqueios em tempo real e CPU)."""
    click.secho("\n--- GERANDO RELATÓRIO DE ENERGIA (POWERCFG /ENERGY) ---", fg="cyan", bold=True)
    out_path = Path("data/energy_reports/energy_report.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    click.secho("[*] Coletando dados por 60 segundos (não feche o terminal)...", fg="yellow")
    subprocess.run(f'powercfg /energy /duration 60 /output "{out_path}"', shell=True, capture_output=True)
    
    if not out_path.exists():
        click.secho("✘ Falha ao gerar relatório.", fg="red")
        return
        
    results = report_parser.parse_energy_report(out_path)
    if not results:
        click.secho("✔ Nenhum problema de energia encontrado.", fg="green")
        return
        
    click.secho("\n--- BLOQUEIOS E PROBLEMAS DETECTADOS ---", fg="cyan")
    for r in results:
        color = "red" if r["severity"] == "CRITICAL" else "yellow"
        icon = "🚨" if r["severity"] == "CRITICAL" else "⚠️"
        click.secho(f"  {icon} [{r['process']}] {r['title']}", fg=color, bold=True)
        click.echo(f"      {r['description'][:100]}...")

@cli.command("fix-startup")
def cmd_fix_startup():
    """Remove OneDrive, Tailscale e Firefox da inicialização (HKCU)."""
    click.secho("\n--- REMOVENDO PROGRAMAS DA INICIALIZAÇÃO ---", fg="cyan", bold=True)
    
    targets = ["OneDrive", "Mozilla-Firefox-308046B0AF4A39CB", "Tailscale"]
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
        for t in targets:
            try:
                winreg.DeleteValue(key, t)
                click.secho(f"  ✔ Removido: {t}", fg="green")
            except FileNotFoundError:
                click.secho(f"  ○ Já estava desativado: {t}", fg="yellow")
        winreg.CloseKey(key)
    except Exception as e:
        click.secho(f"  ✘ Falha ao acessar o registro: {e}", fg="red")
        
    click.secho("\n💡 O Tailscale e o OneDrive podem ser iniciados manualmente quando necessário.", fg="yellow")

@cli.command("s0report")
def cmd_s0report():
    """Gera o relatório de Modern Standby (S0) e extrai os Top Offenders detalhados."""
    from energy_sys.core import report_parser
    click.secho("\n--- GERANDO RELATÓRIO DE MODERN STANDBY (S0) ---", fg="cyan", bold=True)
    out_path = Path("data/energy_reports/s0_report.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    click.secho("[*] Solicitando relatório ao Windows...", fg="yellow")
    subprocess.run(f'powercfg /systempowerreport /output "{out_path}"', shell=True, capture_output=True)

    if not out_path.exists():
        click.secho("✘ Falha ao gerar o relatório.", fg="red")
        return

    click.secho(f"✔ Relatório gerado em: {out_path}", fg="green")
    click.secho("\n[*] Analisando culpados do S0...", fg="cyan")

    results = report_parser.parse_powercfg_report(out_path)
    if not results:
        click.secho("⚠ Nenhum culpado encontrado.", fg="yellow")
        return

    # Cabeçalho da tabela
    click.secho(f"\n  {'% ATIVO':>8} | {'DRENO (mW)':>12} | {'TIPO':<10} | {'NOME':<35}", fg="white", bold=True)
    click.echo("  " + "-" * 75)
    
    for r in results[:15]: # Top 15
        color = "red" if r["is_known_culprit"] else "yellow"
        icon = "🚨" if r["is_known_culprit"] else "⚠️"
        
        drain_str = f"{r['drain_mw']:.0f} mW" if r.get("drain_mw") is not None else "---"
        
        click.secho(
            f"  {r['percent_str']:>8} | "
            f"{drain_str:>12} | "
            f"{r['type']:<10} | "
            f"{icon} {r['name']}", 
            fg=color
        )
        
    click.echo("  " + "-" * 75)
    click.secho("\n💡 Dica: O 'DRENO (mW)' mostra o consumo real em miliwatts de cada componente durante o sono.", fg="yellow")

@cli.command("tweak")
@click.option("--apply", is_flag=True, help="Aplica os ajustes de economia (requer Admin).")
@click.option("--rollback", is_flag=True, help="Reverte os ajustes para o padrão.")
@click.option("--list", "list_all", is_flag=True, help="Lista os ajustes disponíveis.")
def cmd_tweak(apply: bool, rollback: bool, list_all: bool):
    """Aplica ou reverte ajustes cirúrgicos de economia de energia na bateria."""
    click.secho("\n--- AJUSTES DE ENERGIA (TWEAK) ---", fg="cyan", bold=True)
    
    if not system_tweaks.is_admin():
        click.secho("⚠  Aviso: Alguns ajustes exigem privilégios de Administrador.", fg="yellow")

    tweaks = {
        "modern-standby": {
            "name": "Desativar Rede no Modern Standby",
            "desc": "Impede o Wi-Fi de drenar bateria quando o PC está fechado.",
            "action": lambda disable: system_tweaks.apply_modern_standby_network(disable)
        },
        "fast-startup": {
            "name": "Desativar Inicialização Rápida",
            "desc": "Garante desligamento completo e evita drenos fantasmas.",
            "action": lambda disable: system_tweaks.apply_fast_startup(disable)
        },
        "hybrid-cpu": {
            "name": "Priorizar E-Cores na Bateria",
            "desc": "Força o uso de núcleos de eficiência para economizar carga.",
            "action": lambda disable: system_tweaks.apply_hybrid_cpu_policy(disable)
        }
    }

    if list_all or (not apply and not rollback):
        click.echo("\nAjustes disponíveis:")
        for tid, t in tweaks.items():
            click.echo(f"  • {click.style(tid, fg='cyan', bold=True)}: {t['name']}")
            click.echo(f"    {t['desc']}")
        click.echo("\n💡 Use 'sysutils energy tweak --apply' para ativar ou '--rollback' para reverter.\n")
        return

    if apply and rollback:
        click.secho("[ERRO] Escolha --apply ou --rollback, não ambos.", fg="red")
        return

    is_disable = apply
    mode_str = "APLICANDO" if apply else "REVERTENDO"
    click.secho(f"\n[*] {mode_str} ajustes de economia...", fg="yellow", bold=True)
    
    for tid, t in tweaks.items():
        ok, msg = t["action"](is_disable)
        cor = "green" if ok else "red"
        icon = "✔" if ok else "✘"
        click.secho(f"  {icon} {t['name']}: {msg}", fg=cor)
        
    click.secho(f"\n💡 {'Reinicie o PC para aplicar as mudanças.' if apply else 'Configurações restauradas.'}", fg="green")


@cli.group("hardware")
def hardware_group():
    """Gerencia a leitura real de hardware (Watts via LibreHardwareMonitor)."""
    pass

@hardware_group.command("install")
def cmd_hw_install():
    """Instala o pacote PyLibreHardwareMonitor via pip."""
    click.secho("\n[*] Instalando PyLibreHardwareMonitor...", fg="cyan")
    import sys
    import subprocess
    try:
        # Roda silenciosamente o pip install
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "PyLibreHardwareMonitor"],
            check=True
        )
        click.secho("✔ [OK] Biblioteca instalada com sucesso!", fg="green", bold=True)
        click.secho("💡 Nota: Para ler os Watts reais, execute este terminal como Administrador.", fg="yellow")
    except subprocess.CalledProcessError as e:
        click.secho(f"✘ [FALHA] Erro ao instalar: {e}", fg="red", bold=True)

@hardware_group.command("test")
def cmd_hw_test():
    """Testa a leitura de Watts reais do hardware."""
    from energy_sys.core import hardware_monitor
    click.secho("\n--- TESTE DE HARDWARE (RAPL) ---", fg="cyan", bold=True)
    
    click.secho("[*] Inicializando sensores...", fg="yellow")
    watts = hardware_monitor.read_power()
    
    if watts is not None:
        click.secho(f"✔ [OK] Leitura obtida com sucesso!", fg="green", bold=True)
        click.secho(f"  • CPU Package Power: {watts:.2f} W", fg="white", bold=True)
    else:
        click.secho("✘ [FALHA] Não foi possível ler os Watts.", fg="red", bold=True)
        click.echo("  • Motivos prováveis:")
        click.echo("    1. A biblioteca PyLibreHardwareMonitor não está instalada.")
        click.echo("    2. O terminal não está rodando como Administrador.")
        click.echo("    3. O seu processador não expõe o sensor RAPL via .NET.")
        click.echo("    dica, tente este\n      winget install --id namazso.PawnIO --exact --silent --accept-package-agreements --accept-source-agreements")

@hardware_group.command("diag")
def cmd_hw_diag():
    """Exibe todos os hardwares e sensores detectados (Raio-X do sistema)."""
    from energy_sys.core import hardware_monitor
    click.secho("\n--- DIAGNÓSTICO COMPLETO DE HARDWARE ---", fg="cyan", bold=True)
    
    click.secho("[*] Lendo sensores...", fg="yellow")
    hws = hardware_monitor.dump_diagnostic()
    
    if not hws:
        click.secho("✘ Nenhum hardware detectado. (Verifique se está rodando como Admin).", fg="red")
        return

    for hw in hws:
        click.secho(f"\n[Hardware] {hw['name']} ({hw['type']})", fg="green", bold=True)
        for s in hw["sensors"]:
            val = f"{s['value']:.2f}" if isinstance(s['value'], (int, float)) else str(s['value'])
            color = "yellow" if s["type"] == "Power" else "white"
            click.secho(f"  • {s['name']:<35} | {s['type']:<12} | {val}", fg=color)
            
    click.secho("\n💡 Dica: Sensores em amarelo são de Potência (Watts).", fg="cyan")

@cli.command("doctor")
def cmd_doctor():
    """Diagnostica o ambiente para leitura real de hardware."""
    from energy_sys.core import doctor
    click.secho("\n--- DOUTOR DE HARDWARE (ENERGY SYS) ---", fg="cyan", bold=True)
    
    click.secho("[*] Executando checagens...", fg="yellow")
    all_ok, logs = doctor.run_diagnostics()
    
    for log in logs:
        color = "green" if log.startswith("✔") else "red"
        click.secho(f"  {log}", fg=color)
        
    if all_ok:
        click.secho("\n✔ [SAÚDE OK] Seu sistema está pronto para telemetria de hardware real.", fg="green", bold=True)
    else:
        click.secho("\n⚠ [AÇÃO NECESSÁRIA] Corrija os itens marcados com ✘ acima.", fg="yellow", bold=True)
        click.echo("  Dica: Use 'sysutils energy hardware install' e 'sysutils energy hardware install-driver'.")
    click.echo()

@hardware_group.command("install-driver")
def cmd_hw_install_driver():
    """Instala o driver PawnIO via winget (necessário para leitura de sensores)."""
    click.secho("\n[*] Instalando driver PawnIO...", fg="cyan")
    cmd = [
        "winget", "install", "--id", "namazso.PawnIO",
        "--exact", "--silent",
        "--accept-package-agreements", "--accept-source-agreements"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="cp850")
        if res.returncode == 0:
            click.secho("✔ [OK] PawnIO instalado com sucesso!", fg="green", bold=True)
            click.secho("💡 Reinicie o PC se os sensores não responderem imediatamente.", fg="yellow")
        else:
            click.secho(f"✘ [FALHA] {res.stderr or res.stdout}", fg="red")
    except Exception as e:
        click.secho(f"✘ [ERRO] {e}", fg="red")

@cli.command("pin")
@click.argument("process_name")
@click.option("--core-type", type=click.Choice(["e-cores", "p-cores"]), default="e-cores", help="Tipo de núcleo para fixar o processo.")
def cmd_pin(process_name: str, core_type: str):
    """Força um processo a rodar apenas em núcleos específicos (Afinidade de CPU)."""
    from energy_sys.core import process_tuner
    click.secho(f"\n--- AFINIDADE DE CPU ---", fg="cyan", bold=True)
    click.secho("[AVISO] Comando legado por nome: todas as instâncias com esse nome podem ser afetadas.", fg="yellow")
    click.echo(f"[*] Fixando '{process_name}' nos {core_type.upper()}...")
    
    ok, msg, count = process_tuner.pin_process(process_name, core_type)
    
    if ok:
        click.secho(f"✔ [OK] {msg}", fg="green", bold=True)
        click.secho(f"  • {count} processo(s) afetado(s).", fg="white")
        click.secho("\n💡 Dica: Reinicie o processo se ele não responder bem.", fg="yellow")
        click.secho("   Use 'sysutils energy top --monitor' para ver o impacto nos Watts.", fg="cyan")
    else:
        click.secho(f"✘ [FALHA] {msg}", fg="red")
