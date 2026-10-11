# energy_sys/platform/windows/win_power.py
from __future__ import annotations
import ctypes
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict

class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', ctypes.c_byte),
        ('BatteryFlag', ctypes.c_byte),
        ('BatteryLifePercent', ctypes.c_byte),
        ('SystemStatusFlag', ctypes.c_byte),
        ('BatteryLifeTime', ctypes.c_ulong),
        ('BatteryFullLifeTime', ctypes.c_ulong),
    ]

def get_system_power_status() -> Optional[Dict]:
    """Obtém status de energia direto do Kernel do Windows (kernel32.dll)."""
    if os.name != 'nt':
        return None
    sps = SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
        return None

    ac_map = {0: "Bateria (Desconectado)", 1: "Conectado na Tomada (AC)", 255: "Desconhecido"}
    ac_status = ac_map.get(sps.ACLineStatus, "Desconhecido")
    has_battery = sps.BatteryFlag != 128 and sps.BatteryFlag != 255
    charging = bool(sps.BatteryFlag & 8) if has_battery else False

    lifetime_sec = None if sps.BatteryLifeTime == 0xFFFFFFFF else sps.BatteryLifeTime

    return {
        "ac_connected": sps.ACLineStatus == 1,
        "ac_status": ac_status,
        "has_battery": has_battery,
        "charging": charging,
        "percent": sps.BatteryLifePercent if sps.BatteryLifePercent != 255 else None,
        "seconds_remaining": lifetime_sec,
    }

def generate_powercfg_battery_report(output_html: Path) -> bool:
    """Gera o relatório oficial de bateria e degradação do Windows."""
    try:
        cmd = f'powercfg /batteryreport /output "{output_html}"'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.returncode == 0 and output_html.exists()
    except Exception:
        return False
