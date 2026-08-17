# install.py
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def log_step(step, msg):
    print(f"\n\033[1;36m[{step}] {msg}\033[0m")

def log_ok(msg):
    print(f"  \033[1;32m✔ {msg}\033[0m")

def log_warn(msg):
    print(f"  \033[1;33m⚠ {msg}\033[0m")

def log_err(msg):
    print(f"  \033[1;31m✘ {msg}\033[0m")

def ensure_directories():
    """Garante que todas as pastas vitais do sistema existam."""
    dirs = [
        ROOT / "bin",
        ROOT / "engine" / "native",
        ROOT / "data" / "db",
        ROOT / "data" / "vulcan_idx",
        ROOT / ".doxoade" / "logs",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    # Garante __init__.py em todos os pacotes Python
    packages = ['netdiag', 'sysdiag', 'diskdiag', 'ramdiag', 'doxbackup', 'bloatbreaker', 'cli', 'utils']
    for pkg in packages:
        init_f = ROOT / pkg / "__init__.py"
        if not init_f.exists():
            init_f.touch()

def compile_native_binaries():
    """Tenta compilar as DLLs nativas se o GCC estiver disponível."""
    gcc_path = shutil.which("gcc")
    if not gcc_path:
        log_warn("Compilador GCC não localizado no PATH. As DLLs existentes serão usadas.")
        return

    print("  Compilando motores nativos em C...")

    compilations = [
        # Vulcan Dox V3 (DLL do Backup)
        {
            "src": ROOT / "engine" / "native" / "dox_packer.c",
            "out": ROOT / "engine" / "native" / "vulcan_dox_v3.dll",
            "flags": ["-shared", "-lkernel32"]
        },
        {
            "src": ROOT / "engine" / "native" / "dox_packer.c",
            "out": ROOT / "bin" / "vulcan_dox.dll",
            "flags": ["-shared", "-lkernel32"]
        },
        # Vulcan Cleaner (Batch Shredder)
        {
            "src": ROOT / "src" / "native" / "vulcan_cleaner.c",
            "out": ROOT / "bin" / "vulcan_cleaner.dll",
            "flags": ["-shared", "-lkernel32"]
        },
        # Vulcan RAM (Trim API)
        {
            "src": ROOT / "src" / "native" / "vulcan_ram.c",
            "out": ROOT / "bin" / "vulcan_ram.dll",
            "flags": ["-shared", "-lpsapi"]
        }
    ]

    for item in compilations:
        if not item["src"].exists():
            continue
        cmd = ["gcc", "-O3", "-s", str(item["src"]), "-o", str(item["out"])] + item["flags"]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            log_ok(f"Forjado: {item['out'].name}")
        except subprocess.CalledProcessError as e:
            log_warn(f"Falha ao compilar {item['out'].name}: {e.stderr.decode('utf-8', errors='ignore')[:100]}")

def main():
    print("=" * 60)
    print("⚡ INSTALADOR & SINTONIZADOR SYSUTILS V3 (VULCAN CORE)")
    print("=" * 60)

    # 1. Estrutura de pastas
    log_step("1/4", "Preparando estrutura de diretórios e pacotes...")
    ensure_directories()
    log_ok("Estrutura de diretórios inicializada.")

    # 2. Atualizar pip/wheel
    log_step("2/4", "Atualizando gerenciadores de instalação (pip, wheel, setuptools)...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=True)
        log_ok("Gerenciadores de pacotes atualizados.")
    except Exception as e:
        log_warn(f"Não foi possível atualizar o pip base: {e}")

    # 3. Instalar dependências e registrar CLI
    log_step("3/4", "Instalando dependências e registrando comando 'sysutils'...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], cwd=str(ROOT), check=True)
        log_ok("Pacote 'sysutils' registrado com sucesso em modo editável.")
    except subprocess.CalledProcessError as e:
        log_err(f"Falha na instalação via pip. Erro: {e}")
        sys.exit(1)

    # 4. Compilação dos binários nativos C
    log_step("4/4", "Verificando e compilando aceleradores C nativos...")
    compile_native_binaries()

    print("\n" + "=" * 60)
    log_ok("INSTALAÇÃO CONCLUÍDA COM SUCESSO!")
    print("Para testar, digite no terminal:")
    print("   \033[1;33msysutils --help\033[0m")
    print("=" * 60)

if __name__ == "__main__":
    main()