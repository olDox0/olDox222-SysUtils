# -*- coding: utf-8 -*-
# android_sys/core/audio_monitor.py
"""
Horus: Monitor de Eventos de Foco de Áudio (AudioMonitor).

Polling de 'adb shell dumpsys audio' em intervalo configurável,
detectando transições GAIN <-> LOSS <-> DUCK e imprimindo no terminal.

Uso previsto:
  sysutils android audio monitor --interval 1.0 --duration 60
"""
from __future__ import annotations
import time
from typing import Callable, Dict, List, Optional

from android_sys.core import audio_policy


def snapshot_focus_state() -> Dict:
    """
    Captura o estado atual do foco de áudio via dumpsys.
    Devolve dict com chave 'focus_stack' (lista) e 'timestamp'.
    """
    holders = audio_policy.list_active_focus_holders()
    return {"focus_stack": holders, "timestamp": time.time()}


def _index_by_package(stack: List[Dict]) -> Dict[str, Dict]:
    """Indexa a pilha por nome de pacote (último vence)."""
    idx: Dict[str, Dict] = {}
    for h in stack:
        pkg = h.get("package")
        if pkg:
            idx[pkg] = h
    return idx


def diff_focus_states(
    prev: Dict,
    curr: Dict,
) -> List[Dict]:
    """
    Compara dois snapshots e devolve eventos de transição:
      [{"event": "GAIN"|"LOSS"|"DUCK", "package": str, "at": float}, ...]

    Regras:
      - Pacote que estava antes e não está agora -> LOSS
      - Pacote que não estava antes e está agora -> GAIN
      - Pacote presente nos dois, mas gain mudou -> DUCK (ou GAIN se subiu)
    """
    prev_idx = _index_by_package(prev.get("focus_stack", []))
    curr_idx = _index_by_package(curr.get("focus_stack", []))
    now = curr.get("timestamp", time.time())
    events: List[Dict] = []

    for pkg in prev_idx:
        if pkg not in curr_idx:
            events.append({"event": "LOSS", "package": pkg, "at": now,
                           "from_gain": prev_idx[pkg].get("gain")})

    for pkg in curr_idx:
        if pkg not in prev_idx:
            events.append({"event": "GAIN", "package": pkg, "at": now,
                           "gain": curr_idx[pkg].get("gain")})
        else:
            old_gain = prev_idx[pkg].get("gain")
            new_gain = curr_idx[pkg].get("gain")
            if old_gain and new_gain and old_gain != new_gain:
                # Se o gain baixou para DUCK/TRANSIENT_MAY_DUCK -> DUCK
                if "DUCK" in (new_gain or ""):
                    events.append({"event": "DUCK", "package": pkg, "at": now,
                                   "from_gain": old_gain, "gain": new_gain})
                else:
                    events.append({"event": "GAIN", "package": pkg, "at": now,
                                   "from_gain": old_gain, "gain": new_gain})

    return events


def monitor_focus(
    interval: float = 1.0,
    duration: float = 60.0,
    on_event: Optional[Callable[[Dict], None]] = None,
) -> List[Dict]:
    """
    Loop de monitoramento por 'duration' segundos.
    Se on_event for fornecido, chama-o a cada transição detectada.
    Retorna a lista completa de eventos capturados.
    """
    events: List[Dict] = []
    prev = snapshot_focus_state()
    start = time.time()

    # Se o on_event for None, usa um print simples
    emit = on_event or (lambda e: print(format_event(e)))

    while time.time() - start < duration:
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            break
        curr = snapshot_focus_state()
        new_events = diff_focus_states(prev, curr)
        for e in new_events:
            events.append(e)
            emit(e)
        prev = curr

    return events


def format_event(event: Dict) -> str:
    """Formata um evento para exibição no terminal (com cor opcional)."""
    kind = event.get("event", "?")
    pkg = event.get("package", "?")
    ts = time.strftime("%H:%M:%S", time.localtime(event.get("at", time.time())))

    icon = {"GAIN": "▲", "LOSS": "▼", "DUCK": "≈"}.get(kind, "•")
    color = {"GAIN": "\033[92m", "LOSS": "\033[91m", "DUCK": "\033[93m"}.get(kind, "\033[0m")
    reset = "\033[0m"

    detail = ""
    if kind == "GAIN" and event.get("gain"):
        detail = f"  [{event['gain']}]"
    elif kind == "LOSS" and event.get("from_gain"):
        detail = f"  (era {event['from_gain']})"
    elif kind == "DUCK":
        detail = f"  {event.get('from_gain')} → {event.get('gain')}"

    return f"{color}{icon} [{ts}] {kind:<5} {pkg}{detail}{reset}"
