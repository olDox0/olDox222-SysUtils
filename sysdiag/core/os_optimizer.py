# sysdiag/core/os_optimizer.py
import subprocess

def disable_telemetry_services():
    """Para e desativa serviços de coleta de dados."""
    services = ["DiagTrack", "dmwappushservice", "WerSvc"] # Telemetria e Erros
    for svc in services:
        subprocess.run(["powershell", "-Command", f"Stop-Service -Name {svc} -Force; Set-Service -Name {svc} -StartupType Disabled"], capture_output=True)

def optimize_visual_effects():
    """Ajusta o Windows para 'Melhor Desempenho' (Desativa sombras e animações inúteis)."""
    # Este comando desativa animações de janela e sombras, economizando GPU/RAM
    ps_cmd = "Set-ItemProperty -Path 'HKCU:\\Control Panel\\Desktop' -Name 'UserPreferencesMask' -Value ([byte[]](0x90,0x12,0x03,0x80,0x10,0x00,0x00,0x00))"
    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)

def set_high_performance_power():
    """Ativa o plano de Alto Desempenho via GUID."""
    # GUID do plano 'High Performance'
    cmd = "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
    subprocess.run(cmd, shell=True, capture_output=True)