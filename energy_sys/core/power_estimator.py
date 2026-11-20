# energy_sys/core/power_estimator.py
from __future__ import annotations
import psutil
from typing import Dict
from energy_sys.platform.windows.win_power import get_system_power_status
from energy_sys.core.battery_telemetry import get_wmi_battery_telemetry
from energy_sys.core import hardware_monitor

def detect_cpu_profile() -> Dict:
    cpu_count = psutil.cpu_count(logical=True) or 2
    sys_status = get_system_power_status()
    is_laptop = sys_status and sys_status.get("has_battery")
    
    if is_laptop:
        base_idle_watts = 5.0
        max_cpu_watts = 6.0
    else:
        base_idle_watts = 25.0
        max_cpu_watts = 45.0
    return {
        "is_laptop": is_laptop,
        "base_idle_watts": base_idle_watts,
        "max_cpu_watts": max_cpu_watts,
        "cores": cpu_count,
    }

def estimate_instant_watts() -> Dict:
    # 1. Tenta Bateria (Melhor para consumo TOTAL do sistema)
    batt_watts = hardware_monitor.read_battery_discharge()
    if batt_watts is not None and batt_watts > 0:
        return {
            "method": "Hardware Real (Descarga da Bateria)",
            "watts": round(batt_watts, 2),
            "accuracy": "ALTA (Hardware)",
            "details": {"source": "battery"}
        }

    # 2. Tenta CPU RAPL (Excelente para consumo do Processador)
    cpu_watts = hardware_monitor.read_power()
    if cpu_watts is not None and cpu_watts > 0:
        # Como é só a CPU, adicionamos uma estimativa base para o resto (tela, etc)
        # Se estiver na tomada, a estimativa base é um pouco maior.
        sys_status = get_system_power_status()
        base_system = 5.0 if sys_status and not sys_status.get("ac_connected") else 8.0
        total_watts = cpu_watts + base_system
        
        return {
            "method": "Hardware Real (CPU RAPL + Base)",
            "watts": round(total_watts, 2),
            "accuracy": "ALTA (Hardware CPU)",
            "details": {"source": "cpu_rapl", "cpu_watts": cpu_watts, "base_watts": base_system}
        }

    # 3. Fallback WMI (Estimativa ACPI antiga)
    wmi_data = get_wmi_battery_telemetry()
    if wmi_data and wmi_data.get("is_discharging") and wmi_data.get("watts_discharging", 0) > 0:
        return {
            "method": "Sensor WMI/ACPI (Descarga Estimada)",
            "watts": wmi_data["watts_discharging"],
            "accuracy": "MÉDIA (Heurística)",
            "details": wmi_data
        }
        
    # 4. Fallback Final (psutil Heurística)
    cpu_percent = psutil.cpu_percent(interval=0.4)
    profile = detect_cpu_profile()
    cpu_dynamic_watts = profile["max_cpu_watts"] * (cpu_percent / 100.0)
    estimated_total = profile["base_idle_watts"] + cpu_dynamic_watts
    return {
        "method": "Estimativa Dinâmica (TDP psutil)",
        "watts": round(estimated_total, 2),
        "accuracy": "BAIXA (Heurística)",
        "cpu_load_percent": cpu_percent,
        "profile": profile
    }
