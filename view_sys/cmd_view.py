import click
import os
import subprocess
import socket
import webbrowser
import time
from pathlib import Path

VNC_PATHS = [
    Path(r"C:\Program Files\TigerVNC Server\winvnc4.exe"),
    Path(r"C:\Program Files\TigerVNC\winvnc4.exe"),
]
REG_HKLM = r"HKLM\SOFTWARE\TigerVNC\WinVNC4"
REG_HKCU = r"HKCU\SOFTWARE\TigerVNC\WinVNC4"
PROC = "winvnc4.exe"
PORT = "5900"

def find_vnc_exe():
    return next((p for p in VNC_PATHS if p.exists()), None)

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "127.0.0.1"

def is_admin():
    try:
        return os.getuid() == 0
    except AttributeError:
        return subprocess.run('net session', shell=True, capture_output=True).returncode == 0

def apply_locks(reg):
    ok = 0
    for k in ["AcceptKeyEvents", "AcceptPointerEvents", "QueryConnect"]:
        r = subprocess.run(f'reg add "{reg}" /v "{k}" /t REG_DWORD /d 0 /f',
                           shell=True, capture_output=True)
        ok += (r.returncode == 0)
    return ok == 3

def process_running():
    r = subprocess.run(f'tasklist /FI "IMAGENAME eq {PROC}"', shell=True, capture_output=True, text=True)
    return PROC.lower() in r.stdout.lower()

def port_listening():
    r = subprocess.run('netstat -an', shell=True, capture_output=True, text=True)
    return f':{PORT}' in r.stdout and 'LISTENING' in r.stdout

def reg_has_password(reg):
    r = subprocess.run(f'reg query "{reg}" /v Password', shell=True, capture_output=True, text=True)
    return r.returncode == 0 and "Password" in r.stdout

@click.group()
def cli():
    """Gerenciamento de Visualização de Tela Segura (View-Only, modo usuário)."""
    pass

@cli.command()
def setup():
    """Aplica travas View-Only e prepara o modo usuário (sem serviço)."""
    click.echo("🔍 [SysUtils :: view] Modo usuário (processo) — sem serviço do Windows.")
    if os.name != 'nt':
        click.secho("❌ Otimizado para Windows.", fg="red"); return

    vnc_exe = find_vnc_exe()
    if not vnc_exe:
        click.echo("📥 TigerVNC não encontrado. Abrindo navegador...")
        webbrowser.open("https://sourceforge.net/projects/tigervnc/files/stable/1.16.2/tigervnc64-winvnc-1.16.2.exe/download")
        click.echo("   Instale (Next>Next>Finish), ignore o aviso 'unmaintained', e rode de novo.")
        return

    click.secho(f"✅ TigerVNC em: {vnc_exe}", fg="green")

    click.echo("🛡️  Aplicando travas View-Only (HKLM + HKCU)...")
    if is_admin():
        click.echo(f"   {'✅' if apply_locks(REG_HKLM) else '⚠️ '} HKLM")
    click.echo(f"   {'✅' if apply_locks(REG_HKCU) else '⚠️ '} HKCU")

    click.echo("\n" + "="*65)
    click.secho(" 🚨 DEFINIR SENHA (GUI) 🚨 ", fg="red", bold=True)
    click.echo(" VNC não aceita conexão sem senha. Abra o TigerVNC no menu Iniciar")
    click.echo(" (item 'VNC Server', NÃO 'Configure VNC Service') e em:")
    click.echo("   Options > Authentication > Configure > defina a Primary Password.")
    click.echo(" (VNC usa só os 8 primeiros caracteres da senha.)")
    click.echo(" Depois rode: sysutils view start")
    click.echo("="*65)

