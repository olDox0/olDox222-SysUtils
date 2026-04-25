# bloatbreaker/core/scanner.py
import subprocess
import psutil
from bloatbreaker.core.heuristics import BLOAT_APP_PATTERNS, BLOAT_SERVICES

def remove_bloatware_aggressive(package_name):
    """
    Remove o pacote do usuário atual E a matriz de provisionamento.
    Nota: Requer terminal como ADMINISTRADOR.
    """
    # 1. Remove do usuário
    cmd_user = f"Get-AppxPackage -AllUsers *{package_name}* | Remove-AppxPackage -ErrorAction SilentlyContinue"
    # 2. Remove a matriz (Provisioned) para que o Windows não reinstale no próximo boot
    cmd_prov = f"Get-AppxProvisionedPackage -Online | Where-Object {{ $_.DisplayName -like '*{package_name}*' }} | Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue"
    
    try:
        subprocess.run(["powershell", "-Command", cmd_user], capture_output=True)
        subprocess.run(["powershell", "-Command", cmd_prov], capture_output=True)
        return True
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: remove_bloatware_aggressive\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return False

def remove_bloatware(package_name):
    """Remove um pacote Appx permanentemente para o usuário atual."""
    # O comando PowerShell procura o pacote pelo nome e o remove
    cmd = f"Get-AppxPackage *{package_name}* | Remove-AppxPackage"
    try:
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: remove_bloatware\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return False

def disable_service(service_name):
    """Desativa um serviço e o impede de iniciar com o Windows."""
    try:
        # Requer privilégios de administrador
        cmd = f"Stop-Service -Name {service_name}; Set-Service -Name {service_name} -StartupType Disabled"
        subprocess.run(["powershell", "-Command", cmd], capture_output=True)
        return True
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: disable_service\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return False

def get_installed_bloatware():
    """Lista aplicativos UWP (Appx) que batem com a lista de bloatware."""
    cmd = "Get-AppxPackage -AllUsers | Select-Object Name"
    result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
    
    found_apps = []
    if result.returncode == 0:
        installed_names = result.stdout.splitlines()
        for app in installed_names:
            app = app.strip()
            if any(pattern in app for pattern in BLOAT_APP_PATTERNS):
                found_apps.append(app)
    return list(set(found_apps))

def get_active_bloat_services():
    """Verifica quais serviços de telemetria/bloat estão rodando."""
    found_services = []
    for service in psutil.win_service_iter():
        try:
            s_info = service.as_dict()
            if s_info['name'] in BLOAT_SERVICES and s_info['status'] == 'running':
                found_services.append(s_info['name'])
        except Exception as e:
            import sys as _dox_sys, os as _dox_os
            exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: get_active_bloat_services\033[0m")
            print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
            continue
    return found_services

def get_pagefile_usage():
    """Analisa o impacto no Pagefile."""
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "ram_used_percent": vm.percent,
        "pagefile_used_mb": swap.used / (1024 * 1024),
        "pagefile_total_mb": swap.total / (1024 * 1024)
    }