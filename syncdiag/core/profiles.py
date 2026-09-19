# syncdiag/core/profiles.py
"""
Gerencia perfis de sincronização (origem/destino/opções) persistidos
em data/sync_profiles.json — mesma pasta 'data/' já usada pelo SysUtils
para banco de dados e índices (ver install.py / phase_2_topology).
"""
import json
from pathlib import Path
from typing import Optional, List, Dict

PROFILES_PATH = Path("data") / "sync_profiles.json"


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
    excludes: Optional[List[str]] = None,
) -> None:
    data = _load_raw()
    data[name] = {
        "origem": origem,
        "destino": destino,
        "threads": threads,
        "excludes": excludes or [],
    }
    _save_raw(data)


def remove_profile(name: str) -> bool:
    data = _load_raw()
    if name not in data:
        return False
    del data[name]
    _save_raw(data)
    return True
