# -*- coding: utf-8 -*-
# doxbackup/core/watermelon_ext.py
"""
DCT1 Watermelon Extension Auditor

Sistema read-only para avaliar extensões e recomendar estratégia
de compressão para o DCT1 Watermelon.

Nenhum arquivo é modificado ou removido.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


WATERMELON_EXT_VERSION = "DCT1W-EXT-0.1"

# Mínimo para recomendar dicionário.
# Valores inspirados no dict_learner do Doxoade.
MIN_DICT_FILES = 8
MIN_DICT_BYTES = 96 * 1024

# Heurísticas de entropia.
ENTROPY_HIGH = 7.45
ENTROPY_DICT_MAX = 6.90

IGNORED_DIRS = {
    "$RECYCLE.BIN",
    "SYSTEM VOLUME INFORMATION",
    ".DOXOADE",
    ".DOXOADE_CACHE",
    ".GIT",
    ".IDEA",
    ".MYPY_CACHE",
    ".PYTEST_CACHE",
    ".RUFF_CACHE",
    ".VENV",
    ".VSCODE",
    "__PYCACHE__",
    "BUILD",
    "DIST",
    "NODE_MODULES",
    "TEMP",
    "TMP",
    "VENV",
}

IGNORED_EXTS = {
    ".tmp",
    ".temp",
    ".bak",
    ".old",
    ".log",
    ".dmp",
    ".swp",
    ".crdownload",
    ".dox",
}

STORE_EXTS = {
    ".7z",
    ".avi",
    ".bin",
    ".db",
    ".dll",
    ".dox",
    ".exe",
    ".gif",
    ".gguf",
    ".gz",
    ".iso",
    ".jpeg",
    ".jpg",
    ".mkv",
    ".mp3",
    ".mp4",
    ".obj",
    ".png",
    ".pyd",
    ".rar",
    ".so",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".webp",
    ".whl",
    ".zim",
    ".zip",
    ".zst",
}

DICT_EXTS = {
    ".py",
    ".pyi",
    ".pyx",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".json",
    ".jsonc",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".conf",
    ".md",
    ".markdown",
    ".rst",
    ".txt",
    ".csv",
    ".tsv",
    ".xml",
}


@dataclass
class ExtensionStats:
    ext: str
    count: int = 0
    total_bytes: int = 0
    sampled_files: int = 0
    sampled_bytes: int = 0
    entropy_sum: float = 0.0
    min_entropy: Optional[float] = None
    max_entropy: Optional[float] = None
    unreadable: int = 0
    recommended_mode: str = "pending"
    confidence: str = "low"
    reasons: List[str] = field(default_factory=list)


@dataclass
class FileDecision:
    path: str
    ext: str
    size: int
    category: str
    mode: str
    reason: str
    entropy: Optional[float] = None
    sampled_bytes: int = 0


@dataclass
class ExtensionAuditReport:
    version: str
    source: str
    generated_at: str = ""
    total_files: int = 0
    total_bytes: int = 0
    ignored_files: int = 0
    unreadable_files: int = 0
    skipped_symlinks: int = 0
    extensions: Dict[str, ExtensionStats] = field(default_factory=dict)
    decisions: List[FileDecision] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def normalize_ext(name: str) -> str:
    ext = Path(name).suffix.lower()
    return ext if ext else ".noext"


def is_ignored_dir(name: str) -> bool:
    up = name.strip().upper()

    if up in IGNORED_DIRS:
        return True

    # Por padrão, ignora pastas ocultas, salvo exceções.
    if up.startswith(".") and up not in {".CONFIG", ".DOCUMENTS", ".PHOTOS"}:
        return True

    return False


def classify_extension(ext: str) -> str:
    if ext in IGNORED_EXTS:
        return "ignore"

    if ext in STORE_EXTS:
        return "store"

    if ext in DICT_EXTS:
        return "dict_candidate"

    return "general"


def calculate_entropy(data: bytes) -> float:
    if not data:
        return 0.0

    freq = [0] * 256

    for byte in data:
        freq[byte] += 1

    length = len(data)
    entropy = 0.0

    for count in freq:
        if count <= 0:
            continue

        p = count / length
        entropy -= p * math.log2(p)

    return entropy


def _sample_file(path: Path, max_bytes: int) -> tuple[bytes, int]:
    """
    Lê uma amostra do arquivo sem carregar tudo.

    Estratégia:
    - arquivo pequeno: lê inteiro;
    - arquivo grande: lê início, meio e fim.
    """
    size = path.stat().st_size

    if size <= 0:
        return b"", 0

    if size <= max_bytes:
        data = path.read_bytes()
        return data, len(data)

    part = max(1, max_bytes // 3)

    with open(path, "rb") as f:
        head = f.read(part)

        f.seek(size // 2)
        middle = f.read(part)

        f.seek(max(0, size - part))
        tail = f.read(part)

    data = head + middle + tail
    return data, len(data)


def _confidence(stats: ExtensionStats) -> str:
    if stats.sampled_files >= 16 and stats.total_bytes >= 1_000_000:
        return "high"

    if stats.sampled_files >= 8 and stats.total_bytes >= 256_000:
        return "medium"

    return "low"


def _finalize_extension_recommendations(report: ExtensionAuditReport) -> None:
    for ext, stats in report.extensions.items():
        category = classify_extension(ext)

        avg_entropy = None
        if stats.sampled_files > 0:
            avg_entropy = stats.entropy_sum / stats.sampled_files

        if category == "ignore":
            stats.recommended_mode = "skip"
            stats.reasons.append("ignored_extension")

        elif category == "store":
            stats.recommended_mode = "store"
            stats.reasons.append("known_store_extension")

        elif stats.count < MIN_DICT_FILES or stats.total_bytes < MIN_DICT_BYTES:
            stats.recommended_mode = "zstd"
            stats.reasons.append("insufficient_corpus_for_dict")

        elif avg_entropy is not None and avg_entropy >= ENTROPY_HIGH:
            stats.recommended_mode = "store"
            stats.reasons.append("high_entropy_probably_incompressible")

        elif category == "dict_candidate":
            stats.recommended_mode = "zstd+dict"
            stats.reasons.append("known_textual_or_source_extension")

        elif (
            avg_entropy is not None
            and avg_entropy <= ENTROPY_DICT_MAX
            and stats.count >= 16
            and stats.total_bytes >= 256 * 1024
        ):
            stats.recommended_mode = "zstd+dict"
            stats.reasons.append("low_entropy_general_corpus")

        else:
            stats.recommended_mode = "zstd"
            stats.reasons.append("general_zstd")

        stats.confidence = _confidence(stats)


def _decision_mode_from_stats(category: str, stats: Optional[ExtensionStats]) -> str:
    if category == "ignore":
        return "skip"

    if category == "store":
        return "store"

    if stats is None:
        return "zstd"

    return stats.recommended_mode


def audit_extensions(
    source,
    *,
    sample_bytes: int = 4 * 1024 * 1024,
    max_files: Optional[int] = None,
    include_decisions: bool = False,
    follow_symlinks: bool = False,
) -> ExtensionAuditReport:
    """
    Auditoria read-only de extensões.

    Não altera nenhum arquivo.
    """
    source_path = Path(source).resolve()

    report = ExtensionAuditReport(
        version=WATERMELON_EXT_VERSION,
        source=str(source_path),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    records: List[FileDecision] = []
    stop = False

    for root, dirs, files in os.walk(source_path, followlinks=follow_symlinks):
        dirs[:] = [d for d in dirs if not is_ignored_dir(d)]

        for name in files:
            if max_files is not None and report.total_files >= max_files:
                stop = True
                break

            full_path = Path(root) / name

            try:
                if full_path.is_symlink() and not follow_symlinks:
                    report.skipped_symlinks += 1
                    continue

                st = full_path.stat()
            except OSError:
                report.unreadable_files += 1
                continue

            ext = normalize_ext(name)
            category = classify_extension(ext)

            report.total_files += 1
            report.total_bytes += st.st_size

            if category == "ignore":
                report.ignored_files += 1

                if include_decisions:
                    records.append(
                        FileDecision(
                            path=full_path.as_posix(),
                            ext=ext,
                            size=st.st_size,
                            category=category,
                            mode="skip",
                            reason="ignored_extension",
                        )
                    )

                continue

            stats = report.extensions.setdefault(ext, ExtensionStats(ext=ext))
            stats.count += 1
            stats.total_bytes += st.st_size

            entropy: Optional[float] = None
            sampled_bytes = 0

            if category != "store" and st.st_size > 0:
                try:
                    data, sampled_bytes = _sample_file(full_path, sample_bytes)
                    entropy = calculate_entropy(data)

                    stats.sampled_files += 1
                    stats.sampled_bytes += sampled_bytes
                    stats.entropy_sum += entropy

                    if stats.min_entropy is None or entropy < stats.min_entropy:
                        stats.min_entropy = entropy

                    if stats.max_entropy is None or entropy > stats.max_entropy:
                        stats.max_entropy = entropy

                except OSError:
                    stats.unreadable += 1
                    report.unreadable_files += 1

            if include_decisions:
                records.append(
                    FileDecision(
                        path=full_path.as_posix(),
                        ext=ext,
                        size=st.st_size,
                        category=category,
                        mode="pending",
                        reason="awaiting_extension_policy",
                        entropy=entropy,
                        sampled_bytes=sampled_bytes,
                    )
                )

        if stop:
            break

    _finalize_extension_recommendations(report)

    if include_decisions:
        for rec in records:
            stats = report.extensions.get(rec.ext)
            rec.mode = _decision_mode_from_stats(rec.category, stats)

            if stats and stats.reasons:
                rec.reason = "; ".join(stats.reasons)

        report.decisions = records

    return report


def report_to_policy(report: ExtensionAuditReport) -> Dict:
    """
    Converte o relatório em uma política simples para uso futuro
    pelo motor DCT1 Watermelon.
    """
    rules = {}
    confidence = {}
    reasons = {}
    stats_out = {}

    for ext, stats in report.extensions.items():
        rules[ext] = stats.recommended_mode
        confidence[ext] = stats.confidence
        reasons[ext] = stats.reasons

        avg_entropy = None
        if stats.sampled_files > 0:
            avg_entropy = stats.entropy_sum / stats.sampled_files

        stats_out[ext] = {
            "count": stats.count,
            "total_bytes": stats.total_bytes,
            "sampled_files": stats.sampled_files,
            "sampled_bytes": stats.sampled_bytes,
            "avg_entropy": avg_entropy,
            "min_entropy": stats.min_entropy,
            "max_entropy": stats.max_entropy,
            "unreadable": stats.unreadable,
        }

    return {
        "version": report.version,
        "generated_at": report.generated_at,
        "source": report.source,
        "rules": rules,
        "confidence": confidence,
        "reasons": reasons,
        "stats": stats_out,
    }