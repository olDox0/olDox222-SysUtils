# energy_sys/core/power_strategies.py
from __future__ import annotations
import json
import re
import subprocess
import psutil
import ctypes
import os
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASELINE_FILE = PROJECT_ROOT / "data" / "power_baseline.json"

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
        "sub": "19cbb8fa-5279-450e-9f18-0a6727fbba81",
        "setting": "12bbe462-763e-4272-97f7-da30076dbd16",
        "eco_value": 3,
        "default_value": 0,
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
        "eco_value": 300,
        "default_value": 600,
        "risk": "BAIXO",
        "risk_details": "A tela apaga após 5 minutos sem interação de mouse/teclado.",
        "benefits": "Reduz o consumo constante do painel (1.5W a 3.0W)."
    },
    "cool-policy": {
        "name": "Política de Resfriamento Passivo (Ventilador Quieto)",
        "sub": "SUB_PROCESSOR",
        "setting": "SYSCOOLPOLICY",
        "eco_value": 0,
        "default_value": 1,
        "risk": "MÉDIO/ALTO",
        "risk_details": "Em dispositivos com poeira ou bateria viciada (ex: Amaranth), manter ventilação ativa é mais seguro.",
        "benefits": "Reduz o ruído do ventilador em notebooks novos."
    }
}

def query_current_dc_value(sub: str, setting: str) -> Optional[int]:
    """Obtém o valor DC real atual do powercfg, compatível com PT-BR e EN."""
    try:
        cmd = f"powercfg /q SCHEME_CURRENT {sub} {setting}"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            return None
        
        match = re.search(r"(?:DC.*?:\s*|Energia DC.*?:\s*)0x([0-9a-fA-F]+)", res.stdout, re.IGNORECASE)
        if match:
            return int(match.group(1), 16)
        
        all_hex = re.findall(r"0x([0-9a-fA-F]+)", res.stdout)
        if all_hex:
            return int(all_hex[-1], 16)
        return None
    except Exception:
        return None

def unlock_wifi_power_setting() -> None:
    """Desbloqueia no registro do Windows a chave oculta de energia do Wi-Fi."""
    try:
        reg_cmd = (
            r'reg add "HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerSettings'
            r'\19cbb8fa-5279-450e-9f18-0a6727fbba81\12bbe462-763e-4272-97f7-da30076dbd16" '
            r'/v Attributes /t REG_DWORD /d 2 /f'
        )
        subprocess.run(reg_cmd, shell=True, capture_output=True)
    except Exception:
        pass

def ensure_baseline_snapshot() -> Dict[str, int]:
    """Grava a linha de base original do sistema uma única vez."""
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if BASELINE_FILE.exists():
        try:
            return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    baseline = {}
    for strat_id, info in STRATEGIES.items():
        val = query_current_dc_value(info["sub"], info["setting"])
        baseline[strat_id] = val if val is not None else info["default_value"]

    BASELINE_FILE.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
    return baseline

def apply_power_setting(sub: str, setting: str, value: int) -> bool:
    """Aplica o valor de energia na bateria (DC)."""
    if "12bbe462" in setting:
        unlock_wifi_power_setting()

    cmd = f"powercfg /setdcvalueindex SCHEME_CURRENT {sub} {setting} {value} && powercfg /setactive SCHEME_CURRENT"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode == 0

def get_hybrid_cpu_topology(total_threads: int) -> Dict[int, str]:
    """
    Identifica P-Cores e E-Cores pela EfficiencyClass do Windows.

    Valores maiores de EfficiencyClass indicam maior desempenho intrínseco.
    A classe máxima é tratada como P-Core e a mínima como E-Core. Se a
    topologia não puder ser mapeada integralmente, retorna rótulos neutros.
    """
    default_map = {i: "Núcleo Padrão" for i in range(total_threads)}
    if os.name != "nt" or total_threads <= 0:
        return default_map

    try:
        kernel32 = ctypes.windll.kernel32
        get_info = kernel32.GetLogicalProcessorInformationEx

        buf_len = ctypes.c_ulong(0)
        get_info(0, None, ctypes.byref(buf_len))
        if buf_len.value == 0:
            return default_map

        buffer = ctypes.create_string_buffer(buf_len.value)
        if not get_info(0, buffer, ctypes.byref(buf_len)):
            return default_map

        raw_bytes = buffer.raw[:buf_len.value]
        pointer_size = ctypes.sizeof(ctypes.c_void_p)
        group_mask_size = pointer_size + 8
        offset = 0
        logical_classes: Dict[int, int] = {}

        while offset + 8 <= len(raw_bytes):
            relationship = int.from_bytes(raw_bytes[offset:offset + 4], "little")
            structure_size = int.from_bytes(raw_bytes[offset + 4:offset + 8], "little")
            if structure_size < 8 or offset + structure_size > len(raw_bytes):
                return default_map

            if relationship == 0:  # RelationProcessorCore
                if structure_size < 32:
                    return default_map

                efficiency_class = raw_bytes[offset + 9]
                group_count = int.from_bytes(raw_bytes[offset + 30:offset + 32], "little")
                required_size = 32 + (group_count * group_mask_size)
                if group_count < 1 or required_size > structure_size:
                    return default_map

                for group_index in range(group_count):
                    group_offset = offset + 32 + (group_index * group_mask_size)
                    mask = int.from_bytes(
                        raw_bytes[group_offset:group_offset + pointer_size],
                        "little",
                    )
                    group_id = int.from_bytes(
                        raw_bytes[group_offset + pointer_size:group_offset + pointer_size + 2],
                        "little",
                    )

                    # psutil expõe índices lógicos lineares. Até existir uma
                    # conversão confiável de processor groups, falhamos seguro.
                    if group_id != 0:
                        return default_map

                    bit = 0
                    while mask:
                        if mask & 1:
                            logical_classes[bit] = efficiency_class
                        mask >>= 1
                        bit += 1

            offset += structure_size

        if set(logical_classes) != set(range(total_threads)):
            return default_map

        classes = set(logical_classes.values())
        if len(classes) < 2:
            return default_map

        performance_class = max(classes)
        return {
            index: (
                "P-Core (Performance)"
                if efficiency_class == performance_class
                else "E-Core (Eficiência)"
            )
            for index, efficiency_class in logical_classes.items()
        }
    except Exception:
        return default_map

def get_cpu_telemetry() -> Dict:
    """Coleta métricas com distinção de arquitetura híbrida e clock."""
    freq = psutil.cpu_freq()
    load_per_core = psutil.cpu_percent(interval=0.3, percpu=True)
    total_threads = len(load_per_core)
    
    cpu_name = "Processador Genérico"
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        winreg.CloseKey(key)
    except Exception:
        pass

    # Chamada corrigida: get_hybrid_cpu_topology
    topology_map = get_hybrid_cpu_topology(total_threads)
    is_hybrid = any("P-Core" in v for v in topology_map.values())

    return {
        "cpu_name": cpu_name,
        "is_hybrid": is_hybrid,
        "cores_logical": total_threads,
        "cores_physical": psutil.cpu_count(logical=False) or total_threads,
        "current_mhz": round(freq.current, 1) if freq else 0.0,
        "max_mhz": round(freq.max, 1) if freq and freq.max > 0 else (freq.current if freq else 0.0),
        "load_total": round(sum(load_per_core) / max(1, total_threads), 1),
        "load_per_core": load_per_core,
        "core_labels": topology_map,
    }
