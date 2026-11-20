import click
from .vnc_manager import get_lan_ip, set_view_only_mode, start_vnc_service, stop_vnc_service

@click.group()
def view():
    """Gerenciamento de visualização de tela em rede local (View-Only)."""
    pass

@view.command()
def start():
    """Inicia o servidor TigerVNC em modo View-Only (seguro para leap_sys/Barrier)."""
    click.echo("[SysUtils :: view_sys] Configurando modo View-Only no registro do Windows...")
    success, msg = set_view_only_mode()
    
    if not success:
        click.echo(f"[ERRO] {msg}", err=True)
        click.echo("[DICA] Execute 'sysutils view start' em um terminal com privilégios de Administrador.")
        return

    click.echo(f"[OK] Registro atualizado em: {msg}")
    
    click.echo("[SysUtils :: view_sys] Iniciando serviço TigerVNC...")
    success, msg = start_vnc_service()
    
    if success:
        ip = get_lan_ip()
        click.echo("\n" + "="*50)
        click.echo(f"✅ TigerVNC Ativo e Seguro (View-Only)")
        click.echo(f"🌐 IP Local: {ip}")
        click.echo(f"🔌 Porta Padrão: 5900")
        click.echo(f"📱 No dispositivo secundário, abra o VNC Viewer e conecte em: {ip}:5900")
        click.echo("🛡️  Input remoto bloqueado. O leap_sys (Barrier) mantém o controle total.")
        click.echo("="*50 + "\n")
    else:
        click.echo(f"[ERRO] {msg}", err=True)

@view.command()
def stop():
    """Encerra o servidor TigerVNC."""
    click.echo("[SysUtils :: view_sys] Encerrando serviço TigerVNC...")
    success, msg = stop_vnc_service()
    
    if success:
        click.echo(f"[OK] {msg}")
    else:
        click.echo(f"[AVISO] {msg}")

@view.command()
def status():
    """Verifica o status atual do serviço e configurações de View-Only."""
    import subprocess
    try:
        result = subprocess.run(["sc", "query", "tvnserver"], capture_output=True, text=True)
        if "RUNNING" in result.stdout:
            click.echo("✅ Serviço TigerVNC: EM EXECUÇÃO")
        else:
            click.echo("⏹️  Serviço TigerVNC: PARADO")
    except Exception:
        click.echo("❌ Não foi possível verificar o status do serviço.")
