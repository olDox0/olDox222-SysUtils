from __future__ import annotations
import subprocess
import json
from typing import List, Dict

def get_wake_enabled_tasks() -> List[Dict]:
    """Lista tarefas agendadas que podem acordar o sistema (WakeToRun)."""
    ps_cmd = (
        "Get-ScheduledTask | "
        "Where-Object { $_.State -ne 'Disabled' -and $_.Settings.WakeToRun -eq $true } | "
        "Select-Object TaskName, TaskPath, State | "
        "ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=20
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

def get_active_tasks_summary() -> Dict:
    """Sumariza o estado das tarefas agendadas."""
    ps_cmd = (
        "$tasks = Get-ScheduledTask | Where-Object { $_.State -ne 'Disabled' }; "
        "$wake = ($tasks | Where-Object { $_.Settings.WakeToRun -eq $true }); "
        "[PSCustomObject]@{ TotalActive = $tasks.Count; WakeToRunCount = $wake.Count } | "
        "ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=15
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception:
        pass
    return {"TotalActive": 0, "WakeToRunCount": 0}
