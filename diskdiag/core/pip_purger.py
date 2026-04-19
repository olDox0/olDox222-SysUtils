# diskdiag/core/pip_purger.py
import subprocess
import sys
from utils.error_info import handle_error

# Pacotes que NÃO devem ser removidos (essenciais para o sistema e o SysUtils)
PROTECTED_PACKAGES = {
    "pip", "setuptools", "wheel", "sysutils", 
    "psutil", "click", "colorama", "doxoade",
    "ocsys",
}

def purge_global_packages(dry_run=True):
    """Remove pacotes não protegidos do ambiente global."""
    try:
        # 1. Obtém lista de instalados via pip freeze
        base_exe = sys.base_prefix + "\\python.exe"
        output = subprocess.check_output([base_exe, "-m", "pip", "list", "--format=freeze"], text=True)
        
        to_remove = []
        for line in output.splitlines():
            name = line.split("==")[0].lower()
            if name not in PROTECTED_PACKAGES:
                to_remove.append(name)
        
        if not to_remove:
            return 0, []

        if not dry_run:
            # 2. Executa a desinstalação em lote
            # -y confirma automaticamente
            cmd = [base_exe, "-m", "pip", "uninstall", "-y"] + to_remove
            subprocess.run(cmd, capture_output=True)
            
        return len(to_remove), to_remove

    except Exception as e:
        handle_error(e, context="pip_purger.purge")
        return 0, []