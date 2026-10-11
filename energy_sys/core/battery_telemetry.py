# energy_sys/core/battery_telemetry.py
from __future__ import annotations
import subprocess
import json
from typing import Optional, Dict

def get_wmi_battery_telemetry() -> Optional[Dict]:
    """Consulta os sensores WMI para medir mW, mV e mWh em tempo real."""
    ps_cmd = """
    $status = Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue | Select-Object -First 1
    $static = Get-CimInstance -Namespace root/wmi -ClassName BatteryStaticData -ErrorAction SilentlyContinue | Select-Object -First 1
    
    if ($status) {
        [PSCustomObject]@{
            DischargeRate     = $status.DischargeRate
            ChargeRate        = $status.ChargeRate
            Voltage           = $status.Voltage
            RemainingCapacity = $status.RemainingCapacity
            DesignedCapacity  = if ($static) { $static.DesignedCapacity } else { $null }
            Charging          = $status.Charging
            Discharging       = $status.Discharging
            PowerOnline       = $status.PowerOnline
        } | ConvertTo-Json
    }
    """
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        data = json.loads(proc.stdout)
        
        # Converte taxa de descarga para Watts
        voltage_v = (data.get("Voltage") or 0) / 1000.0
        discharge_raw = data.get("DischargeRate") or 0
        charge_raw = data.get("ChargeRate") or 0
        
        # No padrão ACPI, DischargeRate pode ser mWh ou mA
        # Se for mW: taxa / 1000 = W
        # Se for mA: (taxa * Volts) / 1000000 = W
        watts_discharging = round(discharge_raw / 1000.0, 2) if discharge_raw > 0 else 0.0
        watts_charging = round(charge_raw / 1000.0, 2) if charge_raw > 0 else 0.0

        return {
            "has_sensor": True,
            "watts_discharging": watts_discharging,
            "watts_charging": watts_charging,
            "voltage_v": round(voltage_v, 2),
            "remaining_mwh": data.get("RemainingCapacity"),
            "designed_mwh": data.get("DesignedCapacity"),
            "is_discharging": data.get("Discharging", False),
            "is_charging": data.get("Charging", False),
        }
    except Exception:
        return None
