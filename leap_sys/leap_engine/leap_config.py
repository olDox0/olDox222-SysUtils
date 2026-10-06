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
    }
    dir_server_to_client, dir_client_to_server = dir_map.get(position, ("right", "left"))

    # Configuração com Aliases: aceita 'bluebaby' e 'DESKTOP-5NP5BHE' para a mesma tela
    conf = f"""# ==============================================================================
# LEAP SYS CONFIGURATION FILE (Aliases Nativos)
# ==============================================================================

section: screens
\t{server_name}:
\tbluebaby:
end

section: aliases
\tbluebaby:
\t\tDESKTOP-5NP5BHE
end

section: links
\t{server_name}:
\t\t{dir_server_to_client} = bluebaby
\tbluebaby:
\t\t{dir_client_to_server} = {server_name}
end

section: options
\theartbeat = 5000
\trelativeMouseMoves = false
\tscreenSaverSync = true
\twin32KeepForeground = false
\tclipboardSharing = true
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
