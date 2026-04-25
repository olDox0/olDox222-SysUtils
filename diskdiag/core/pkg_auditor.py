# diskdiag/core/pkg_auditor.py
import os
import sys
from pathlib import Path
from diskdiag.analysis.disk_analysis import _format_size

def audit_global_packages():
    """Analisa o tamanho de cada biblioteca instalada no site-packages global."""
    # Localiza o site-packages global
    global_sp = Path(sys.base_prefix) / "Lib" / "site-packages"
    if not global_sp.exists():
        return []

    pkg_stats = []
    
    # Itera sobre as pastas no site-packages
    # Ignora pastas de metadados (.dist-info, .egg-info) para focar no código/binários
    for entry in global_sp.iterdir():
        if entry.is_dir() and not entry.name.endswith(('.dist-info', '.egg-info')):
            try:
                size = sum(f.stat().st_size for f in entry.rglob('*') if f.is_file())
                if size > 1024 * 1024: # Foca em quem tem mais de 1MB
                    pkg_stats.append((entry.name, size))
            except Exception as e:
                import sys as _dox_sys, os as _dox_os
                exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                line_n = exc_tb.tb_lineno
                print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: audit_global_packages\033[0m")
                print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
                continue
            
    return sorted(pkg_stats, key=lambda x: x[1], reverse=True)