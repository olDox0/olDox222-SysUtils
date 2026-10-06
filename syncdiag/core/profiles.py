# syncdiag/core/profiles.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, List, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILES_PATH = PROJECT_ROOT / "data" / "sync_profiles.json"

def _load_raw() -> Dict:
    if not PROFILES_PATH.exists():
        return {}
    try:
        return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_raw(data: Dict) -> None:
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

def list_profiles() -> Dict:
    return _load_raw()

def get_profile(name: str) -> Optional[Dict]:
    return _load_raw().get(name)

def add_profile(
    name: str,
    origem: str,
    destino: str,
    threads: int = 16,
    excludes_dir: Optional[List[str]] = None,
    excludes_file: Optional[List[str]] = None,
) -> None:
    data = _load_raw()
    data[name] = {
        "origem": origem,
        "destino": destino,
        "threads": threads,
        "excludes_dir": excludes_dir or [],
        "excludes_file": excludes_file or [],
    }
    _save_raw(data)

def remove_profile(name: str) -> bool:
    data = _load_raw()
    if name not in data:
        return False
    del data[name]
    _save_raw(data)
    return True
