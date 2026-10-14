# -*- coding: utf-8 -*-
# android_sys/core/apk_builder.py
"""
Hefesto: Compilador e Empacotador Autônomo de APKs Benzaiten (Sem Gradle).
Pipeline completo:
  1. aapt2 compile/link (Manifesto + Recursos)
  2. javac + d8 (Geração de classes.dex real)
  3. Injeção de assets HTML/JS na raiz do APK
  4. zipalign (Alinhamento de 4 bytes)
  5. apksigner v2/v3 oficial com OpenJDK 17
Conformidade: ProDeNov 1.2, 3.1.4 e 5.3.
"""
from __future__ import annotations
import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import Tuple, List, Optional
from android_sys.core import sdk_installer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "android_sys" / "templates" / "benzaiten_shell"
BUILD_DIR = PROJECT_ROOT / "data" / "android_build"

def preflight_check(source_assets_dir: Path | None = None) -> Tuple[bool, str]:
    sdk_installer.inject_java_env()
    tools = sdk_installer.get_required_tools()
    for name in ["aapt2", "zipalign", "android_jar"]:
        if not tools[name].exists():
            return False, f"Ferramenta '{name}' ausente. Execute 'sysutils android sdk setup --apply'."
    return True, "Preflight aprovado."

def _clean_res_dir(res_dir: Path):
    for py_file in res_dir.rglob("*.py"):
        try: py_file.unlink()
        except: pass
    for cache_dir in res_dir.rglob("__pycache__"):
        try: shutil.rmtree(cache_dir)
        except: pass

def _ensure_main_activity_source(src_file: Path):
    src_file.parent.mkdir(parents=True, exist_ok=True)
    if not src_file.exists():
        src_file.write_text("""package com.doxoade.benzaiten;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.util.Log;

public class MainActivity extends Activity {
    private WebView webView;
    private static final String TAG = "BenzaitenMobile";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);

        webView.addJavascriptInterface(new HermesBridge(), "__dx_native__");
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.loadUrl("file:///android_asset/index.html");
        setContentView(webView);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    public class HermesBridge {
        @JavascriptInterface
        public void send(String payload) {
            Log.d(TAG, "Hermes Message Received: " + payload);
            webView.post(new Runnable() {
                @Override
                public void run() {
                    String echo = "{\\\"status\\\":\\\"success\\\",\\\"payload\\\":{\\\"pong\\\":true}}";
                    webView.evaluateJavascript("window.__dx_receive__('" + echo + "');", null);
                }
            });
        }
    }
}
""", encoding="utf-8")

