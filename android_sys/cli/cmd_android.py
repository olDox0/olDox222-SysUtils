# android_sys/cli/cmd_android.py
from __future__ import annotations
import click
from pathlib import Path
from android_sys.core import installer, adb_manager, scrcpy_runner

@click.group(name="android")
def cli():
    """AndroidSys — Controle, Espelhamento e Ferramentas Android Sem Fio."""
    pass

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

@cli.command("auto")
def cmd_auto():
    """Localiza a porta do celular na rede Wi-Fi e conecta automaticamente."""
    installer.ensure_binaries()
    ok, msg = adb_manager.scan_and_auto_connect()
    if ok:
        click.secho(f"✔ [AUTO-CONNECT] {msg}", fg="green", bold=True)
        click.echo("👉 Para abrir a tela no PC: sysutils android mirror")
    else:
        click.secho(f"✘ [FALHA] {msg}", fg="yellow")
        click.echo("Dica: Use 'sysutils android connect <porta>' se souber a porta atual.")

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
        click.echo("👉 1. Feche a caixinha de pareamento no celular.")
        click.echo("👉 2. Olhe o 'Endereço IP e porta' principal na tela de Depuração sem fio.")
        ip = target.split(":")[0]
        click.secho(f"👉 3. Execute: sysutils android connect {ip}:<PORTA_PRINCIPAL>\n", fg="yellow", bold=True)
    else:
        click.secho(f"\n✘ [FALHA] {msg}", fg="red")

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
