# ramdiag/core/pagefile.py
import psutil
import subprocess
from ramdiag.platform.windows import disk_info

def calculate_smart_pagefile():
    """
    Calcula os valores ideais de Pagefile baseados na RAM física e tipo de disco.
    """
    ram_total_mb = psutil.virtual_memory().total / (1024 * 1024)
    drive_type = disk_info.get_system_drive_type()
    
    # Regras Vulcan para DDR3 / Sistemas com pouca RAM:
    if drive_type == "SSD":
        # No SSD, o acesso é rápido. Mantemos um mínimo seguro e deixamos expandir.
        min_mb = 1024 
        max_mb = ram_total_mb * 1.5
    else:
        # No HDD, a fragmentação mata a performance. Forçamos TAMANHO FIXO (Min == Max).
        if ram_total_mb < 4096:
            min_mb = max_mb = 4096 
        else:
            min_mb = max_mb = ram_total_mb * 1.5

    return {
        "drive_type": drive_type,
        "min_size": int(min_mb),
        "max_size": int(max_mb),
        "is_fixed": min_mb == max_mb
    }

def apply_pagefile_settings(min_mb, max_mb):
    """
    Aplica as configurações de Pagefile usando PowerShell (CIM).
    Mais estável que WMIC em sistemas modernos (Windows 10/11).
    """
    # Script PowerShell para desativar o gerenciamento automático e definir valores
    ps_script = f"""
    $sys = Get-CimInstance Win32_ComputerSystem
    if ($sys.AutomaticManagedPagefile) {{
        Set-CimInstance -InputObject $sys -Property @{{AutomaticManagedPagefile=$False}} -ErrorAction SilentlyContinue
    }}
    
    $pagefile = Get-CimInstance Win32_PageFileSetting | Where-Object {{ $_.Name -like "C:*" }}
    if ($pagefile) {{
        Set-CimInstance -InputObject $pagefile -Property @{{InitialSize={min_mb}; MaximumSize={max_mb}}}
    }} else {{
        New-CimInstance -ClassName Win32_PageFileSetting -Property @{{Name="C:\\pagefile.sys"; InitialSize={min_mb}; MaximumSize={max_mb}}}
    }}
    """
    
    try:
        # Executa o script via PowerShell
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except Exception as e:
        return False