@cli.command()
def start():
    """Inicia o winvnc4.exe em modo SERVER (porta 5900 LISTENING)."""
    vnc_exe = find_vnc_exe()
    if not vnc_exe:
        click.secho("❌ winvnc4.exe não encontrado. Rode: sysutils view setup", fg="red"); return
    
    if process_running() and port_listening():
        click.echo("ℹ️  TigerVNC já está ativo e escutando.")
        ip = get_lan_ip()
        click.echo(f"🌐 Conexão: {ip}:{PORT}")
        return

    # Mata qualquer instância anterior (GUI de configuração)
    if process_running():
        click.echo("⚠️  Encerrando instância anterior (GUI de configuração)...")
        subprocess.run(f'taskkill /F /IM {PROC}', shell=True, capture_output=True)
        time.sleep(1)

    click.echo("⚙️  Iniciando TigerVNC em modo SERVER...")
    
    # Método correto: usar o atalho do Menu Iniciar "VNC Server" (modo usuário)
    # Ou iniciar via shell com o parâmetro correto
    shortcuts = [
        Path(os.environ.get('APPDATA', '')) / r"Microsoft\Windows\Start Menu\Programs\TigerVNC 64-bit\VNC Server.lnk",
        Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\TigerVNC 64-bit\VNC Server.lnk"),
        Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\TigerVNC\VNC Server.lnk"),
    ]
    
    shortcut = next((s for s in shortcuts if s.exists()), None)
    
    if shortcut:
        # Usa o atalho oficial do Menu Iniciar
        subprocess.run(f'start "" "{shortcut}"', shell=True)
    else:
        # Fallback: inicia o binário diretamente (pode abrir GUI)
        subprocess.run(f'start "" "{vnc_exe}"', shell=True)
        click.echo("⚠️  Usando fallback direto. Se a GUI abrir, feche-a e use o atalho do Menu Iniciar.")

    # Aguarda o servidor iniciar
    for i in range(10):
        time.sleep(1)
        if process_running() and port_listening():
            break
    
    if process_running() and port_listening():
        ip = get_lan_ip()
        click.echo("\n" + "="*65)
        click.secho(" 🚀 TIGERVNC ATIVO (View-Only) ", fg="green", bold=True)
        click.echo(f" 🌐 Conexão: {ip}:{PORT}")
        click.echo(f" 🔌 Porta :{PORT}: 🟢 LISTENING")
        click.echo(" 🛡️  Input remoto: BLOQUEADO (leap_sys/Barrier mantém soberania)")
        click.echo("="*65)
    elif process_running():
        click.secho("⚠️  Processo rodando, mas porta 5900 não está LISTENING.", fg="yellow")
        click.echo("   → A GUI de configuração abriu em vez do servidor.")
        click.echo("   → Feche a GUI e use o atalho 'VNC Server' do Menu Iniciar.")
    else:
        click.secho("❌ O processo não iniciou. Verifique antivírus/UAC.", fg="red")

@cli.command()
def stop():
    """Encerra o winvnc4.exe."""
    if not process_running():
        click.echo("ℹ️  winvnc4.exe não está rodando."); return
    subprocess.run(f'taskkill /F /IM {PROC}', shell=True, capture_output=True)
    click.secho("✅ winvnc4.exe encerrado.", fg="green")

@cli.command()
def status():
    """Diagnóstico: processo + porta + travas + senha."""
    click.echo("📊 [SysUtils :: view :: status]")
    click.echo(f"   Processo {PROC:<22}: {'🟢 ATIVO' if process_running() else '🔴 PARADO'}")
    click.echo(f"   Porta {PORT:<22}: {'🟢 LISTENING' if port_listening() else '🔴 FECHADA'}")
    for reg in [REG_HKLM, REG_HKCU]:
        if subprocess.run(f'reg query "{reg}"', shell=True, capture_output=True).returncode == 0:
            pwd = "🟢 DEFINIDA" if reg_has_password(reg) else "🔴 NÃO DEFINIDA"
            click.echo(f"   [{'HKLM' if 'HKLM' in reg else 'HKCU'}] Password: {pwd}")
            for k in ["AcceptKeyEvents", "AcceptPointerEvents", "QueryConnect"]:
                r = subprocess.run(f'reg query "{reg}" /v {k}', shell=True, capture_output=True, text=True)
                click.echo(f"   [{'HKLM' if 'HKLM' in reg else 'HKCU'}] {k:<20}: {'🛡️  BLOQUEADO (0)' if '0x0' in r.stdout else '⚠️  PERMITIDO' if r.returncode==0 else '❔ não definido'}")

@cli.command()
def config():
    """Abre a GUI do TigerVNC (modo usuário) para definir senha/opções."""
    vnc_exe = find_vnc_exe()
    if not vnc_exe:
        click.secho("❌ winvnc4.exe não encontrado.", fg="red"); return
    subprocess.run(f'start "" "{vnc_exe}"', shell=True)
    click.echo("🪟 GUI do TigerVNC aberta. Defina a senha em Options > Authentication.")
