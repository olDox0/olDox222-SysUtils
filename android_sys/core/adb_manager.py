# -*- coding: utf-8 -*-
# android_sys/core/adb_manager.py
"""
Hermes / Poseidon: Gerenciador de Comunicação ADB e Envio sem Fio (TCP/IP).
Controla conexões, pareamento mDNS/código e instalação remota de APKs via Wi-Fi.
Conformidade: ProDeNov 2.1 e 3.1.4.
"""
from __future__ import annotations
import json
import socket
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
from android_sys.core.installer import get_binary_paths

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "data" / "android_config.json"

def save_last_ip(ip: str):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg["last_ip"] = ip
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def run_adb(args: List[str]) -> subprocess.CompletedProcess:
    adb_bin = get_binary_paths()["adb"]
    cmd = [str(adb_bin)] + args
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

def pair_device(ip_port: str, code: str) -> Tuple[bool, str]:
    """Pareia com o celular usando a porta efêmera e o código de 6 dígitos."""
    res = run_adb(["pair", ip_port, code])
    out = res.stdout.strip() or res.stderr.strip()
    success = "successfully paired" in out.lower() or res.returncode == 0
    if success and ":" in ip_port:
        save_last_ip(ip_port.split(":")[0])
    return success, out

def connect_device(target: str) -> Tuple[bool, str]:
    """Conecta ao serviço principal de depuração Wi-Fi do celular."""
    cfg = load_config()
    last_ip = cfg.get("last_ip", "192.168.18.105")

    # Tratamento de atalhos de porta
    if target.isdigit():
        target = f"{last_ip}:{target}"
    elif target.startswith(":"):
        target = f"{last_ip}{target}"
    elif ":" not in target:
        target = f"{target}:5555"

    if ":" in target and not target.startswith(":"):
        save_last_ip(target.split(":")[0])

    res = run_adb(["connect", target])
    out = res.stdout.strip() or res.stderr.strip()
    success = "connected to" in out.lower()
    return success, out

def get_connected_devices() -> List[str]:
    """Retorna os dispositivos Android conectados e ativos."""
    res = run_adb(["devices"])
    devices = []
    for line in res.stdout.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices

def install_apk(device_target: str, apk_path: Path) -> Tuple[bool, str]:
    """Envia e instala um arquivo APK diretamente no celular pelo ar (Wi-Fi)."""
    if not apk_path.exists():
        return False, f"Arquivo não encontrado: {apk_path}"

    # Executa o adb install com flag -r (reinstall preservando dados)
    res = run_adb(["-s", device_target, "install", "-r", str(apk_path.resolve())])
    out = res.stdout.strip() or res.stderr.strip()
    success = "success" in out.lower()
    return success, out

def scan_and_auto_connect(ip: str | None = None) -> Tuple[bool, str]:
    """Varre as portas dinâmicas do Android na rede Wi-Fi e conecta sozinho."""
    target_ip = ip or load_config().get("last_ip", "192.168.18.105")
    if not target_ip:
        return False, "Nenhum IP registrado. Conecte ao menos uma vez informando IP:porta."

    print(f"[*] Varrendo portas ativas no celular ({target_ip})...")
    candidate_ports = []
    for port in range(35000, 45001):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.015)
        if s.connect_ex((target_ip, port)) == 0:
            candidate_ports.append(port)
        s.close()
        if len(candidate_ports) >= 2:
            break

    if not candidate_ports:
        return False, f"Nenhuma porta de depuração aberta detectada em {target_ip}."

    for p in candidate_ports:
        ok, msg = connect_device(f"{target_ip}:{p}")
        if ok:
            return True, f"Conectado com sucesso em {target_ip}:{p}!"

    return False, "Portas localizadas, mas o celular recusou a conexão."
