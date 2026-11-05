# -*- coding: utf-8 -*-
# android_sys/cli/cmd_android.py
"""
Zeus: Orquestrador CLI de Comandos para AndroidSys.
Suporta Pareamento Wi-Fi, Conexão Direta, Espelhamento sem fio (Scrcpy)
e Gestão do SDK Mínimo Headless (RIT 1).
Conformidade: ProDeNov 5.3 (Dry-run por padrão).
"""
from __future__ import annotations
import click
from pathlib import Path
from android_sys.core import installer, adb_manager, scrcpy_runner, sdk_installer, apk_builder, audio_policy

@click.group(name="android")
def cli():
    """AndroidSys — Controle, Espelhamento e Ferramentas Android Sem Fio."""
    pass

# ==============================================================================
# SUBGRUPO: SDK HEADLESS (RIT 1)
# ==============================================================================
@cli.group("sdk")
def sdk_group():
    """Gerenciamento do SDK Mínimo Headless (aapt2, d8, zipalign, android.jar)."""
    pass

@sdk_group.command("status")
def cmd_sdk_status():
    """Auditoria forense das ferramentas de compilação em disco (ProDeNov 3.1.4)."""
    click.secho("\n" + "=" * 75, fg="cyan")
    click.secho(" 🛡️  AUDITORIA FORENSE: ANDROID SDK HEADLESS (SEM GRADLE)", fg="cyan", bold=True)
    click.secho("=" * 75, fg="cyan")
    
    audit = sdk_installer.audit_sdk_tools()
    click.echo(f"  {'FERRAMENTA':<15} | {'STATUS':<10} | {'TAMANHO':>10} | CAMINHO")
    click.echo("  " + "-" * 71)

    for name, info in audit.items():
        cor = "green" if "✔" in info["status"] else "yellow" if "⚠" in info["status"] else "red"
        status_styled = click.style(info["status"], fg=cor, bold=True)
        click.echo(f"  {name:<15} | {status_styled:<19} | {info['size_formatted']:>10} | {info['path']}")

    click.echo("=" * 75)
    
    if sdk_installer.is_sdk_ready():
        click.secho("✔ [PRONTO] Todas as ferramentas essenciais para build estão operacionais!\n", fg="green", bold=True)
    else:
        click.secho("⚠ [INCOMPLETO] Execute 'sysutils android sdk setup' para simular ou '--apply' para baixar.\n", fg="yellow")

@sdk_group.command("setup")
@click.option("--apply", "apply_changes", is_flag=True, help="Efetua o download real. Sem isto roda em Dry-Run seguro.")
def cmd_sdk_setup(apply_changes: bool):
    """Instalação cirúrgica das build-tools mínimas com salvaguarda Dry-Run (ProDeNov 5.3)."""
    modo = "EXECUÇÃO REAL" if apply_changes else "DRY-RUN (Simulação Segura)"
    click.secho(f"\n[*] Iniciando procedimento de setup do SDK Headless [{modo}]...", fg="cyan", bold=True)

    ok, msg, logs = sdk_installer.install_minimal_sdk(apply_changes=apply_changes)
    
    for l in logs:
        click.echo(f"  {l}")

    if ok:
        cor = "green" if apply_changes else "cyan"
        click.secho(f"\n[{'SUCESSO' if apply_changes else 'SIMULAÇÃO OK'}] {msg}", fg=cor, bold=True)
        if not apply_changes:
            click.secho("👉 Para autorizar o download cirúrgico dos ~83 MB, execute:", fg="yellow")
            click.secho("   sysutils android sdk setup --apply\n", fg="yellow", bold=True)
    else:
        click.secho(f"\n✘ [FALHA] {msg}\n", fg="red", bold=True)

# ==============================================================================
# COMANDOS DE CONECTIVIDADE SEM FIO & KVM
# ==============================================================================
@cli.command("pair")
@click.argument("target", required=False)
@click.argument("code", required=False)
def cmd_pair(target: str | None, code: str | None):
    """Pareia com o celular usando a porta efêmera e o código de 6 dígitos."""
    installer.ensure_binaries()
    if not target:
        target = click.prompt("Digite o IP:Porta da caixa de pareamento (ex: 192.168.18.105:45817)")
    if not code:
        code = click.prompt("Digite o código de pareamento de 6 dígitos (ex: 271711)")

    click.secho(f"[*] Pareando com {target}...", fg="cyan")
    ok, msg = adb_manager.pair_device(target, code)
    if ok:
        click.secho(f"\n✔ [SUCESSO] Celular pareado com sucesso!", fg="green", bold=True)
        click.echo("👉 1. Feche a caixa de pareamento no celular.")
        click.echo("👉 2. Veja a porta principal na tela de Depuração sem fio.")
        ip = target.split(":")[0]
        click.secho(f"👉 3. Execute: sysutils android connect {ip}:<PORTA_PRINCIPAL>\n", fg="yellow", bold=True)
    else:
        click.secho(f"\n✘ [FALHA] {msg}", fg="red")

