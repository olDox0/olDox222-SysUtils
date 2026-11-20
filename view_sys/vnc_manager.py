import subprocess
import socket
import click

def get_lan_ip():
    """Obtém o IP local da LAN (pode ser substituído por uma chamada ao seu módulo netdiag)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def set_view_only_mode():
    """
    Configura o TigerVNC no Windows para modo 'View-Only' nativo.
    Modifica o registro para rejeitar input remoto, evitando conflito com leap_sys.
    """
    # Tenta primeiro HKLM (serviço do sistema), fallback para HKCU (modo usuário)
    reg_paths = [
        r"HKLM\SOFTWARE\TigerVNC\WinVNC4",
        r"HKCU\SOFTWARE\TigerVNC\WinVNC4"
    ]
    
    for path in reg_paths:
        try:
            # Desativa eventos de teclado e mouse do cliente VNC
            subprocess.run(
                ["reg", "add", path, "/v", "AcceptKeyEvents", "/t", "REG_DWORD", "/d", "0", "/f"],
                capture_output=True, check=True
            )
            subprocess.run(
                ["reg", "add", path, "/v", "AcceptPointerEvents", "/t", "REG_DWORD", "/d", "0", "/f"],
                capture_output=True, check=True
            )
            return True, path
        except subprocess.CalledProcessError:
            continue
            
    return False, "Falha ao alterar o registro. Execute o terminal como Administrador."

def start_vnc_service():
    """Inicia o serviço do TigerVNC no Windows (tvnserver)."""
    try:
        result = subprocess.run(["net", "start", "tvnserver"], capture_output=True, text=True)
        # Aceita respostas de sucesso em PT-BR ou EN-US
        if result.returncode == 0 or "já está sendo iniciado" in result.stdout or "started successfully" in result.stdout.lower():
            return True, "Serviço TigerVNC (tvnserver) iniciado com sucesso."
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "Serviço 'tvnserver' não encontrado. Instale o TigerVNC Server para Windows."

def stop_vnc_service():
    """Para o serviço do TigerVNC no Windows."""
    try:
        result = subprocess.run(["net", "stop", "tvnserver"], capture_output=True, text=True)
        if result.returncode == 0 or "foi encerrado" in result.stdout or "stopped successfully" in result.stdout.lower():
            return True, "Serviço TigerVNC encerrado com sucesso."
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "Erro ao tentar parar o serviço."
