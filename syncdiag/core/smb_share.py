# syncdiag/core/smb_share.py
import ctypes
import subprocess
from typing import Optional, List, Dict

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def create_share(name: str, path: str, user: Optional[str] = None) -> Dict:
    # No Windows PT-BR o grupo universal chama-se 'Todos', no EN-US é 'Everyone'
    grant_candidates = [user] if user else ["Everyone", "Todos"]

    proc = None
    success = False
    for grant_target in grant_candidates:
        cmd = f'net share {name}="{path}" /GRANT:{grant_target},FULL'
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode == 0:
            success = True
            break

    # Fallback via PowerShell se o net share recusar mapeamento de SID
    if not success:
        ps_cmd = f'New-SmbShare -Name "{name}" -Path "{path}" -FullAccess "Everyone","Todos" -ErrorAction SilentlyContinue'
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        success = (proc.returncode == 0)

    return {
        "success": success,
        "stdout": proc.stdout.strip() if proc else "",
        "stderr": proc.stderr.strip() if proc else "",
        "cmd": f'net share {name}="{path}"',
    }

def remove_share(name: str) -> Dict:
    cmd = f'net share {name} /DELETE /YES'
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {
        "success": proc.returncode == 0,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }

def list_shares() -> List[Dict]:
    proc = subprocess.run(["net", "share"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    shares = []
    started = False
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("---"):
            started = True
            continue
        if not started or not stripped:
            continue
        low = stripped.lower()
        if low.startswith("o comando") or low.startswith("the command"):
            break
        parts = stripped.split(None, 2)
        if parts:
            shares.append({
                "name": parts[0],
                "path": parts[1] if len(parts) > 1 else "",
                "remark": parts[2] if len(parts) > 2 else "",
            })
    return shares