@cli.command("connect")
@click.argument("target", required=False)
def cmd_connect(target: str | None):
    """Conecta ao celular via Wi-Fi. Aceita 'IP:porta' ou apenas a 'porta'."""
    installer.ensure_binaries()
    if not target:
        cfg = adb_manager.load_config()
        last_ip = cfg.get("last_ip", "192.168.18.105")
        target = click.prompt("Digite a porta (ou IP:porta)", default=f"{last_ip}:5555")

    click.secho(f"[*] Conectando ao Android em {target}...", fg="cyan")
    ok, msg = adb_manager.connect_device(target)
    if ok:
        click.secho(f"✔ [CONECTADO] {msg}", fg="green", bold=True)
        click.echo("👉 Para abrir a tela no PC: sysutils android mirror")
    else:
        click.secho(f"✘ [FALHA] {msg}", fg="red")

@cli.command("mirror")
@click.option("--fps", default=60, show_default=True, help="Taxa de quadros máxima.")
@click.option("--size", default=1024, show_default=True, help="Resolução máxima.")
@click.option("--pc-audio", is_flag=True, help="Envia áudio para o PC (Padrão: mantém no celular).")
def cmd_mirror(fps: int, size: int, pc_audio: bool):
    """Abre a tela do celular (o áudio permanece tocando no celular por padrão)."""
    installer.ensure_binaries()
    devs = adb_manager.get_connected_devices()
    if not devs:
        click.secho("[ERRO] Nenhum celular conectado. Conecte primeiro com 'sysutils android connect'.", fg="red")
        return

    target = devs[0]
    click.secho(f"[*] Espelhando {target} ({fps} FPS) | Áudio no Celular...", fg="cyan")
    proc = scrcpy_runner.start_scrcpy(target, mode="mirror", max_fps=fps, max_size=size, forward_audio=pc_audio)
    proc.wait()

@cli.command("otg")
def cmd_otg():
    """Modo KVM físico no celular: mouse e teclado do PC sem streaming de vídeo."""
    installer.ensure_binaries()
    devs = adb_manager.get_connected_devices()
    if not devs:
        click.secho("[ERRO] Nenhum celular conectado.", fg="red")
        return
    target = devs[0]
    click.secho(f"[*] Modo KVM ativo em {target} (Zero uso de CPU/Vídeo)...", fg="cyan")
    proc = scrcpy_runner.start_scrcpy(target, mode="otg")
    proc.wait()

@cli.command("devices")
def cmd_devices():
    """Lista celulares conectados via Wi-Fi."""
    installer.ensure_binaries()
    devs = adb_manager.get_connected_devices()
    click.echo("\n--- DISPOSITIVOS ANDROID CONECTADOS ---")
    if not devs:
        click.secho("  ○ Nenhum aparelho conectado via Wi-Fi.", fg="yellow")
    for d in devs:
        click.secho(f"  ● {d} (Ativo)", fg="green", bold=True)
    click.echo("---------------------------------------\n")

