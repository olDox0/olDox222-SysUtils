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
    """
    Gera o texto de configuração com links bidirecionais entre Server e Client.
    """
    # Mapeamento bidirecional da transição de bordas
    dir_map = {
        "right": ("right", "left"),
        "left":  ("left", "right"),
        "above": ("up", "down"),
        "below": ("down", "up")
    }
    dir_server_to_client, dir_client_to_server = dir_map.get(position, ("right", "left"))

    conf = f"""# ==============================================================================
# LEAP SYS CONFIGURATION FILE (Gerado automaticamente pelo SysUtils)
# ==============================================================================

section: screens
\t{server_name}:
\t\thalfDuplexCapsLock = false
\t\thalfDuplexNumLock = false
\t\thalfDuplexScrollLock = false
\t\txtestIsXineramaUnaware = false
\t\tswitchCorners = none
\t\tswitchCornerSize = 0
\t{client_name}:
\t\thalfDuplexCapsLock = false
\t\thalfDuplexNumLock = false
\t\thalfDuplexScrollLock = false
\t\txtestIsXineramaUnaware = false
\t\tswitchCorners = none
\t\tswitchCornerSize = 0
end

section: links
\t{server_name}:
\t\t{dir_server_to_client} = {client_name}
\t{client_name}:
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
