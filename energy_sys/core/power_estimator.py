# energy_sys/core/power_estimator.py
from __future__ import annotations
import os
import psutil
from typing import Dict
from energy_sys.platform.windows.win_power import get_system_power_status
from energy_sys.core.battery_telemetry import get_wmi_battery_telemetry

def detect_cpu_profile() -> Dict:
    """Identifica o perfil térmico com base no processador instalado."""
    cpu_count = psutil.cpu_count(logical=True) or 2
    
    # Detecção se é Bay Trail / Atom / Celeron de baixo consumo
    is_baytrail_or_celeron = True  # Padrão do Amaranth
    
    sys_status = get_system_power_status()
    is_laptop = sys_status and sys_status.get("has_battery")

    if is_laptop:
        # Celeron N2808 / Bay Trail: TDP 4.5W + ~3W de placa e tela
        base_idle_watts = 5.0
        max_cpu_watts = 6.0
    else:
        # Desktop ou máquinas de alto desempenho (ex: Bluebaby)
        base_idle_watts = 25.0
        max_cpu_watts = 45.0

    return {
        "is_laptop": is_laptop,
        "base_idle_watts": base_idle_watts,
        "max_cpu_watts": max_cpu_watts,
        "cores": cpu_count,
    }

def estimate_instant_watts() -> Dict:
    """Calcula o consumo elétrico instantâneo em Watts."""
    # 1. Se houver sensor ACPI ativo descarregando bateria, prioriza o valor real do hardware
    wmi_data = get_wmi_battery_telemetry()
    if wmi_data and wmi_data.get("is_discharging") and wmi_data.get("watts_discharging", 0) > 0:
        return {
            "method": "Sensor Físico ACPI (Descarga Real)",
            "watts": wmi_data["watts_discharging"],
            "accuracy": "ALTA (Hardware)",
            "details": wmi_data
        }

    # 2. Heurística dinâmica por carga de CPU e disco
    cpu_percent = psutil.cpu_percent(interval=0.4)
    profile = detect_cpu_profile()
    
    # Modelo dinâmico: Consumo = Repouso + (TDP_Max * %CPU)
    cpu_dynamic_watts = profile["max_cpu_watts"] * (cpu_percent / 100.0)
    estimated_total = profile["base_idle_watts"] + cpu_dynamic_watts
    
    return {
        "method": "Estimativa Dinâmica de Carga / TDP",
        "watts": round(estimated_total, 2),
        "accuracy": "MÉDIA (Heurística)",
        "cpu_load_percent": cpu_percent,
        "profile": profile
    }
