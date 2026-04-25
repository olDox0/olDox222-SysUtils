# diskdiag/core/system_bloat.py
import os
from pathlib import Path

def audit_appdata_bloat(limit=15):
    """Busca as pastas mais pesadas no AppData do usuário."""
    local = os.environ.get('LOCALAPPDATA')
    roaming = os.environ.get('APPDATA')
    
    heavy_folders = []
    for base in [local, roaming]:
        if not base: continue
        p = Path(base)
        for entry in p.iterdir():
            if entry.is_dir():
                try:
                    # Cálculo de tamanho (limitado para performance)
                    # Soma apenas arquivos na raiz e no primeiro nível de subpastas
                    size = sum(f.stat().st_size for f in entry.iterdir() if f.is_file())
                    # Adiciona subpastas comuns de lixo
                    for sub in ["Cache", "Local Storage", "Code Cache"]:
                        sub_p = entry / sub
                        if sub_p.exists():
                            size += sum(f.stat().st_size for f in sub_p.rglob('*') if f.is_file())
                    
                    if size > 10 * 1024 * 1024: # Acima de 10MB
                        heavy_folders.append((entry.name, size))
                except Exception as e:
                    import sys as _dox_sys, os as _dox_os
                    exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                    f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    line_n = exc_tb.tb_lineno
                    print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: audit_appdata_bloat\033[0m")
                    print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
                    continue
                
    return sorted(heavy_folders, key=lambda x: x[1], reverse=True)[:limit]