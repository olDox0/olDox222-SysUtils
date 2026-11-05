# sysutils/leap_sys/leap_engine/leap_config.py
"""
Hera: Gerador de configuração declarativa para o input-leaps.exe.
Suporta topologia de telas: right, left, above (up), below (down).
"""
from __future__ import annotations
from pathlib import Path

def generate_conf_content(
    server_name: str,
    client_name: str,
    position: str = "right"
) -> str:
    dir_map = {
        "right": ("right", "left"),
        "left":  ("left", "right"),
        "above": ("up", "down"),
        "below": ("down", "up")
    }def generate_conf_content(
    server_name: str,
    client_name: str,
    position: str = "right",
    on_battery: bool = False
) -> str:
    dir_map = {
        "right": ("right", "left"),
        "left":  ("left", "right"),
        "above": ("up", "down"),
        "below": ("down", "up")
    }
    dir_server_to_client, dir_client_to_server = dir_map.get(position, ("right", "left"))
    
    # Otimização: Se estiver na bateria, aumenta o heartbeat para 15s (menos pacotes de rede)
    # e desliga o clipboard sharing para economizar CPU.
    heartbeat = "15000" if on_battery else "5000"
    clipboard = "false" if on_battery else "true"
    
    conf = f"""
section: screens
\t{server_name}:
\t{client_name}:
end
section: aliases
\t{client_name}:
\t\tDESKTOP-5NP5BHE
end
section: links
\t{server_name}:
\t\t{dir_server_to_client} = {client_name}
\t{client_name}:
\t\t{dir_client_to_server} = {server_name}
end
section: options
\theartbeat = {heartbeat}
\trelativeMouseMoves = false
\tscreenSaverSync = true
\twin32KeepForeground = false
\tclipboardSharing = {clipboard}
\tswitchDelay = 250
end
"""
    return conf

def write_runtime_config(
    conf_dir: Path,
    server_name: str,
    client_name: str,
    position: str = "right"
) -> Path:
    conf_dir.mkdir(parents=True, exist_ok=True)
    target_path = conf_dir / "leap_runtime.conf"
    content = generate_conf_content(server_name, client_name, position)
    target_path.write_text(content, encoding="utf-8")
    return target_path
