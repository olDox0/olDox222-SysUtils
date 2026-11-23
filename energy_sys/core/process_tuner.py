# energy_sys/core/process_tuner.py
from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import psutil

from energy_sys.core import power_strategies

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = PROJECT_ROOT / "data" / "energy_reports"
STATE_FILE = REPORT_DIR / "process_affinity_state.json"
HISTORY_FILE = REPORT_DIR / "process_affinity_history.jsonl"


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_state() -> dict[str, dict[str, Any]]:
    if not STATE_FILE.exists():
        return {}
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Não foi possível ler o estado de afinidade: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise RuntimeError("Formato do arquivo de estado de afinidade desconhecido.")
    processes = payload.get("processes")
    if not isinstance(processes, dict):
        raise RuntimeError("O campo 'processes' do estado de afinidade é inválido.")
    return processes


def _save_state(processes: dict[str, dict[str, Any]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "updated_at": _timestamp(), "processes": processes}
    temporary = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(STATE_FILE)


def _record_event(**fields: Any) -> str | None:
    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        with HISTORY_FILE.open("a", encoding="utf-8", newline="\n") as history:
            history.write(json.dumps(
                {"timestamp": _timestamp(), **fields},
                ensure_ascii=False,
            ) + "\n")
            history.flush()
    except OSError as exc:
        return f"O histórico não pôde ser gravado: {exc}"
    return None


def _same_process(record: dict[str, Any], create_time: float) -> bool:
    try:
        return abs(float(record["create_time"]) - create_time) <= 0.001
    except (KeyError, TypeError, ValueError):
        return False


def _process_identity(process: psutil.Process) -> tuple[str, float]:
    return process.name(), round(process.create_time(), 6)


def get_core_indices(core_type: str = "e-cores") -> List[int]:
    """Retorna índices lógicos P/E; não adivinha topologias desconhecidas."""
    if core_type not in {"e-cores", "p-cores"}:
        return []

    total_threads = psutil.cpu_count(logical=True) or 0
    if total_threads <= 0:
        return []
    topology = power_strategies.get_hybrid_cpu_topology(total_threads)
    wanted = "E-Core" if core_type == "e-cores" else "P-Core"
    return sorted(
        index for index, label in topology.items()
        if isinstance(index, int)
        and 0 <= index < total_threads
        and wanted in label
    )


def apply_process_affinity(
    pid: int,
    mode: str,
) -> Tuple[bool, str, Dict[str, Any] | None]:
    """Aplica eco/perf a um PID específico e preserva a afinidade original."""
    mode_to_core = {"eco": "e-cores", "perf": "p-cores"}
    if mode not in mode_to_core:
        return False, f"Modo inválido: {mode}. Use eco ou perf.", None

    cores = get_core_indices(mode_to_core[mode])
    if not cores:
        message = f"Topologia indisponível: não foi possível identificar {mode_to_core[mode]}."
        _record_event(pid=pid, action="apply", mode=mode, result="rejected", details=message)
        return False, message, None

    try:
        process = psutil.Process(pid)
        name, create_time = _process_identity(process)
        previous_affinity = process.cpu_affinity()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError) as exc:
        message = f"Não foi possível acessar o PID {pid}: {exc}"
        _record_event(pid=pid, action="apply", mode=mode, result="failed", details=message)
        return False, message, None

    key = str(pid)
    try:
        processes = _load_state()
        old_record = processes.get(key)
        same_identity = bool(isinstance(old_record, dict) and _same_process(old_record, create_time))
        if old_record and not same_identity:
            _record_event(
                pid=pid,
                name=old_record.get("name") if isinstance(old_record, dict) else None,
                create_time=old_record.get("create_time") if isinstance(old_record, dict) else None,
                action="state",
                result="stale_pid_record_replaced",
                details="O PID foi reutilizado; o estado anterior não pertence ao processo atual.",
            )

        original_affinity = (
            list(old_record["original_affinity"])
            if same_identity
            else list(previous_affinity)
        )
        record: Dict[str, Any] = {
            "pid": pid,
            "name": name,
            "create_time": create_time,
            "original_affinity": original_affinity,
            "current_affinity": list(previous_affinity),
            "mode": mode,
            "target_affinity": list(cores),
            "status": "pending",
            "updated_at": _timestamp(),
        }
        processes[key] = record
        # O snapshot original é persistido antes da chamada que altera a CPU.
        _save_state(processes)
    except (OSError, RuntimeError, KeyError, TypeError) as exc:
        return False, f"Não foi possível proteger o estado original: {exc}", None

    try:
        process.cpu_affinity(cores)
        actual_affinity = process.cpu_affinity()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError, ValueError) as exc:
        try:
            actual_affinity = process.cpu_affinity()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            actual_affinity = None

        if actual_affinity is None:
            # Resultado indeterminado: mantém o snapshot para permitir --normal.
            record["status"] = "uncertain"
            processes[key] = record
            _save_state(processes)
            result = "uncertain"
        elif actual_affinity != previous_affinity:
            record["current_affinity"] = list(actual_affinity)
            record["status"] = "partial"
            record["updated_at"] = _timestamp()
            processes[key] = record
            _save_state(processes)
            result = "partial"
        else:
            if same_identity:
                processes[key] = old_record
            else:
                processes.pop(key, None)
            _save_state(processes)
            result = "failed"

        log_error = _record_event(
            pid=pid, name=name, create_time=create_time,
            action="apply", mode=mode,
            original_affinity=original_affinity,
            previous_affinity=previous_affinity,
            target_affinity=cores,
            current_affinity=actual_affinity,
            result=result, details=str(exc),
        )
        suffix = f" {log_error}" if log_error else ""
        return False, f"Falha ao aplicar afinidade: {exc}.{suffix}", record if result != "failed" else None

    record["current_affinity"] = list(actual_affinity)
    record["status"] = "active"
    record["updated_at"] = _timestamp()
    processes[key] = record
    try:
        _save_state(processes)
        state_warning = None
    except OSError as exc:
        # O primeiro snapshot continua salvo e é suficiente para o rollback.
        state_warning = f"Estado aplicado não pôde ser atualizado: {exc}"

    exact = sorted(actual_affinity) == sorted(cores)
    result = "success" if exact else "partial"
    details = None if exact else "O Windows aplicou uma afinidade diferente da solicitada."
    log_error = _record_event(
        pid=pid, name=name, create_time=create_time,
        action="apply", mode=mode,
        original_affinity=original_affinity,
        previous_affinity=previous_affinity,
        target_affinity=cores,
        current_affinity=actual_affinity,
        result=result, details=details,
    )
    warnings = [item for item in (state_warning, log_error) if item]
    suffix = f" Aviso: {'; '.join(warnings)}" if warnings else ""

    if exact:
        return True, f"PID {pid} ({name}) limitado a {mode}: CPUs lógicas {actual_affinity}.{suffix}", record

    message = (
        f"Afinidade parcial no PID {pid} ({name}). Solicitado: {cores}; "
        f"aplicado: {actual_affinity}. O estado original foi preservado."
    )
    return False, message + suffix, record


