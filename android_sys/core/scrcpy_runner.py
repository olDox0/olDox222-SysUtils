# android_sys/core/scrcpy_runner.py
from __future__ import annotations
import subprocess
import os
from android_sys.core.installer import get_binary_paths

def start_scrcpy(
    device_ip: str,
    mode: str = "mirror",
    max_fps: int = 60,
    max_size: int = 1024,
    forward_audio: bool = False  # <-- ÁUDIO PERMANECE NO CELULAR POR PADRÃO
) -> subprocess.Popen:
    scrcpy_bin = get_binary_paths()["scrcpy"]
    adb_bin = get_binary_paths()["adb"]

    env = os.environ.copy()
    env["ADB"] = str(adb_bin)

    cmd = [str(scrcpy_bin), "--tcpip=" + device_ip]

    if mode == "otg":
        cmd.extend(["--otg", "--no-video", "--no-audio"])
    else:
        cmd.extend([
            f"--max-fps={max_fps}",
            f"--max-size={max_size}",
            "--stay-awake",
        ])
        
        # Mantém o som tocando no próprio alto-falante do celular
        if not forward_audio:
            cmd.append("--no-audio")

    return subprocess.Popen(cmd, env=env)