@cli.command("build")
@click.option("--source", "src_dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="Diretório de assets HTML/JS customizados. Padrão: template Benzaiten.")
@click.option("--out", "out_file", type=click.Path(dir_okay=False), default=None,
              help="Caminho de saída do APK gerado.")
@click.option("--apply", "apply_changes", is_flag=True, help="Efetua o build real. Padrão: Dry-Run seguro.")
def cmd_build(src_dir: str | None, out_file: str | None, apply_changes: bool):
    """Compila o APK com a interface webview do Benzaiten sem Android Studio."""
    modo = "EXECUÇÃO REAL" if apply_changes else "DRY-RUN (Simulação)"
    click.secho(f"\n[*] Iniciando pipeline de build Benzaiten NeoGUI [{modo}]...", fg="cyan", bold=True)

    source_path = Path(src_dir) if src_dir else None
    dest_path = Path(out_file) if out_file else None

    ok, msg, logs = apk_builder.build_apk(
        source_assets_dir=source_path,
        output_apk=dest_path,
        dry_run=not apply_changes
    )

    for l in logs:
        click.echo(f"  {l}")

    if ok:
        cor = "green" if apply_changes else "cyan"
        click.secho(f"\n[{'SUCESSO' if apply_changes else 'SIMULAÇÃO OK'}] {msg}", fg=cor, bold=True)
        if not apply_changes:
            click.secho("👉 Para efetivar a geração do APK, execute: sysutils android build --apply\n", fg="yellow", bold=True)
    else:
        click.secho(f"\n✘ [FALHA] {msg}\n", fg="red", bold=True)

@cli.command("run")
@click.option("--source", "src_dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="Diretório de assets customizados.")
def cmd_run(src_dir: str | None):
    """Pipeline completo de 1 comando: Compila ➔ Envia pelo ar (Wi-Fi) ➔ Inicia Scrcpy."""
    click.secho("\n🚀 [AUTO-RUN] Disparando pipeline completo de desenvolvimento móvel...", fg="cyan", bold=True)

    # 1. Compilação
    source_path = Path(src_dir) if src_dir else None
    ok_b, msg_b, logs_b = apk_builder.build_apk(source_assets_dir=source_path, dry_run=False)
    if not ok_b:
        click.secho(f"✘ [FALHA NO BUILD] {msg_b}", fg="red")
        return

    apk_path = Path(apk_builder.BUILD_DIR / "benzaiten_app.apk")
    click.secho(f"✔ [BUILD OK] {apk_path.name} pronto para envio.", fg="green")

    # 2. Envio sem fio via ADB
    devs = adb_manager.get_connected_devices()
    if not devs:
        click.secho("[!] Celular desconectado. Tentando reconexão Wi-Fi...", fg="yellow")
        adb_manager.connect_device("192.168.18.105")
        devs = adb_manager.get_connected_devices()

    if not devs:
        click.secho("[ERRO] Não foi possível localizar o celular na rede Wi-Fi. Conecte com 'sysutils android connect'.", fg="red")
        return

    target = devs[0]
    click.secho(f"[*] Instalando {apk_path.name} em {target} pelo ar...", fg="cyan")
    ok_i, msg_i = adb_manager.install_apk(target, apk_path)
    if not ok_i:
        click.secho(f"✘ [FALHA NA INSTALAÇÃO] {msg_i}", fg="red")
        return

    click.secho("✔ [INSTALADO] Iniciando espelhamento de tela e áudio no celular...", fg="green", bold=True)

    # 3. Abre no celular via intent e inicia espelhamento com Scrcpy
    adb_manager.run_adb(["-s", target, "shell", "monkey", "-p", "com.doxoade.benzaiten", "-c", "android.intent.category.LAUNCHER", "1"])
    proc = scrcpy_runner.start_scrcpy(target, mode="mirror", max_fps=60, max_size=1024, forward_audio=False)
    proc.wait()

@cli.group("audio")
def audio_group():
    """Android Audiio Management Systems - A2MS"""
    pass

@audio_group.command("patch")
@click.option("--apps", "-a", required=True,
              help="Pacotes separados por vírgula (ex: com.spotify.music,com.google.android.youtube).")
@click.option("--mode", type=click.Choice(audio_policy.AUDIO_MODES),
              default="mix", show_default=True,
              help="mix=paralelismo total; duck=abaixa volume; exclusive=padrão Android.")
@click.option("--apply", "apply_changes", is_flag=True,
              help="Efetua a alteração real via ADB. Sem isto, DRY-RUN.")
@click.option("--safe-only", is_flag=True,
              help="Recusa pacotes fora da lista segura (VLC, Spotify, YT Music).")
@click.option("--restart", is_flag=True,
              help="Faz 'am force-stop' nos pacotes após --apply (releitura do appops).")
def cmd_audio_patch(apps: str, mode: str, apply_changes: bool, safe_only: bool, restart: bool):
    """Aplica TAKE_AUDIO_FOCUS ignore/allow aos pacotes indicados."""   # ← ADICIONAR
    from android_sys.core import audio_state
    pkg_list = [p.strip() for p in apps.split(",") if p.strip()]
    seen = set()
    pkg_list = [p for p in pkg_list if not (p in seen or seen.add(p))]

    # NOVO: snapshot ANTES de aplicar (só em --apply)
    if apply_changes and not safe_only:
        ok_s, msg_s, _ = audio_state.take_snapshot(pkg_list, label=f"pre-patch:{mode}")
        if ok_s:
            click.secho(f"  📸 Snapshot pré-patch salvo.", fg="cyan")

    ok, msg, logs = audio_policy.apply_audio_policy(
        packages=pkg_list, mode=mode, dry_run=not apply_changes,
        safe_only=safe_only, restart=restart,
    )
    for l in logs:
        click.echo(f"  {l}")
    cor = "green" if ok and apply_changes else ("cyan" if ok else "red")
    click.secho(f"\n[{'OK' if ok else 'FALHA'}] {msg}\n", fg=cor, bold=True)

    # NOVO: log no histórico
    if apply_changes:
        audio_state.log_operation(
            "patch", pkg_list, mode,
            "success" if ok else "fail",
            f"safe_only={safe_only} restart={restart}",
        )


@audio_group.command("known")
def cmd_audio_known():
    """Lista pacotes conhecidos que toleram (ou não) TAKE_AUDIO_FOCUS=ignore."""
    click.secho("\n✔ Confirmados seguros (continuam a tocar com ignore):", fg="green", bold=True)
    for p in audio_policy.KNOWN_IGNORE_SAFE:
        click.echo(f"  ● {p}")
    click.secho("\n⚠ Prováveis (relatos, não testados aqui):", fg="yellow", bold=True)
    for p in audio_policy.KNOWN_IGNORE_SUSPECTED:
        click.echo(f"  ● {p}")
    click.secho("\n✘ NÃO use 'ignore' (param ao receber negação de foco):", fg="red", bold=True)
    click.echo("  ● Navegadores em geral (Vivaldi, Firefox, Chrome)")
    click.echo("  ● Apps de videochamada (WhatsApp, Telegram)")
    click.echo("  ● Players que exigem foco exclusivo\n")

@audio_group.command("snapshot")
@click.option("--apps", "-a", default=None,
              help="Pacotes a capturar. Padrão: usa pacotes do último patch.")
@click.option("--label", "-l", default="manual", show_default=True,
              help="Rótulo do snapshot (para identificar no histórico).")
def cmd_audio_snapshot(apps: str, label: str):
    """Tira snapshot do estado atual (para rollback posterior)."""
    from android_sys.core import audio_state
    if apps:
        pkg_list = [p.strip() for p in apps.split(",") if p.strip()]
    else:
        cfg = audio_policy.load_audio_config()
        pkg_list = cfg.get("packages", [])
        if not pkg_list:
            click.secho("[ERRO] Nenhum pacote. Use --apps ou aplique um patch primeiro.", fg="red")
            return
    ok, msg, snap = audio_state.take_snapshot(pkg_list, label=label)
    click.secho(f"\n[{'OK' if ok else 'FALHA'}] {msg}\n",
                fg="green" if ok else "red", bold=True)
    if ok and snap:
        for pkg, state in snap["packages"].items():
            click.echo(f"  ● {pkg}: {state.get('value', '?')}")
        audio_state.log_operation("snapshot", pkg_list, "-", "success", f"label={label}")


@audio_group.command("verify")
def cmd_audio_verify():
    """Verifica se o estado atual confere com o último snapshot."""
    from android_sys.core import audio_state
    snap = audio_state.load_snapshot()
    if not snap:
        click.secho("[ERRO] Nenhum snapshot. Use 'audio snapshot' primeiro.", fg="red")
        return
    ok, msg, diffs = audio_state.verify_state(snap)
    click.secho(f"\n{'✔' if ok else '✘'} [{'OK' if ok else 'DIVERGE'}] {msg}",
                fg="green" if ok else "yellow", bold=True)
    click.echo(f"  Snapshot: {snap.get('iso')} ({snap.get('label')})")
    for d in diffs:
        icon = "✔" if d["match"] else "✘"
        color = "green" if d["match"] else "yellow"
        click.secho(
            f"  {icon} {d['package']:<40} expected={str(d['expected']):<8} actual={d['actual']}",
            fg=color,
        )
    audio_state.log_operation(
        "verify", [d["package"] for d in diffs], "-",
        "match" if ok else "diverge",
    )


@audio_group.command("rollback")
@click.option("--force", is_flag=True, help="Reverte sem pedir confirmação.")
def cmd_audio_rollback(force: bool):
    """Reverte todos os pacotes ao estado do último snapshot."""
    from android_sys.core import audio_state
    snap = audio_state.load_snapshot()
    if not snap:
        click.secho("[ERRO] Nenhum snapshot. Use 'audio snapshot' primeiro.", fg="red")
        return
    n = len(snap.get("packages", {}))
    if not force:
        click.secho(f"\n⚠ Vai reverter {n} pacote(s) para snapshot de {snap.get('iso')}.",
                    fg="yellow")
        if not click.confirm("Continuar?"):
            return
    ok, msg, logs = audio_state.rollback_to_snapshot(snap)
    for l in logs:
        click.echo(f"  {l}")
    click.secho(f"\n[{'OK' if ok else 'FALHA'}] {msg}\n",
                fg="green" if ok else "red", bold=True)
    audio_state.log_operation(
        "rollback", list(snap.get("packages", {}).keys()), "-",
        "success" if ok else "fail",
    )


@audio_group.command("history")
@click.option("--limit", "-n", default=20, show_default=True, help="Número de entradas.")
def cmd_audio_history(limit: int):
    """Mostra o histórico de operações de áudio (mais recentes primeiro)."""
    from android_sys.core import audio_state
    entries = audio_state.read_history(limit)
    if not entries:
        click.secho("(sem histórico)", fg="yellow")
        return
    click.secho(f"\n📜 Histórico (últimas {len(entries)} operações):", fg="cyan", bold=True)
    for e in reversed(entries):
        result = e.get("result", "?")
        icon = {"success": "✔", "fail": "✘", "match": "✔", "diverge": "⚠"}.get(result, "•")
        color = "green" if result in ("success", "match") else "red" if result == "fail" else "yellow"
        pkgs_list = e.get("packages", [])
        pkgs = ",".join(pkgs_list[:2])
        if len(pkgs_list) > 2:
            pkgs += f",+{len(pkgs_list) - 2}"
        click.secho(
            f"  {icon} [{e.get('ts')}] {e.get('op'):<10} {pkgs:<30} {result}",
            fg=color,
        )

@audio_group.command("apps")
@click.argument("needle")
def cmd_audio_apps(needle: str):
    """Lista pacotes instalados cujo nome contém NEEDLE."""
    devs = adb_manager.get_connected_devices()
    if not devs:
        click.secho("[ERRO] Nenhum dispositivo conectado.", fg="red"); return
    pkgs = adb_manager.list_packages_matching(devs[0], needle)
    if not pkgs:
        click.secho(f"○ Nenhum pacote contém '{needle}'.", fg="yellow"); return
    for p in pkgs:
        click.secho(f"  ● {p}", fg="green")


@audio_group.command("probe")
def cmd_audio_probe():
    """AudioProbe: mostra a pilha de foco de áudio atual (dumpsys audio)."""
    click.secho("\n🔍 AudioProbe — Pilha de Foco Atual", fg="cyan", bold=True)
    holders = audio_policy.list_active_focus_holders()
    click.echo(audio_policy.format_probe_report(holders))


@audio_group.command("monitor")
@click.option("--interval", default=1.0, show_default=True, type=float,
              help="Intervalo de polling (segundos).")
@click.option("--duration", default=60.0, show_default=True, type=float,
              help="Duração total do monitoramento (segundos).")
def cmd_audio_monitor(interval: float, duration: float):
    """AudioMonitor: observa transições GAIN/LOSS em tempo real."""
    click.secho(f"\n👁  AudioMonitor [{duration}s @ {interval}s]...", fg="cyan", bold=True)
    events = audio_monitor.monitor_focus(
        interval=interval, duration=duration,
        on_event=lambda e: click.echo(audio_monitor.format_event(e)),
    )
    click.secho(f"\n[*] {len(events)} evento(s) capturado(s).", fg="green")


@audio_group.command("restore")
@click.option("--apps", "-a", required=True, help="Pacotes a reverter (separados por vírgula).")
def cmd_audio_restore(apps: str):
    """Reverte TAKE_AUDIO_FOCUS para 'allow' nos pacotes indicados."""
    pkg_list = [p.strip() for p in apps.split(",") if p.strip()]
    click.secho(f"\n[*] Restaurando foco padrão para {pkg_list}...", fg="cyan")
    ok, msg, logs = audio_policy.restore_audio_policy(pkg_list)
    for l in logs: click.echo(f"  {l}")
    click.secho(f"\n[{'OK' if ok else 'FALHA'}] {msg}\n",
                fg="green" if ok else "red", bold=True)



