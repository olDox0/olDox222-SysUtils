# energy_sys/core/power_strategies.py
from __future__ import annotations
import json
import re
import subprocess
import psutil
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASELINE_FILE = PROJECT_ROOT / "data" / "power_baseline.json"
STATE_FILE = PROJECT_ROOT / "data" / "power_state.json"

STRATEGIES = {
    "cpu-limit": {
        "name": "Teto de Frequência da CPU (80% na Bateria)",
        "sub": "SUB_PROCESSOR",
        "setting": "PROCTHROTTLEMAX",
        "eco_value": 80,
        "default_value": 100,
        "risk": "BAIXO",
        "risk_details": "Reduz o pico de clock da CPU na bateria. Não afeta a máquina na tomada.",
        "benefits": "Corta picos de consumo e reduz o aquecimento interno na bateria."
    },
    "wifi-sleep": {
        "name": "Economia de Energia do Wi-Fi na Bateria",
        "sub": "19cbb8fa-5279-450e-9f18-0a6727fbba81",  # GUID padrão da Wireless Adapter Settings
        "setting": "12bbe462-763e-4272-97f7-da30076dbd16", # Economia Máxima de Energia
        "eco_value": 3,                                    # 3 = Economia Máxima de Energia
        "default_value": 0,                                # 0 = Desempenho Máximo
        "alt_sub": "SUB_NONE",
        "alt_setting": "0e796bdb-100d-47d6-a2e5-f7d2daa51f51", # Modern Standby (Win 11)
        "risk": "BAIXO",
        "risk_details": "O rádio Wi-Fi entra em repouso agressivo ao suspender. Reconecta ao reativar a tela.",
        "benefits": "Evita consumo de bateria com o dispositivo ocioso."
    },
    "wake-timers": {
        "name": "Desativar Temporizadores de Despertar (Wake Timers)",
        "sub": "SUB_SLEEP",
        "setting": "RTCWAKE",
        "eco_value": 0,
        "default_value": 1,
        "risk": "BAIXO",
        "risk_details": "Tarefas agendadas e atualizações não acordam a máquina na bateria.",
        "benefits": "Impede que o computador desperte sozinho fora da tomada."
    },
    "screen-timeout": {
        "name": "Desligamento de Tela Ociosa (5 minutos)",
        "sub": "SUB_VIDEO",
        "setting": "VIDEOIDLE",
        "eco_value": 300,  # 5 minutos (300 segundos)
        "default_value": 600, # 10 minutos
        "risk": "BAIXO",
        "risk_details": "A tela apaga após 5 minutos sem interação de mouse/teclado.",
        "benefits": "Reduz o consumo constante do painel (1.5W a 3.0W)."
    },
    "cool-policy": {
        "name": "Política de Resfriamento Passivo (Ventilador Quieto)",
        "sub": "SUB_PROCESSOR",
        "setting": "SYSCOOLPOLICY",
        "eco_value": 0,  # 0 = Passivo, 1 = Ativo
        "default_value": 1,
        "risk": "MÉDIO/ALTO",
        "risk_details": "Em dispositivos com poeira ou bateria viciada (ex: Amaranth), manter ventilação ativa é mais seguro.",
        "benefits": "Reduz o ruído do ventilador em notebooks novos."
    }
}

def query_current_dc_value(sub: str, setting: str) -> Optional[int]:
    """Obtém o valor DC atual diretamente do powercfg."""
    try:
        cmd = f"powercfg /q SCHEME_CURRENT {sub} {setting}"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            return None
        match = re.search(r"0x([0-9a-fA-F]+)", res.stdout)
        if match:
            return int(match.group(1), 16)
        return None
    except Exception:
        return None

def ensure_baseline_snapshot() -> Dict[str, int]:
    """Salva a linha de base original do sistema se o arquivo ainda não existir."""
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if BASELINE_FILE.exists():
        try:
            return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    baseline = {}
    for strat_id, info in STRATEGIES.items():
        val = query_current_dc_value(info["sub"], info["setting"])
        if val is None and "alt_sub" in info:
            val = query_current_dc_value(info["alt_sub"], info["alt_setting"])
        baseline[strat_id] = val if val is not None else info["default_value"]

    BASELINE_FILE.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
    return baseline

def apply_power_setting(sub: str, setting: str, value: int, alt_sub: str | None = None, alt_setting: str | None = None) -> bool:
    """Aplica uma diretiva no powercfg com tentativa em rota alternativa se necessário."""
    cmd = f"powercfg /setdcvalueindex SCHEME_CURRENT {sub} {setting} {value} && powercfg /setactive SCHEME_CURRENT"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        return True
    
    # Tentativa com GUID alternativo (ex: Modern Standby vs. ACPI Clássico)
    if alt_sub and alt_setting:
        alt_cmd = f"powercfg /setdcvalueindex SCHEME_CURRENT {alt_sub} {alt_setting} {value} && powercfg /setactive SCHEME_CURRENT"
        alt_res = subprocess.run(alt_cmd, shell=True, capture_output=True, text=True)
        return alt_res.returncode == 0

    return False

def get_cpu_telemetry() -> Dict:
    """Coleta métricas de clock, núcleos e throttling térmico da CPU."""
    freq = psutil.cpu_freq()
    load_per_core = psutil.cpu_percent(interval=0.2, percpu=True)
    
    # Leitura do nome da CPU via Registro do Windows
    cpu_name = "Processador Genérico"
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        winreg.CloseKey(key)
    except Exception:
        pass

    return {
        "cpu_name": cpu_name,
        "cores_logical": psutil.cpu_count(logical=True) or 2,
        "cores_physical": psutil.cpu_count(logical=False) or 2,
        "current_mhz": round(freq.current, 1) if freq else 0.0,
        "max_mhz": round(freq.max, 1) if freq and freq.max > 0 else (freq.current if freq else 0.0),
        "load_total": round(sum(load_per_core) / max(1, len(load_per_core)), 1),
        "load_per_core": load_per_core,
    }
