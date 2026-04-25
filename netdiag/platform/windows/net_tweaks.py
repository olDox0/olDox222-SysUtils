# netdiag/platform/windows/net_tweaks.py
import winreg

def set_reg_value(root, path, name, value, val_type=winreg.REG_DWORD):
    try:
        key = winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, val_type, value)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: set_reg_value\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return False

def apply_tcp_latency_tweaks():
    """Aplica o Game-Mode Network (TcpAckFrequency) para resposta instantânea."""
    # 1. Encontra a interface de rede ativa (percorre as interfaces do registro)
    path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
    try:
        main_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        for i in range(winreg.QueryInfoKey(main_key)[0]):
            sub_key_name = winreg.EnumKey(main_key, i)
            sub_path = f"{path}\\{sub_key_name}"
            # TcpAckFrequency=1 força o Windows a enviar pacotes de resposta imediatamente
            set_reg_value(winreg.HKEY_LOCAL_MACHINE, sub_path, "TcpAckFrequency", 1)
            # TCPNoDelay desativa o algoritmo de Nagle (que segura pacotes pequenos na RAM)
            set_reg_value(winreg.HKEY_LOCAL_MACHINE, sub_path, "TCPNoDelay", 1)
        winreg.CloseKey(main_key)
        return True
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: apply_tcp_latency_tweaks\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return False

def optimize_global_net_params():
    """Ajusta parâmetros globais do TCP/IP."""
    path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
    # Aumenta o limite de conexões efêmeras
    set_reg_value(winreg.HKEY_LOCAL_MACHINE, path, "MaxUserPort", 65534)
    # Diminui o tempo que o Windows segura uma conexão fechada na RAM (TimeWait)
    set_reg_value(winreg.HKEY_LOCAL_MACHINE, path, "TcpTimedWaitDelay", 30)