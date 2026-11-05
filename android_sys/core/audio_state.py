# -*- coding: utf-8 -*-
# android_sys/core/audio_state.py
"""
Osiris / Hera: Gerenciamento de Estado do Áudio (Snapshot, Verify, Rollback, History).

Responsável por:
  1. Snapshot: captura o valor atual de TAKE_AUDIO_FOCUS para cada pacote.
  2. Verify: compara estado atual vs último snapshot, reporta divergências.
  3. Rollback: restaura o snapshot (todos os pacotes).
  4. History: registra operações em JSONL (audit trail append-friendly).

Layout:
  data/audio_state/last_snapshot.json   (último snapshot)
  data/audio_state/history.jsonl         (append-only)
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from android_sys.core import adb_manager, audio_policy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "data" / "audio_state"
SNAPSHOT_FILE = STATE_DIR / "last_snapshot.json"
HISTORY_FILE = STATE_DIR / "history.jsonl"

APPOP_KEY = "TAKE_AUDIO_FOCUS"


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _parse_appop_value(raw: str) -> str:
    """
    Extrai 'allow'/'ignore'/'deny'/'default' de 'TAKE_AUDIO_FOCUS: ignore; time=...'.

    Formato Android 13:
      'TAKE_AUDIO_FOCUS: ignore; time=+1d19h48m ago; rejecttime=+2h17m ago'
    Só o primeiro token após ':' importa.
    """
    raw = (raw or "").strip()
    if ":" in raw:
        value = raw.split(":", 1)[1].strip()
        # Corta em ';' (time=, rejecttime=)
        value = value.split(";")[0].strip()
        return value.lower()
    # Fallback: corta em ';' também (raw sem ':')
    return raw.split(";")[0].strip().lower()


def take_snapshot(
    packages: List[str],
    label: str = "auto",
) -> Tuple[bool, str, Dict]:
    """Captura o estado atual de cada pacote e persiste em disco."""
    device = audio_policy._get_target_device()
    if not device:
        return False, "Nenhum dispositivo conectado.", {}
    if not packages:
        return False, "Nenhum pacote fornecido.", {}

    snapshot: Dict = {
        "timestamp": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "label": label,
        "device": device,
        "packages": {},
    }
    for pkg in packages:
        ok, val = adb_manager.get_appop(device, pkg, APPOP_KEY)
        snapshot["packages"][pkg] = {
            "ok": ok,
            "value": _parse_appop_value(val) if ok else None,
            "raw": (val or "").strip() if ok else None,
        }

    _ensure_state_dir()
    SNAPSHOT_FILE.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return True, f"Snapshot de {len(packages)} pacote(s) salvo.", snapshot


def load_snapshot() -> Optional[Dict]:
    """Carrega o último snapshot do disco (ou None)."""
    if not SNAPSHOT_FILE.exists():
        return None
    try:
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def verify_state(
    expected: Optional[Dict] = None,
) -> Tuple[bool, str, List[Dict]]:
    """
    Compara o estado atual com o snapshot.
    Se `expected` for None, usa o snapshot do disco.
    Retorna (ok, msg, diffs), onde cada diff é:
      {"package": str, "expected": str|None, "actual": str|None, "match": bool}
    """
    if expected is None:
        expected = load_snapshot()
    if not expected:
        return False, "Nenhum snapshot para comparar.", []

    device = audio_policy._get_target_device()
    if not device:
        return False, "Nenhum dispositivo conectado.", []

    diffs: List[Dict] = []
    for pkg, exp in expected.get("packages", {}).items():
        exp_val = exp.get("value")
        ok, curr_raw = adb_manager.get_appop(device, pkg, APPOP_KEY)
        curr_val = _parse_appop_value(curr_raw) if ok else None
        diffs.append({
            "package": pkg,
            "expected": exp_val,
            "actual": curr_val,
            "match": (curr_val == exp_val),
        })

    all_match = all(d["match"] for d in diffs)
    if all_match:
        return True, f"Estado confere com snapshot de {expected.get('iso')}.", diffs
    n_div = sum(1 for d in diffs if not d["match"])
    return False, f"{n_div}/{len(diffs)} pacote(s) divergem do snapshot.", diffs


def rollback_to_snapshot(
    snapshot: Optional[Dict] = None,
) -> Tuple[bool, str, List[str]]:
    """Restaura cada pacote ao valor do snapshot."""
    logs: List[str] = []
    if snapshot is None:
        snapshot = load_snapshot()
    if not snapshot:
        return False, "Nenhum snapshot para reverter.", logs

    device = audio_policy._get_target_device()
    if not device:
        return False, "Nenhum dispositivo conectado.", logs

    logs.append(f"Dispositivo: {device}")
    logs.append(f"Snapshot de: {snapshot.get('iso', '?')} ({snapshot.get('label', '?')})")

    failed: List[str] = []
    for pkg, state in snapshot.get("packages", {}).items():
        target = state.get("value")
        if target is None:
            logs.append(f"  ⚠ {pkg}: sem valor no snapshot, pulando")
            continue
        ok, out = adb_manager.set_appop(device, pkg, APPOP_KEY, target)
        if ok:
            logs.append(f"  ↻ {pkg}: → {target}")
        else:
            failed.append(pkg)
            logs.append(f"  ✘ {pkg}: {out or 'falha'}")

    if failed:
        return False, f"{len(failed)} falharam: {', '.join(failed)}", logs
    return True, f"Revertido para snapshot de {snapshot.get('iso', '?')}.", logs


def log_operation(
    op_type: str,
    packages: List[str],
    mode: str,
    result: str,
    notes: str = "",
) -> None:
    """Append de uma operação no histórico (JSONL)."""
    _ensure_state_dir()
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "epoch": time.time(),
        "op": op_type,
        "packages": list(packages),
        "mode": mode,
        "result": result,
        "notes": notes,
    }
    try:
        with HISTORY_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_history(limit: int = 50) -> List[Dict]:
    """Lê as últimas `limit` operações do histórico."""
    if not HISTORY_FILE.exists():
        return []
    entries: List[Dict] = []
    try:
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return entries[-limit:]
