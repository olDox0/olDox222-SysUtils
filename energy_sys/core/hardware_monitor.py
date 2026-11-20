# energy_sys/core/hardware_monitor.py
from __future__ import annotations
import threading
from typing import Optional, Dict, List

_computer_instance = None
_init_lock = threading.Lock()
_init_failed = False

def _init_computer():
    global _computer_instance, _init_failed
    if _computer_instance is not None:
        return
    if _init_failed:
        return

    with _init_lock:
        if _computer_instance is not None:
            return
        try:
            from HardwareMonitor.Hardware import Computer
            comp = Computer()
            comp.IsCpuEnabled = True
            comp.IsGpuEnabled = True
            comp.IsBatteryEnabled = True
            comp.IsMotherboardEnabled = False
            comp.IsMemoryEnabled = False
            comp.Open()
            _computer_instance = comp
        except Exception:
            _init_failed = True

def read_power() -> Optional[float]:
    """Lê a potência total do pacote da CPU (CPU Package Power)."""
    global _computer_instance
    if _computer_instance is None:
        _init_computer()
    if _computer_instance is None:
        return None

    try:
        for hardware in _computer_instance.Hardware:
            if str(hardware.HardwareType) == "Cpu":
                hardware.Update() # <-- ESSENCIAL para atualizar os valores
                for sensor in hardware.Sensors:
                    if str(sensor.SensorType) == "Power" and "Package" in sensor.Name:
                        if sensor.Value is not None:
                            return float(sensor.Value)
    except Exception:
        pass
    return None

def read_battery_discharge() -> Optional[float]:
    """Lê a taxa de descarga da bateria (Watts totais do sistema)."""
    global _computer_instance
    if _computer_instance is None:
        _init_computer()
    if _computer_instance is None:
        return None

    try:
        for hardware in _computer_instance.Hardware:
            if str(hardware.HardwareType) == "Battery":
                hardware.Update()
                for sensor in hardware.Sensors:
                    if str(sensor.SensorType) == "Power" and "Discharge Rate" in sensor.Name:
                        if sensor.Value is not None:
                            return float(sensor.Value)
    except Exception:
        pass
    return None

def dump_diagnostic() -> List[Dict]:
    """Retorna todos os hardwares e sensores para o comando de diagnóstico."""
    global _computer_instance
    if _computer_instance is None:
        _init_computer()
    if _computer_instance is None:
        return []

    results = []
    try:
        for hw in _computer_instance.Hardware:
            hw.Update()
            hw_data = {"name": hw.Name, "type": str(hw.HardwareType), "sensors": []}
            for sensor in hw.Sensors:
                hw_data["sensors"].append({
                    "name": sensor.Name,
                    "type": str(sensor.SensorType),
                    "value": sensor.Value
                })
            results.append(hw_data)
    except Exception:
        pass
    return results

def close() -> None:
    global _computer_instance
    if _computer_instance is not None:
        try:
            _computer_instance.Close()
        except Exception:
            pass
        _computer_instance = None