def build_apk(
    app_name: str = "Benzaiten NeoGUI",
    package_id: str = "com.doxoade.benzaiten",
    source_assets_dir: Path | None = None,
    output_apk: Path | None = None,
    dry_run: bool = False
) -> Tuple[bool, str, List[str]]:
    logs: List[str] = []
    ok_pre, err_pre = preflight_check(source_assets_dir)
    if not ok_pre:
        return False, err_pre, logs

    out_final = output_apk or (BUILD_DIR / "benzaiten_app.apk")
    assets_dir = source_assets_dir or (TEMPLATES_DIR / "assets")

    logs.append(f"Aplicação  : {app_name} ({package_id})")
    logs.append(f"Assets     : {assets_dir}")
    logs.append(f"Destino APK: {out_final}")

    if dry_run:
        logs.append("[DRY-RUN] Simulação das etapas:")
        logs.append("  1. aapt2 compile/link -> unaligned.apk")
        logs.append("  2. javac + d8 -> classes.dex")
        logs.append("  3. zip inject -> classes.dex + assets/")
        logs.append("  4. zipalign 4 -> aligned.apk")
        logs.append("  5. apksigner v2/v3 -> benzaiten_app.apk")
        return True, "Simulação de compilação bem-sucedida.", logs

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    tools = sdk_installer.get_required_tools()

    tmp_res_zip = BUILD_DIR / "res.zip"
    tmp_unaligned_apk = BUILD_DIR / "unaligned.apk"
    tmp_aligned_apk = BUILD_DIR / "aligned.apk"
    tmp_classes_dir = BUILD_DIR / "classes"

    res_dir = TEMPLATES_DIR / "res"
    _clean_res_dir(res_dir)

    # 1. aapt2 compile
    logs.append("[*] Compilando recursos visuais com aapt2...")
    cmd_compile = [str(tools["aapt2"]), "compile", "--dir", str(res_dir), "-o", str(tmp_res_zip)]
    p_comp = subprocess.run(cmd_compile, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p_comp.returncode != 0:
        return False, f"Falha no aapt2 compile: {p_comp.stderr or p_comp.stdout}", logs

    # 2. aapt2 link
    logs.append("[*] Vinculando manifesto e gerando APK base...")
    manifest_path = TEMPLATES_DIR / "AndroidManifest.xml"
    cmd_link = [
        str(tools["aapt2"]), "link",
        "-I", str(tools["android_jar"]),
        "--manifest", str(manifest_path),
        str(tmp_res_zip),
        "-o", str(tmp_unaligned_apk),
        "--auto-add-overlay"
    ]
    p_link = subprocess.run(cmd_link, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p_link.returncode != 0:
        return False, f"Falha no aapt2 link: {p_link.stderr or p_link.stdout}", logs

    # 3. Compilação Java ➔ classes.dex
    logs.append("[*] Compilando MainActivity.java e gerando classes.dex...")
    dex_out = BUILD_DIR / "classes.dex"
    java_src = TEMPLATES_DIR / "src" / "MainActivity.java"
    _ensure_main_activity_source(java_src)

    javac_bin = sdk_installer.find_java_tool("javac")
    if javac_bin:
        tmp_classes_dir.mkdir(parents=True, exist_ok=True)
        cmd_javac = [
            javac_bin, "-cp", str(tools["android_jar"]),
            "-d", str(tmp_classes_dir),
            str(java_src)
        ]
        p_javac = subprocess.run(cmd_javac, capture_output=True, text=True)
        if p_javac.returncode != 0:
            return False, f"Falha no javac: {p_javac.stderr}", logs

        class_files = [str(p) for p in tmp_classes_dir.rglob("*.class")]
        cmd_d8 = [str(tools["d8"]), "--output", str(BUILD_DIR), "--min-api", "24"] + class_files
        p_d8 = subprocess.run(cmd_d8, shell=True, capture_output=True, text=True)
        if p_d8.returncode != 0:
            return False, f"Falha no d8: {p_d8.stderr}", logs
    else:
        return False, "Compilador 'javac' não encontrado.", logs

    # 4. Injeção de classes.dex e assets HTML/JS
    logs.append("[*] Injetando classes.dex e assets HTML/JS...")
    with zipfile.ZipFile(tmp_unaligned_apk, "a", compression=zipfile.ZIP_DEFLATED) as z_out:
        if dex_out.exists():
            z_out.write(dex_out, arcname="classes.dex")
        for root, _, files in os.walk(assets_dir):
            for file in files:
                f_path = Path(root) / file
                rel_path = f_path.relative_to(assets_dir)
                z_out.write(f_path, arcname=f"assets/{rel_path.as_posix()}")

    # 5. zipalign
    logs.append("[*] Alinhando memória de 4 bytes com zipalign...")
    tmp_aligned_apk.unlink(missing_ok=True)
    cmd_align = [str(tools["zipalign"]), "-p", "-f", "4", str(tmp_unaligned_apk), str(tmp_aligned_apk)]
    p_align = subprocess.run(cmd_align, capture_output=True, text=True)
    if p_align.returncode != 0:
        return False, f"Falha no zipalign: {p_align.stderr or p_align.stdout}", logs

    # 6. Assinatura com apksigner oficial
    logs.append("[*] Assinando pacote com apksigner (v2/v3 compatível com Android 13)...")
    out_final.unlink(missing_ok=True)
    ok_sign, msg_sign = _sign_apk_official(tmp_aligned_apk, out_final, tools)
    if not ok_sign:
        return False, msg_sign, logs

    # Limpeza
    tmp_res_zip.unlink(missing_ok=True)
    tmp_unaligned_apk.unlink(missing_ok=True)
    tmp_aligned_apk.unlink(missing_ok=True)
    if tmp_classes_dir.exists():
        shutil.rmtree(tmp_classes_dir, ignore_errors=True)

    size_kb = out_final.stat().st_size / 1024
    logs.append(f"✔ [OK] APK compilado e assinado: {out_final.name} ({size_kb:.1f} KB)")
    return True, f"APK gerado em {out_final}", logs

def _sign_apk_official(src_apk: Path, dest_apk: Path, tools: dict) -> Tuple[bool, str]:
    sdk_installer.inject_java_env()
    keystore_path = BUILD_DIR / "debug.keystore"
    keytool_bin = sdk_installer.find_java_tool("keytool")

    # Higienização: se a keystore for o arquivo dummy antigo (começa com fe ed fe ed), apaga para forçar geração real
    if keystore_path.exists():
        try:
            head = keystore_path.read_bytes()[:4]
            if head == b"\xfe\xed\xfe\xed" or keystore_path.stat().st_size < 2100:
                keystore_path.unlink()
        except Exception:
            pass

    if not keystore_path.exists() and keytool_bin:
        cmd_gen = [
            keytool_bin, "-genkeypair", "-v",
            "-keystore", str(keystore_path),
            "-storetype", "PKCS12",
            "-storepass", "android",
            "-alias", "androiddebugkey",
            "-keypass", "android",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-dname", "CN=Android Debug,O=Android,C=US"
        ]
        res_key = subprocess.run(cmd_gen, capture_output=True, text=True)
        if res_key.returncode != 0:
            return False, f"Falha ao gerar debug.keystore: {res_key.stderr or res_key.stdout}"

    if keystore_path.exists():
        cmd_sign = [
            str(tools["apksigner"]), "sign",
            "--ks", str(keystore_path),
            "--ks-pass", "pass:android",
            "--ks-key-alias", "androiddebugkey",
            "--key-pass", "pass:android",
            "--out", str(dest_apk),
            str(src_apk)
        ]
        res = subprocess.run(cmd_sign, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            return True, "Assinatura v2/v3 oficial validada."
        else:
            return False, f"Falha no apksigner: {res.stderr or res.stdout}"

    return False, "Não foi possível assinar o APK. keytool ou apksigner indisponíveis."
