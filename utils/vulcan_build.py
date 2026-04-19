# utils/vulcan_build.py
import subprocess
import os
from pathlib import Path

def ensure_native_engine(dll_name):
    """
    Verifica se a DLL existe. Se não, aciona o batch de build.
    """
    # Localiza a raiz do projeto (assumindo que utils está 1 nível abaixo)
    project_root = Path(__file__).parents[1]
    dll_path = project_root / "engine" / "native" / dll_name
    bat_path = project_root / "scripts" / "build_native.bat"

    if not dll_path.exists():
        print(f"[VULCAN:AUTO-BUILD] Motor {dll_name} ausente. Acionando Foundry...")
        try:
            # Muda o diretório de trabalho para a raiz para o batch funcionar
            subprocess.run([str(bat_path)], cwd=str(project_root), check=True)
            if dll_path.exists():
                print(f"[VULCAN:AUTO-BUILD] {dll_name} reconstruído com sucesso.")
                return True
        except Exception as e:
            print(f"[VULCAN:ERROR] Falha ao compilar motor nativo: {e}")
            return False
    return True