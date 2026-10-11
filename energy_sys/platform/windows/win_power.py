# energy_sys/platform/windows/win_power.py
from __future__ import annotations
import ctypes
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, List

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

# Matriz Declarativa de Otimizações de Energia
ECO_TWEAKS = [
    {
        "id": "cpu_cap",
        "title": "Teto de Frequência da CPU (80% na Bateria)",
        "cmd": "powercfg /setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMAX 80",
        "why": "Impede que o processador dê picos de Turbo Boost agressivos de 25W+ ao abrir janelas.",
        "scope": "Apenas na BATERIA (DC). Na tomada (AC), a CPU opera normalmente a 100%.",
        "safe_reason": "Totalmente reversível. Não afeta digitação ou tarefas de código leve."
    },
    {
        "id": "standby_network",
        "title": "Desconectar Wi-Fi durante o Sono (Anti-Modern Standby Drain)",
        "cmd": "powercfg /setdcvalueindex SCHEME_CURRENT SUB_NONE 0e796bdb-100d-47d6-a2e5-f7d2daa51f51 0",
        "why": "No Windows 11, o notebook mantém a Wi-Fi acordada mesmo com a tampa fechada, drenando bateria.",
        "scope": "Apenas na BATERIA (DC). Ao abrir o notebook, a Wi-Fi reconecta instantaneamente.",
        "safe_reason": "Elimina o dreno silencioso na mochila ou fora da tomada."
    },
    {
        "id": "wake_timers",
        "title": "Desativar Temporizadores de Despertar (Wake Timers)",
        "cmd": "powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 0",
        "why": "Impede que tarefas agendadas do Windows ou manutenções acordem o computador na bateria.",
        "scope": "Apenas na BATERIA (DC).",
        "safe_reason": "Garante que o sono do notebook seja 100% respeitado."
    },
    {
        "id": "display_idle",
        "title": "Desligamento da Tela Ociosa (3 minutos)",
        "cmd": "powercfg /setdcvalueindex SCHEME_CURRENT SUB_VIDEO VIDEOIDLE 180",
        "why": "A tela consome de 1.5W a 3.0W. Apagar após 3 min sem uso poupa energia considerável.",
        "scope": "Apenas na BATERIA (DC).",
        "safe_reason": "Qualquer toque no teclado ou mouse reacende a tela sem perder nada."
    },
    {
        "id": "cooling_policy",
        "title": "Política de Resfriamento Passivo (Ventilador Quieto)",
        "cmd": "powercfg /setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR SYSCOOLPOLICY 0",
        "why": "Desacelera a CPU levemente antes de ligar a ventoinha na bateria, economizando motor elétrico.",
        "scope": "Apenas na BATERIA (DC).",
        "safe_reason": "Reduz o barulho do cooler e poupa energia mecânica da ventoinha."
    }
]

def apply_eco_profile() -> List[str]:
    """Aplica de fato as otimizações no Windows."""
    logs = []
    for tweak in ECO_TWEAKS:
        try:
            res = subprocess.run(tweak["cmd"], shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                logs.append(f"[OK] {tweak['title']}")
            else:
                logs.append(f"[IGNORADO] {tweak['title']} (BIOS/Windows não suporta este índice)")
        except Exception as e:
            logs.append(f"[FALHA] {tweak['title']}: {e}")

    # Revalida e aplica no perfil ativo
    subprocess.run("powercfg /setactive SCHEME_CURRENT", shell=True, capture_output=True)
    return logs

def restore_balanced_profile() -> List[str]:
    """Restaura as configurações de fábrica do Windows."""
    cmd = "powercfg /restoredefaultschemes"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        return ["[OK] Esquemas de energia padrão do Windows restaurados com sucesso."]
    return ["[FALHA] Falha ao restaurar esquemas de energia."]
