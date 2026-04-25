# ramdiag/platform/windows/disk_info.py
import subprocess

def get_system_drive_type():
    """
    Retorna 'SSD' ou 'HDD' para a unidade do sistema.
    """
    try:
        # Comando PowerShell para identificar o tipo de mídia
        cmd = "Get-PhysicalDisk | Select-Object -Property DeviceID, MediaType"
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
        
        # Lógica simplificada: Se encontrar 'SSD' na string de retorno
        output = result.stdout.upper()
        if "SSD" in output:
            return "SSD"
        return "HDD"
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: get_system_drive_type\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return "UNKNOWN"