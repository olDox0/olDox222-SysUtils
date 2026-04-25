# netdiag/core/net_optimizer.py
import subprocess

def disable_delivery_optimization():
    """Desativa o compartilhamento de atualizações via P2P (DoSvc)."""
    # Para o serviço e desativa
    subprocess.run(["powershell", "-Command", "Stop-Service -Name DoSvc -Force; Set-Service -Name DoSvc -StartupType Disabled"], capture_output=True)

def flush_dns_and_reset_stack():
    """Limpa o cache de rede e reinicia o stack TCP/IP."""
    subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)
    subprocess.run("netsh int ip reset", shell=True, capture_output=True)
    subprocess.run("netsh winsock reset", shell=True, capture_output=True)

def set_fast_dns():
    """Configura DNS do Cloudflare (1.1.1.1) para resolução mais rápida."""
    # Aplica na interface principal via PowerShell
    ps_cmd = "Set-DnsClientServerAddress -InterfaceAlias (Get-NetAdapter | Where-Object {$_.Status -eq 'Up'}).InterfaceAlias -ServerAddresses ('1.1.1.1','1.0.0.1')"
    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)