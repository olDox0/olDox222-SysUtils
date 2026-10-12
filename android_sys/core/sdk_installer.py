# -*- coding: utf-8 -*-
# android_sys/core/sdk_installer.py
"""
Hefesto: Gerenciador de Instalação e Auditoria do Android SDK Mínimo (Headless).
Responsável pela aquisição cirúrgica de aapt2, d8, zipalign e android.jar
sem necessidade de instalação do Android Studio ou do daemon do Gradle.
"""
from __future__ import annotations
import os
import sys
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Tuple

# Constantes de Topologia
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_ANDROID_DIR = PROJECT_ROOT / "bin" / "android"
BUILD_TOOLS_DIR = BIN_ANDROID_DIR / "build-tools"

# URLs oficiais e fixas dos binários headless
AAPT2_STANDALONE_URL = "https://dl.google.com/dl/android/maven2/com/android/tools/build/aapt2/8.2.2-10154469/aapt2-8.2.2-10154469-windows.jar"
COMMANDLINE_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"

def get_required_tools() -> Dict[str, Path]:
    """Retorna o dicionário de ferramentas essenciais para build sem Gradle."""
    return {
        "aapt2": BUILD_TOOLS_DIR / "aapt2.exe",
        "d8": BUILD_TOOLS_DIR / "d8.bat",
        "zipalign": BUILD_TOOLS_DIR / "zipalign.exe",
        "apksigner": BUILD_TOOLS_DIR / "apksigner.bat",
        "android_jar": BUILD_TOOLS_DIR / "android.jar",
    }

def audit_sdk_tools() -> Dict[str, bool]:
    """Inspeciona o disco e verifica quais ferramentas estão presentes e executáveis."""
    tools = get_required_tools()
    return {name: path.exists() and path.stat().st_size > 1024 for name, path in tools.items()}

def is_sdk_ready() -> bool:
    """Retorna True se todo o kit cirúrgico estiver pronto para compilação."""
    return all(audit_sdk_tools().values())

def install_minimal_sdk(dry_run: bool = True) -> Tuple[bool, str]:
    """
    Executa o download e instalação cirúrgica dos componentes necessários.
    Suporta salvaguarda dry-run obrigatória (ProDeNov 5.3).
    """
    # Fluxo a ser implementado no RIT 1
    raise NotImplementedError("Implementação controlada no RIT 1.")
