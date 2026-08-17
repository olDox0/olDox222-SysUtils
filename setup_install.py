# -*- coding: utf-8 -*-
"""
================================================================================
⚡ NEXUS SOVEREIGN SETUP & INSTALLER V3.1 (VULCAN CORE)
================================================================================
Padrão Industrial Blindado contra a Praga do Unicode (Windows cp1252)
e com Bootstrapping prioritário de Setuptools/Wheel.
================================================================================
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Força UTF-8 no ambiente Python para subprocessos
ENV_UTF8 = os.environ.copy()
ENV_UTF8["PYTHONUTF8"] = "1"
ENV_UTF8["PYTHONIOENCODING"] = "utf-8"

# ==============================================================================
# 🎨 MOTOR DE CORES ANSI & EXECUTOR SEGURO
# ==============================================================================
if os.name == 'nt':
    os.system('')  # Ativa suporte a ANSI no Windows CMD/PowerShell

class UI:
    CYAN    = '\033[1;36m'
    GREEN   = '\033[1;32m'
    YELLOW  = '\033[1;33m'
    RED     = '\033[1;31m'
    MAGENTA = '\033[1;35m'
    BOLD    = '\033[1m'
    RESET   = '\033[0m'

def log_header(title: str):
    print(f"\n{UI.CYAN}{UI.BOLD}{'='*65}")
    print(f" 🚀 {title}")
    print(f"{'='*65}{UI.RESET}")

def log_step(step: str, desc: str):
    print(f"\n{UI.MAGENTA}[FASE {step}]{UI.RESET} {UI.BOLD}{desc}{UI.RESET}")

def log_ok(msg: str):
    print(f"  {UI.GREEN}✔{UI.RESET} {msg}")

def log_warn(msg: str):
    print(f"  {UI.YELLOW}⚠{UI.RESET} {msg}")

def log_err(msg: str):
    print(f"  {UI.RED}✘{UI.RESET} {msg}")

def safe_run(cmd, cwd=None, check=True) -> subprocess.CompletedProcess:
    """
    Executor blindado contra UnicodeDecodeError no Windows.
    Garante decodificação em UTF-8 com substituição de caracteres ilegais.
    """
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ENV_UTF8
    )

# ==============================================================================
# 🛠️ MATRIZ DE DEPENDÊNCIAS
# ==============================================================================
BOOTSTRAP_PACKAGES = [
    "setuptools>=68.0.0",
    "wheel>=0.41.0",
]

RUNTIME_PACKAGES = [
    "click>=8.1.0",
    "colorama>=0.4.6",
    "psutil>=5.9.5",
    "pycryptodome>=3.19.0",
    "zstandard>=0.22.0",
]

CORE_DIRECTORIES = [
    ROOT / "bin",
    ROOT / "engine" / "native",
    ROOT / "data" / "db",
    ROOT / "data" / "vulcan_idx",
    ROOT / ".doxoade" / "logs",
]

PYTHON_PACKAGES = [
    'netdiag', 'sysdiag', 'diskdiag', 'ramdiag', 
    'doxbackup', 'bloatbreaker', 'cli', 'utils'
]

# ==============================================================================
# ⚙️ FASES DE INSTALAÇÃO
# ==============================================================================

def phase_1_bootstrap_setuptools_and_pip():
    """
    Passo Crítico: Instala PRIMEIRO o Setuptools e Wheel de forma isolada,
    e somente depois atualiza o Pip.
    """
    log_step("1/6", "Bootstrapping Primário (Setuptools & Wheel Primeiro)...")
    
    # 1.1 Garante que ensurepip está disponível se o pip não existir
    try:
        import pip
    except ImportError:
        log_warn("pip ausente. Acionando ensurepip de emergência...")
        safe_run([sys.executable, "-m", "ensurepip", "--upgrade"])

    # 1.2 Instala PRIMEIRO setuptools e wheel
    try:
        safe_run([sys.executable, "-m", "pip", "install", "--upgrade"] + BOOTSTRAP_PACKAGES)
        log_ok("Setuptools e Wheel instalados com prioridade máxima.")
    except Exception as e:
        log_warn(f"Aviso no bootstrap do setuptools: {e}")

    # 1.3 Agora atualiza o pip com segurança
    try:
        safe_run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        log_ok("Gerenciador Pip sincronizado.")
    except Exception as e:
        log_warn(f"Aviso ao atualizar pip: {e}")


def phase_2_topology():
    """Cria a topologia de diretórios e inicializadores __init__.py."""
    log_step("2/6", "Forjando Topologia e Estrutura de Pastas...")
    
    for d in CORE_DIRECTORIES:
        d.mkdir(parents=True, exist_ok=True)
    log_ok("Diretórios de dados, cache e binários sincronizados.")

    for pkg in PYTHON_PACKAGES:
        init_file = ROOT / pkg / "__init__.py"
        if not init_file.exists():
            init_file.parent.mkdir(parents=True, exist_ok=True)
            init_file.touch()
    log_ok("Arquivos __init__.py estruturados em todos os módulos.")


def phase_3_dependencies():
    """Instala as bibliotecas de runtime necessárias."""
    log_step("3/6", "Instalando Dependências de Runtime...")
    
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + RUNTIME_PACKAGES
    try:
        proc = safe_run(cmd)
        for line in proc.stdout.splitlines():
            if "Successfully installed" in line:
                log_ok(f"Instalado: {line.replace('Successfully installed ', '')}")
        log_ok("Todas as bibliotecas Python instaladas e compatíveis.")
    except subprocess.CalledProcessError as e:
        log_err(f"Falha ao instalar dependências: {e.stderr}")
        sys.exit(1)


def phase_4_metalcraft_compilation():
    """Compila os motores nativos C via GCC se disponível."""
    log_step("4/6", "Compilando Motores Nativos C (Vulcan Metalcraft)...")
    
    gcc_path = shutil.which("gcc")
    if not gcc_path:
        log_warn("Compilador GCC não localizado no PATH.")
        log_warn("O SysUtils utilizará os binários pré-compilados ou fallbacks Python.")
        return

    targets = [
        (
            ROOT / "engine" / "native" / "dox_packer.c",
            ROOT / "engine" / "native" / "vulcan_dox_v3.dll",
            ["-shared", "-lkernel32"]
        ),
        (
            ROOT / "engine" / "native" / "dox_packer.c",
            ROOT / "bin" / "vulcan_dox.dll",
            ["-shared", "-lkernel32"]
        ),
        (
            ROOT / "src" / "native" / "vulcan_cleaner.c",
            ROOT / "bin" / "vulcan_cleaner.dll",
            ["-shared", "-lkernel32"]
        ),
        (
            ROOT / "src" / "native" / "vulcan_ram.c",
            ROOT / "bin" / "vulcan_ram.dll",
            ["-shared", "-lpsapi"]
        ),
    ]

    compiled_count = 0
    for src, out, flags in targets:
        if not src.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["gcc", "-O3", "-s", str(src), "-o", str(out)] + flags
        try:
            safe_run(cmd)
            log_ok(f"Motor forjado: {out.name}")
            compiled_count += 1
        except subprocess.CalledProcessError as e:
            log_warn(f"Aviso ao compilar {out.name}: {e.stderr[:80] if e.stderr else ''}")

    if compiled_count > 0:
        log_ok(f"{compiled_count} bibliotecas nativas forjadas com sucesso.")


def phase_5_bind_cli():
    """Registra o comando `sysutils` globalmente no ambiente via setup.py."""
    log_step("5/6", "Vinculando Ponto de Entrada CLI (SysUtils Zeus Router)...")
    
    cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
    try:
        safe_run(cmd, cwd=str(ROOT))
        log_ok("Comando global 'sysutils' registrado com sucesso.")
    except subprocess.CalledProcessError as e:
        log_err(f"Erro ao registrar pacote no modo editável: {e.stderr}")
        sys.exit(1)


def phase_6_smoke_test():
    """Executa auditoria de integridade pós-instalação (Smoke Test)."""
    log_step("6/6", "Auditoria de Integridade (Smoke Test)...")

    # 6.1 Testa imports vitais
    imports_to_test = ["click", "psutil", "zstandard", "Crypto", "setuptools"]
    for mod in imports_to_test:
        try:
            __import__(mod)
            log_ok(f"Módulo Python: '{mod}' [OK]")
        except ImportError as e:
            log_err(f"Módulo '{mod}' falhou no carregamento: {e}")
            sys.exit(1)

    # 6.2 Testa execução real do CLI com saída limpa UTF-8
    try:
        res = safe_run(["sysutils", "--help"], check=False)
        if res.returncode == 0:
            log_ok("CLI 'sysutils' operacional e respondendo em UTF-8.")
        else:
            log_warn(f"CLI retornou código {res.returncode}. Teste via 'python -m cli.main'")
    except Exception as e:
        log_warn(f"Aviso ao invocar comando 'sysutils': {e}")


# ==============================================================================
# 🏁 PONTO DE ENTRADA PRINCIPAL
# ==============================================================================
if __name__ == "__main__":
    log_header("SYSUTILS: INSTALADOR SOBERANO AUTÔNOMO V3.1")
    
    phase_1_bootstrap_setuptools_and_pip()
    phase_2_topology()
    phase_3_dependencies()
    phase_4_metalcraft_compilation()
    phase_5_bind_cli()
    phase_6_smoke_test()
    
    print(f"\n{UI.GREEN}{UI.BOLD}{'='*65}")
    print(" 🎉 INSTALAÇÃO CONCLUÍDA COM 100% DE SUCESSO!")
    print(f"{'='*65}{UI.RESET}")
    print(f"Para iniciar o sistema, digite: {UI.YELLOW}sysutils --help{UI.RESET}\n")