def restore_process_affinity(
    pid: int,
) -> Tuple[bool, str, Dict[str, Any] | None]:
    """Restaura a afinidade original, validando PID e horário de criação."""
    key = str(pid)
    try:
        processes = _load_state()
    except RuntimeError as exc:
        return False, str(exc), None

    record = processes.get(key)
    if not record:
        message = f"Não há afinidade original registrada para o PID {pid}; nada foi alterado."
        _record_event(pid=pid, action="restore", mode="normal", result="no_saved_state", details=message)
        return False, message, None

    try:
        process = psutil.Process(pid)
        name, create_time = _process_identity(process)
        if not _same_process(record, create_time):
            message = (
                f"O PID {pid} agora pertence a outro processo. "
                "A restauração foi bloqueada."
            )
            _record_event(
                pid=pid, name=name, create_time=create_time,
                action="restore", mode="normal",
                result="identity_mismatch", details=message,
            )
            return False, message, None

        original = [int(cpu) for cpu in record["original_affinity"]]
        previous = process.cpu_affinity()
        process.cpu_affinity(original)
        actual = process.cpu_affinity()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess,
            OSError, ValueError, KeyError, TypeError) as exc:
        message = f"Falha ao restaurar a afinidade do PID {pid}: {exc}"
        _record_event(
            pid=pid, name=record.get("name"),
            create_time=record.get("create_time"),
            action="restore", mode="normal",
            original_affinity=record.get("original_affinity"),
            result="failed", details=message,
        )
        return False, message, record

    if sorted(actual) != sorted(original):
        record["current_affinity"] = list(actual)
        record["status"] = "partial"
        record["updated_at"] = _timestamp()
        try:
            _save_state(processes)
        except OSError as exc:
            return False, f"Restauração parcial; não foi possível atualizar o estado: {exc}", record

        message = (
            f"Restauração parcial do PID {pid}. Solicitado: {original}; "
            f"aplicado: {actual}. O registro foi mantido."
        )
        log_error = _record_event(
            pid=pid, name=name, create_time=create_time,
            action="restore", mode="normal",
            original_affinity=original, previous_affinity=previous,
            current_affinity=actual, result="partial", details=message,
        )
        if log_error:
            message += f" {log_error}"
        return False, message, record

    processes.pop(key, None)
    try:
        _save_state(processes)
    except OSError as exc:
        # A afinidade foi restaurada, mas mantemos o registro se a escrita falhar.
        return False, f"A afinidade foi restaurada, mas o estado não pôde ser atualizado: {exc}", record

    message = f"PID {pid} ({name}) restaurado à afinidade original: {actual}."
    log_error = _record_event(
        pid=pid, name=name, create_time=create_time,
        action="restore", mode="normal",
        original_affinity=original, previous_affinity=previous,
        current_affinity=actual, result="success",
    )
    if log_error:
        message += f" Aviso: {log_error}"
    return True, message, record


def get_affinity_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Lê os últimos eventos do histórico JSONL."""
    if limit < 1 or not HISTORY_FILE.exists():
        return []
    events = deque(maxlen=limit)
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as history:
            for line in history:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    events.append(event)
    except OSError as exc:
        raise RuntimeError(f"Não foi possível ler o histórico: {exc}") from exc
    return list(events)


def pin_process(process_name: str, core_type: str = "e-cores") -> Tuple[bool, str, int]:
    """Compatibilidade legada por nome; altera todas as instâncias encontradas."""
    if core_type not in {"e-cores", "p-cores"}:
        return False, f"Tipo inválido: {core_type}. Use e-cores ou p-cores.", 0

    normalized_name = process_name.lower()
    if not normalized_name.endswith(".exe"):
        normalized_name += ".exe"
    mode = {"e-cores": "eco", "p-cores": "perf"}[core_type]

    affected = 0
    failures: List[str] = []
    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = process.info.get("name")
            if name and name.lower() == normalized_name:
                ok, message, _ = apply_process_affinity(process.info["pid"], mode)
                if ok:
                    affected += 1
                else:
                    failures.append(message)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if affected == 0:
        message = f"Nenhum processo '{normalized_name}' foi modificado."
        if failures:
            message += " " + " | ".join(failures[:3])
        return False, message, 0

    message = f"Afinidade aplicada a {affected} instância(s) de '{normalized_name}'."
    if failures:
        message += f" Falhas em {len(failures)} instância(s); consulte o histórico."
    return True, message, affected
