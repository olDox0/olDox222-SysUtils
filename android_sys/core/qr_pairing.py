# android_sys/core/qr_pairing.py
from __future__ import annotations
import os
import re
import time
import random
import secrets
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from android_sys.core.installer import get_binary_paths

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QR_HTML_PATH = PROJECT_ROOT / "data" / "android_qr.html"

def generate_pairing_payload() -> Tuple[str, str, str]:
    """Gera o payload oficial do padrão AOSP Android 11+."""
    service_name = f"sysutils_{secrets.token_hex(3)}"
    pairing_code = f"{random.randint(100000, 999999)}"
    # Formato oficial do protocolo de pareamento do Android
    payload = f"WIFI:T:ADB;S:{service_name};P:{pairing_code};;"
    return service_name, pairing_code, payload

def create_qr_html(payload: str, service_name: str, code: str) -> Path:
    """Gera uma página local de altíssima definição para a câmera focar instantaneamente."""
    QR_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # URL da API de renderização SVG rápida e nítida
    qr_img_url = f"https://api.qrserver.com/v1/create-qr-code/?size=320x320&data={payload}&margin=10"
    
    html_content = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>SysUtils — Pareamento Android QR</title>
    <style>
        body {{
            background: #121214;
            color: #E1E1E6;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }}
        .card {{
            background: #202024;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
            text-align: center;
            border: 1px solid #323238;
        }}
        h2 {{ color: #00B37E; margin-top: 0; }}
        .qr-box {{
            background: #FFFFFF;
            padding: 16px;
            border-radius: 8px;
            display: inline-block;
            margin: 20px 0;
        }}
        img {{ display: block; }}
        .info {{ color: #A8A8B3; font-size: 14px; margin-top: 10px; }}
        .badge {{ background: #29292E; padding: 6px 12px; border-radius: 4px; font-family: monospace; color: #E1E1E6; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>⚡ PAREAMENTO ANDROID SEM FIO</h2>
        <p>No celular: <b>Opções do Desenvolvedor ➔ Depuração sem fio ➔ Parear com código QR</b></p>
        <div class="qr-box">
            <img src="{qr_img_url}" alt="QR Code" width="300" height="300" />
        </div>
        <div class="info">
            Serviço: <span class="badge">{service_name}</span> | Código: <span class="badge">{code}</span>
        </div>
        <p style="color: #7C7C8A; font-size: 12px; margin-top: 20px;">
            Aponte a câmera. A conexão será estabelecida automaticamente no terminal.
        </p>
    </div>
</body>
</html>"""
    QR_HTML_PATH.write_text(html_content, encoding="utf-8")
    return QR_HTML_PATH

def listen_and_pair_mdns(service_name: str, pairing_code: str, timeout: int = 60) -> Tuple[bool, str]:
    """Monitora o mDNS do ADB para capturar o celular assim que a câmera escanear o QR."""
    adb_bin = get_binary_paths()["adb"]
    env = os.environ.copy()
    env["ADB_MDNS_OPENSCREEN"] = "1"  # Ativa o motor nativo de descoberta mDNS

    # Garante o servidor ADB ativo
    subprocess.run([str(adb_bin), "start-server"], env=env, capture_output=True)

    start_time = time.time()
    discovered_pairing_target = None

    while time.time() - start_time < timeout:
        # Consulta serviços mDNS anunciados na rede Wi-Fi
        res = subprocess.run([str(adb_bin), "mdns", "services"], env=env, capture_output=True, text=True)
        
        # Procura anúncio de pareamento do Android (_adb-tls-pairing._tcp)
        for line in res.stdout.splitlines():
            if "_adb-tls-pairing._tcp" in line:
                match = re.search(r"(\d+\.\d+\.\d+\.\d+:\d+)", line)
                if match:
                    discovered_pairing_target = match.group(1)
                    break
        
        if discovered_pairing_target:
            break
        time.sleep(1.2)

    if not discovered_pairing_target:
        return False, "Tempo esgotado. A câmera não escaneou o QR Code a tempo."

    # 1. Executa o pareamento automático usando a senha do QR Code
    pair_res = subprocess.run([str(adb_bin), "pair", discovered_pairing_target, pairing_code], env=env, capture_output=True, text=True)
    if "successfully paired" not in pair_res.stdout.lower() and pair_res.returncode != 0:
        return False, f"Falha no handshake de pareamento: {pair_res.stdout or pair_res.stderr}"

    ip_base = discovered_pairing_target.split(":")[0]
    
    # 2. Aguarda o celular anunciar a porta de conexão principal (_adb-tls-connect._tcp)
    connect_target = None
    connect_start = time.time()
    while time.time() - connect_start < 10:
        res = subprocess.run([str(adb_bin), "mdns", "services"], env=env, capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if "_adb-tls-connect._tcp" in line and ip_base in line:
                match = re.search(r"(\d+\.\d+\.\d+\.\d+:\d+)", line)
                if match:
                    connect_target = match.group(1)
                    break
        if connect_target:
            break
        time.sleep(1.0)

    # 3. Conecta automaticamente
    if connect_target:
        conn_res = subprocess.run([str(adb_bin), "connect", connect_target], env=env, capture_output=True, text=True)
        return True, f"Pareado e conectado com sucesso em {connect_target}!"
    else:
        # Fallback para a porta padrão caso o mDNS demore a responder
        subprocess.run([str(adb_bin), "connect", f"{ip_base}:5555"], env=env, capture_output=True)
        return True, f"Pareado com sucesso em {discovered_pairing_target}! Conecte informando a porta principal."

