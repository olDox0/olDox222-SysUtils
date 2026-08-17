# utils/vulcan_build.py
import subprocess
import os
from pathlib import Path

def ensure_native_engine(dll_name):
    """
    Verifica se a DLL/EXE existe em bin/.
    Se não, aciona o Metalcraft para forjá-la.
    """
    project_root = Path(__file__).parents[1]
    
    # Metalcraft coloca os binários em bin/
    bin_path = project_root / "bin" / dll_name
    
    # Fallback: também verifica engine/native/ para compatibilidade
    legacy_path = project_root / "engine" / "native" / dll_name
    
    if bin_path.exists() or legacy_path.exists():
        return True
    
    print(f"[VULCAN:AUTO-BUILD] Motor {dll_name} ausente em bin/. Acionando Metalcraft...")
    
    # Tenta invocar o Metalcraft via Doxoade
    try:
        # Se o Doxoade estiver disponível, usa o motor Metalcraft
        result = subprocess.run(
            ["doxoade", "metal", "build", "--target", dll_name.replace('.dll', '').replace('.exe', '')],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print(f"[VULCAN:AUTO-BUILD] {dll_name} forjado com sucesso via Metalcraft.")
            return True
        else:
            print(f"[VULCAN:ERROR] Metalcraft falhou: {result.stderr[:200]}")
    except Exception as e:
        print(f"[VULCAN:ERROR] Falha ao invocar Metalcraft: {e}")
    
    # Fallback: tenta compilar manualmente usando src/native/
    src_name = dll_name.replace('.dll', '.c').replace('.exe', '.c')
    src_path = project_root / "src" / "native" / src_name
    
    if src_path.exists():
        print(f"[VULCAN:FALLBACK] Compilando {src_name} diretamente...")
        try:
            bin_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = ["gcc", "-O3", "-s"]
            if dll_name.endswith('.dll'):
                cmd += ["-shared"]
            cmd += ["-o", str(bin_path), str(src_path)]
            if "cleaner" in dll_name or "dox" in dll_name:
                cmd.append("-lkernel32")
            elif "ram" in dll_name:
                cmd.append("-lpsapi")
            
            subprocess.run(cmd, check=True, capture_output=True)
            if bin_path.exists():
                print(f"[VULCAN:FALLBACK] {dll_name} compilado com sucesso.")
                return True
        except Exception as e:
            print(f"[VULCAN:ERROR] Falha na compilação manual: {e}")
    
    return False