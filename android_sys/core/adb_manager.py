# android_sys/core/adb_manager.py
from __future__ import annotations
import json
import socket
import subprocess
from pathlib import Path
from typing import List, Optional
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
        try: return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except: pass
    return {}

def run_adb(args: List[str]) -> subprocess.CompletedProcess:
    adb_bin = get_binary_paths()["adb"]
    cmd = [str(adb_bin)] + args
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

def pair_device(ip_port: str, code: str) -> tuple[bool, str]:
    res = run_adb(["pair", ip_port, code])
    out = res.stdout.strip() or res.stderr.strip()
    success = "successfully paired" in out.lower() or res.returncode == 0
    if success and ":" in ip_port:
        save_last_ip(ip_port.split(":")[0])
    return success, out

def connect_device(target: str) -> tuple[bool, str]:
    cfg = load_config()
    last_ip = cfg.get("last_ip", "192.168.18.105")
    
    # Se o usuário passou apenas a porta de 5 dígitos (ex: '41235')
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
    res = run_adb(["devices"])
    devices = []
    for line in res.stdout.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices

def scan_and_auto_connect(ip: str | None = None) -> tuple[bool, str]:
    """Varre as portas dinâmicas do Android na rede Wi-Fi e conecta sozinho."""
    target_ip = ip or load_config().get("last_ip")
    if not target_ip:
        return False, "Nenhum IP registrado. Conecte ao menos uma vez informando IP:porta."

    print(f"[*] Varrendo portas ativas no celular ({target_ip})...")
    # No Android, a depuração sem fio sorteia portas entre 30000 e 47000
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
        return False, f"Nenhuma porta de depuração aberta detectada em {target_ip}. A 'Depuração sem fio' está ligada no celular?"

    for p in candidate_ports:
        ok, msg = connect_device(f"{target_ip}:{p}")
        if ok:
            return True, f"Conectado com sucesso em {target_ip}:{p}!"

    return False, "Portas localizadas, mas o celular recusou a conexão."
