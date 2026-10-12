# android_sys/core/installer.py
from __future__ import annotations
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = PROJECT_ROOT / "bin" / "android"

# URL direta oficial do pacote portátil Windows x64 (inclui scrcpy + adb + DLLs)
SCRCPY_WIN64_URL = "https://github.com/Genymobile/scrcpy/releases/download/v2.4/scrcpy-win64-v2.4.zip"

def get_binary_paths() -> dict[str, Path]:
    return {
        "adb": BIN_DIR / "adb.exe",
        "scrcpy": BIN_DIR / "scrcpy.exe"
    }

def is_installed() -> bool:
    bins = get_binary_paths()
    return bins["adb"].exists() and bins["scrcpy"].exists()

def ensure_binaries() -> tuple[bool, str]:
    if is_installed():
        return True, f"Ferramentas prontas em {BIN_DIR}"

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    zip_dest = BIN_DIR / "scrcpy_bundle.zip"
    
    try:
        print("[*] Baixando pacote portátil Android (ADB + Scrcpy)...")
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(SCRCPY_WIN64_URL, headers=headers)
        with urllib.request.urlopen(req) as resp, open(zip_dest, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)

        print("[*] Extraindo ferramentas em bin/android/...")
        with zipfile.ZipFile(zip_dest, "r") as z:
            for member in z.namelist():
                filename = os.path.basename(member)
                if not filename:
                    continue
                # Extrai os executáveis e DLLs na raiz de bin/android
                with z.open(member) as src, open(BIN_DIR / filename, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        zip_dest.unlink(missing_ok=True)

        if is_installed():
            return True, "Ambiente Android portátil configurado com sucesso!"
        return False, "Arquivos extraídos, mas adb.exe ou scrcpy.exe não foram encontrados."
    except Exception as e:
        zip_dest.unlink(missing_ok=True)
        return False, f"Falha no download/extração: {e}"
