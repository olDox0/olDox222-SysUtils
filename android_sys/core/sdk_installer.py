# -*- coding: utf-8 -*-
# android_sys/core/sdk_installer.py
"""
Hefesto: Gerenciador de Instalação e Auditoria do Android SDK Mínimo (Headless).
Fornece aquisição cirúrgica dos binários de compilação e autodetecção de JDK.
Conformidade: ProDeNov 1.2, 3.1.4 e 5.3.
"""
from __future__ import annotations
import os
import sys
import shutil
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from typing import Dict, Tuple, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_ANDROID_DIR = PROJECT_ROOT / "bin" / "android"
BUILD_TOOLS_DIR = BIN_ANDROID_DIR / "build-tools"

BUILD_TOOLS_URL_A = "https://dl.google.com/android/repository/build-tools_r34-windows.zip"
BUILD_TOOLS_URL_B = "https://dl.google.com/android/repository/build-tools_r33-windows.zip"
PLATFORM_JAR_URL_A = "https://dl.google.com/android/repository/platform-33_r02.zip"
PLATFORM_JAR_URL_B = "https://dl.google.com/android/repository/platform-34-ext7_r03.zip"

def find_java_tool(tool_name: str = "java") -> Optional[str]:
    """Localiza executáveis do Java no PATH ou nas pastas padrões do Windows."""
    found = shutil.which(tool_name)
    if found:
        return found

    ext = ".exe" if os.name == "nt" else ""
    common_roots = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Eclipse Adoptium",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Java",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Eclipse Adoptium",
    ]

    for root in common_roots:
        if root.exists():
            for p in root.glob(f"**/bin/{tool_name}{ext}"):
                if p.exists():
                    return str(p)
    return None

def inject_java_env() -> bool:
    """Injeta dinamicamente o JDK no PATH do processo atual sem reiniciar o terminal."""
    java_exe = find_java_tool("java")
    if not java_exe:
        return False
    bin_dir = str(Path(java_exe).parent)
    if bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{bin_dir};" + os.environ.get("PATH", "")
    os.environ["JAVA_HOME"] = str(Path(java_exe).parent.parent)
    return True

def get_required_tools() -> Dict[str, Path]:
    return {
        "aapt2": BUILD_TOOLS_DIR / "aapt2.exe",
        "zipalign": BUILD_TOOLS_DIR / "zipalign.exe",
        "d8": BUILD_TOOLS_DIR / "d8.bat",
        "apksigner": BUILD_TOOLS_DIR / "apksigner.bat",
        "android_jar": BUILD_TOOLS_DIR / "android.jar",
    }

def audit_sdk_tools() -> Dict[str, Dict]:
    inject_java_env()
    tools = get_required_tools()
    audit_results = {}
    java_bin = find_java_tool("java")

    for name, path in tools.items():
        exists = path.exists()
        size_bytes = path.stat().st_size if exists else 0
        audit_results[name] = {
            "path": str(path),
            "exists": exists,
            "size_bytes": size_bytes,
            "size_formatted": _format_size(size_bytes),
            "status": "✔ OK" if (exists and size_bytes > 1024) else "✘ AUSENTE"
        }

    audit_results["java_runtime"] = {
        "path": java_bin or "Não localizado no PATH",
        "exists": java_bin is not None,
        "size_bytes": 0,
        "size_formatted": "Host OS",
        "status": "✔ OK" if java_bin else "⚠ ADVISORY"
    }

    return audit_results

def is_sdk_ready() -> bool:
    tools_audit = audit_sdk_tools()
    vital_keys = ["aapt2", "zipalign", "android_jar"]
    return all(tools_audit[k]["exists"] for k in vital_keys)

def install_minimal_sdk(apply_changes: bool = False) -> Tuple[bool, str, List[str]]:
    logs: List[str] = []
    tools = get_required_tools()
    missing = [name for name, p in tools.items() if not p.exists() or p.stat().st_size < 1024]

    if not missing:
        return True, "Todos os binários do SDK Headless já estão presentes e íntegros.", logs

    logs.append(f"Componentes ausentes identificados: {', '.join(missing)}")
    logs.append(f"Diretório de destino: {BUILD_TOOLS_DIR}")

    if not apply_changes:
        return True, "DRY-RUN CONCLUÍDO. Use '--apply' para baixar.", logs

    BUILD_TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    temp_build_tools_zip = BUILD_TOOLS_DIR / "build_tools_temp.zip"
    temp_platform_zip    = BUILD_TOOLS_DIR / "platform_temp.zip"
    headers = {"User-Agent": "Mozilla/5.0"}

    need_tools = any(k in missing for k in ["aapt2", "zipalign", "d8", "apksigner"])
    if need_tools:
        logs.append("[*] Baixando Google Build-Tools Headless...")
        ok_a, err_a = _download_with_progress(BUILD_TOOLS_URL_A, temp_build_tools_zip, headers)
        if not ok_a:
            ok_a, err_a = _download_with_progress(BUILD_TOOLS_URL_B, temp_build_tools_zip, headers)
            if not ok_a:
                return False, f"Falha no download: {err_a}", logs

        with zipfile.ZipFile(temp_build_tools_zip, "r") as z:
            for member in z.namelist():
                base_name = os.path.basename(member)
                if not base_name: continue
                if base_name in ("aapt2.exe", "zipalign.exe", "d8.bat", "apksigner.bat"):
                    with z.open(member) as src, open(BUILD_TOOLS_DIR / base_name, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                if base_name in ("d8.jar", "apksigner.jar"):
                    lib_dir = BUILD_TOOLS_DIR / "lib"
                    lib_dir.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as src, open(lib_dir / base_name, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        temp_build_tools_zip.unlink(missing_ok=True)

    if "android_jar" in missing:
        logs.append("[*] Baixando Platform Stubs (android.jar)...")
        ok_p, err_p = _download_with_progress(PLATFORM_JAR_URL_A, temp_platform_zip, headers)
        if not ok_p:
            ok_p, err_p = _download_with_progress(PLATFORM_JAR_URL_B, temp_platform_zip, headers)
        if ok_p:
            with zipfile.ZipFile(temp_platform_zip, "r") as z:
                for member in z.namelist():
                    if member.endswith("android.jar"):
                        with z.open(member) as src, open(BUILD_TOOLS_DIR / "android.jar", "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        break
            temp_platform_zip.unlink(missing_ok=True)

    return True, "SDK Mínimo Headless validado com sucesso!", logs

def _download_with_progress(url: str, dest_path: Path, headers: dict) -> Tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as resp:
            total_size = resp.getheader('Content-Length')
            total_bytes = int(total_size) if total_size and total_size.isdigit() else 0
            downloaded = 0
            chunk_size = 1024 * 512
            with open(dest_path, "wb") as out_f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk: break
                    out_f.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes > 0 and sys.stdout.isatty():
                        pct = (downloaded / total_bytes) * 100
                        mb_d = downloaded / (1024 * 1024)
                        mb_t = total_bytes / (1024 * 1024)
                        sys.stdout.write(f"\r    Progresso: {mb_d:.1f} MB / {mb_t:.1f} MB ({pct:.1f}%)")
                        sys.stdout.flush()
            if sys.stdout.isatty(): sys.stdout.write("\n")
        return dest_path.exists() and dest_path.stat().st_size > 1024, "Concluído"
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        return False, str(e)

def _format_size(size: int) -> str:
    if size <= 0: return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"
