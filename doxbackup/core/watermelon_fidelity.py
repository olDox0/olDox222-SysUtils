# -*- coding: utf-8 -*-
# doxbackup/core/watermelon_fidelity.py
"""
DCT1 Watermelon Fidelity
Auditoria de integridade rigorosa. Restaura APENAS em diretório temporário.
"""
from __future__ import annotations
import hashlib
# [DOX-UNUSED] import os
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

WATERMELON_FIDELITY_VERSION = "DCT1W-FID-0.1"
CHUNK_SIZE = 1024 * 1024

@dataclass
class FidelityResult:
    ok: bool = True
    version: str = WATERMELON_FIDELITY_VERSION
    mode: str = "full"
    backup_file: str = ""
    source_dir: str = ""
    restore_dir: str = ""
    started_at: str = ""
    duration_sec: float = 0.0
    total_source_files: int = 0
    total_archive_files: int = 0
    verified_files: int = 0
    missing_in_archive: List[str] = field(default_factory=list)
    extra_in_archive: List[str] = field(default_factory=list)
    size_mismatch: List[Dict[str, Any]] = field(default_factory=list)
    hash_mismatch: List[str] = field(default_factory=list)
    path_safety_violations: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.ok = False
        self.messages.append(message)

    def to_dict(self): return asdict(self)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk: break
            h.update(chunk)
    return h.hexdigest()

def safe_join(base_dir: Path, rel_path: str) -> Path:
    base = Path(base_dir).resolve()
    target = (base / rel_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError(f"Path traversal detected: {rel_path}")
    return target

def normalize_rel(name: str) -> str:
    txt = str(name).replace("\\", "/").strip()
    while txt.startswith("./"): txt = txt[2:]
    while txt.startswith("/"): txt = txt[1:]
    p = Path(txt)
    if p.is_absolute():
        parts = p.parts[1:]
        txt = "/".join(parts) if parts else p.name
    return txt or Path(name).name

def build_source_manifest(source_dir, files: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """
    Constrói o manifesto da origem usando a MESMA lógica de exclusão
    do motor de backup (get_file_list).
    """
    source = Path(source_dir).resolve()
    manifest = {}

    if files is None:
        # Usa a mesma lógica de exclusão do pack/backup_data
        from doxbackup.core.engine import get_file_list
        file_iter = [Path(f) for f in get_file_list(str(source))]
    else:
        file_iter = [Path(f) for f in files]

    for file_path in file_iter:
        p = Path(file_path).resolve()
        try:
            rel = p.relative_to(source).as_posix()
        except ValueError:
            rel = p.name

        entry = {"path": rel, "size": None, "sha256": None, "error": None}
        try:
            if not p.is_file(): continue
            st = p.stat()
            entry["size"] = st.st_size
            entry["sha256"] = sha256_file(p)
        except OSError as e:
            entry["error"] = f"{type(e).__name__}: {e}"
        manifest[rel] = entry
    return manifest

def verify_backup_fidelity_watermelon(backup_file, source_dir, adapter, mode="full", restore_base=None) -> FidelityResult:
    started = time.perf_counter()
    result = FidelityResult(
        mode=mode, backup_file=str(backup_file), source_dir=str(source_dir),
        started_at=datetime.now(timezone.utc).isoformat()
    )
    
    source_path = Path(source_dir).resolve()
    if not source_path.exists():
        result.fail(f"source does not exist: {source_path}")
        return result

    source_manifest = build_source_manifest(source_dir)
    result.total_source_files = len([e for e in source_manifest.values() if not e.get("error")])

    try:
        raw_entries = adapter.list_entries() or []
    except Exception as e:
        result.fail(f"failed to list archive: {type(e).__name__}: {e}")
        return result

    archived = {}
    for entry in raw_entries:
        if isinstance(entry, tuple) and len(entry) >= 2:
            archived[normalize_rel(entry[0])] = entry[1]
        elif isinstance(entry, dict):
            archived[normalize_rel(entry.get("path", ""))] = entry.get("size")

    result.total_archive_files = len(archived)

    for rel, entry in source_manifest.items():
        if entry.get("error"): continue
        if rel not in archived:
            result.missing_in_archive.append(rel)
            result.ok = False
            continue
        if archived[rel] is not None and entry["size"] != archived[rel]:
            result.size_mismatch.append({"path": rel, "expected": entry["size"], "actual": archived[rel]})
            result.ok = False

    if mode == "full":
        try:
            base = Path(restore_base).resolve() if restore_base else Path(tempfile.gettempdir()).resolve()
            base.mkdir(parents=True, exist_ok=True)
            restore_dir = Path(tempfile.mkdtemp(prefix="watermelon_restore_", dir=str(base)))
            result.restore_dir = str(restore_dir)
            
            # Pré-cheque de segurança
            for rel in archived.keys():
                try: safe_join(restore_dir, rel)
                except ValueError:
                    result.path_safety_violations.append(rel)
                    result.ok = False
                    
            if result.path_safety_violations:
                result.fail("unsafe archive paths detected; refusing full restore")
                return result

            adapter.extract_all(restore_dir)
            
            # Validação pós-restauração
            for rel, entry in source_manifest.items():
                if entry.get("error") or not entry.get("sha256"): continue
                target = restore_dir / rel
                if not target.exists(): continue
                
                if sha256_file(target) != entry["sha256"]:
                    result.hash_mismatch.append(rel)
                    result.ok = False
                else:
                    result.verified_files += 1
                    
        except Exception as e:
            result.fail(f"restore failed: {type(e).__name__}: {e}")

    result.duration_sec = time.perf_counter() - started
    return result