# ramdiag/core/optimizer.py
import os
import subprocess
from ramdiag.platform.windows import mem_tweaks

def apply_ddr3_optimization_profile():
    """
    Aplica um perfil de baixa latência ideal para DDR3:
    1. Desativa paginação de kernel (força drivers na RAM).
    2. Otimiza o Cache do Sistema.
    3. Ajusta o comportamento do SysMain (Superfetch).
    """
    results = []
    
    # Tweak 1: DisablePagingExecutive
    # Impede que o Windows mova drivers e código do kernel para o disco.
    if mem_tweaks.set_disable_paging_executive(1):
        results.append("[OK] Kernel forçado na RAM (DisablePagingExecutive)")

    # Tweak 2: LargeSystemCache
    # Melhora a performance de I/O em sistemas com RAM limitada.
    if mem_tweaks.set_large_system_cache(1):
        results.append("[OK] Cache de Sistema expandido (LargeSystemCache)")

    # Tweak 3: Ajuste de IoPageLockLimit
    # Aumenta a velocidade de transferência de I/O.
    if mem_tweaks.optimize_io_lock_limit():
        results.append("[OK] Limite de Lock de I/O otimizado")

    return results

def manage_memory_compression(enable=True):
    """
    O Memory Compression pode sobrecarregar CPUs antigas comuns em sistemas DDR3.
    Em alguns casos, desativar melhora a latência.
    """
    cmd = "Enable-mmAgent -MemoryCompression" if enable else "Disable-mmAgent -MemoryCompression"
    try:
        subprocess.run(["powershell", "-Command", cmd], capture_output=True, check=True)
        return True
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: manage_memory_compression\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return False