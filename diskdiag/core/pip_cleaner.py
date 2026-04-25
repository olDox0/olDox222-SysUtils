# diskdiag/core/pip_cleaner.py
import os
import sys
from pathlib import Path
from utils.error_info import handle_error

def get_pip_targets():
    """
    Varredura profunda por 'Cemitérios de Python' no Windows.
    """
    targets = set()
    
    # 1. AppData Roaming (Onde o 'pip install --user' esconde libs de todas as versões)
    roaming = os.environ.get('APPDATA')
    if roaming:
        python_roaming = Path(roaming) / "Python"
        if python_roaming.exists():
            # Acha subpastas como Python310, Python311, etc.
            for version_dir in python_roaming.glob("Python*"):
                sp = version_dir / "site-packages"
                if sp.exists(): targets.add(str(sp))

    # 2. Local AppData (Onde ficam as instalações do Python e o Cache do Pip)
    local = os.environ.get('LOCALAPPDATA')
    if local:
        # Cache do Pip
        pip_cache = Path(local) / "pip" / "cache"
        if pip_cache.exists(): targets.add(str(pip_cache))
        
        # Instalações de programas (Python pode estar aqui)
        programs_python = Path(local) / "Programs" / "Python"
        if programs_python.exists():
            for py_install in programs_python.glob("Python*"):
                sp = py_install / "Lib" / "site-packages"
                if sp.exists(): targets.add(str(sp))

    # 3. Caminho da instalação atual (Global)
    global_sp = Path(sys.base_prefix) / "Lib" / "site-packages"
    if global_sp.exists():
        targets.add(str(global_sp))

    return list(targets)

def scan_pip_junk():
    targets = get_pip_targets()
    junk_list = []
    total_size = 0

    # Se estiver em venv, pegamos o path para ignorar
    current_venv = sys.prefix

    for base_path in targets:
        # Pula se for o venv que estamos usando agora
        if current_venv in base_path:
            continue

        p = Path(base_path)
        if not p.exists(): continue

        try:
            # Para cache do pip, usamos busca profunda
            is_cache = "pip" in str(p).lower()
            entries = p.rglob('*') if is_cache else p.iterdir()

            for entry in entries:
                name = entry.name.lower()
                is_junk = False
                
                # Pastas órfãs (~), cache de bytecode ou instaladores (.whl)
                if name.startswith('~') or name == "__pycache__":
                    is_junk = True
                elif entry.suffix == ".whl" or "pip-req-build-" in name:
                    is_junk = True

                if is_junk and entry.exists():
                    try:
                        if entry.is_file():
                            size = entry.stat().st_size
                        else:
                            # Soma rápida de diretório
                            size = sum(f.stat().st_size for f in entry.rglob('*') if f.is_file())
                        
                        junk_list.append((str(entry), size))
                        total_size += size
                    except Exception as e:
                        import sys as _dox_sys, os as _dox_os
                        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
                        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        line_n = exc_tb.tb_lineno
                        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: scan_pip_junk\033[0m")
                        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        except Exception as e:
            handle_error(e, context=f"pip_scan:{p.name}", silent=True)

    return junk_list, total_size