# energy_sys/core/program_analyzer.py
from __future__ import annotations
import subprocess
import psutil
import json
import winreg
from pathlib import Path
from typing import List, Dict, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKUP_FILE = PROJECT_ROOT / "data" / "startup_backup.json"

def get_startup_programs() -> List[Dict]:
    """Lista programas de inicialização com localização e comando (WMI)."""
    ps_cmd = (
        "Get-CimInstance Win32_StartupCommand | "
        "Select-Object Name, Command, Location, User | "
        "ConvertTo-Json -Compress"
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], 
                             capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if not res.stdout.strip():
            return []
        data = json.loads(res.stdout)
        return [data] if isinstance(data, dict) else data
    except Exception:
        return []

def disable_startup_item(name: str) -> Tuple[bool, str]:
    """Remove um item da inicialização via Registro do Windows (com backup)."""
    # Caminhos comuns de inicialização (HKCU não exige Admin, HKLM exige)
    paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ]
    
    # 1. Faz backup antes de alterar
    current_items = get_startup_programs()
    BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        BACKUP_FILE.write_text(json.dumps(current_items, indent=2), encoding="utf-8")
    except Exception:
        pass # Se falhar o backup, continua (mas avisa no log)

    for hkey, subkey in paths:
        try:
            # Tenta abrir a chave com permissão de leitura/escrita
            key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_ALL_ACCESS)
            try:
                winreg.QueryValueEx(key, name) # Verifica se existe
                winreg.DeleteValue(key, name)  # Deleta
                winreg.CloseKey(key)
                return True, f"Desativado com sucesso: {name}"
            except FileNotFoundError:
                winreg.CloseKey(key)
                continue # Não está nessa chave, tenta a próxima
        except PermissionError:
            return False, f"Acesso negado para modificar {name}. Rode como Administrador."
        except Exception as e:
            continue
            
    return False, f"Item '{name}' não encontrado nas chaves de inicialização."

def get_zombie_processes() -> List[Dict]:
    """Procura processos em TODOS os usuários (útil para achar o Spotify de outro perfil)."""
    zombies = []
    targets = ["spotify.exe", "barrierc.exe", "barriers.exe", "deskflow.exe", "deskflow-core.exe"]
    
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent']):
        try:
            name = (proc.info['name'] or '').lower()
            if name in targets:
                zombies.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "user": proc.info['username'] or "SYSTEM",
                    "cpu": proc.info['cpu_percent']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return zombies

def kill_process_by_pid(pid: int) -> bool:
    """Mata um processo específico pelo PID."""
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False
