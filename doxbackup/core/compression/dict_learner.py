# -*- coding: utf-8 -*-
# doxbackup/core/compression/dict_learner.py
""" Dict Learner — Aprendizado de dicionários Zstd por extensão.
Versão 2.0: Cache LRU + Sanitização robusta + Logging estruturado. """

from __future__ import annotations
import hashlib
import json
import math
import os
import random
import re
import logging
import signal
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import zstandard as zstd

# ═══════════════════════════════════════════════════════════════
# LOGGING ESTRUTURADO (substitui print)
# ═══════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════

LEARNER_VERSION = 2  # Bump: agora com métricas de entropia
MIN_TRAIN_FILES = 8
MIN_TRAIN_BYTES = 32 * 1024
MIN_CORPUS_BYTES_FOR_DICT = 96 * 1024
MAX_SAMPLE_FILES = 500
MAX_SAMPLE_BYTES = 16 * 1024 * 1024
MIN_FILE_SIZE = 64
MAX_FILE_SIZE = 1_000_000
DEFAULT_TRAIN_LEVEL = 5
DEFAULT_COMPRESS_LEVEL = 19
DEFAULT_DICT_SIZE = 64 * 1024
MIN_NET_GAIN_BYTES = 8 * 1024
MIN_PAYBACK_RATIO = 2.0

# Timeout de segurança para treinamento (evita hang em corpus gigante)
TRAIN_TIMEOUT_SECONDS = 60

DictSizeSpec = Union[int, str]

# ═══════════════════════════════════════════════════════════════
# MANIFESTO COM PROPRIEDADES DE EFICIÊNCIA
# ═══════════════════════════════════════════════════════════════

@dataclass
class DictManifest:
    """Manifesto de um dicionário treinado."""
    ext: str
    corpus_sha256: str
    dict_sha256: str
    dict_size: int
    stored_size: int
    sample_count: int
    trained_bytes: int
    train_level: int
    compress_level: int
    learner_version: int
    dict_path: str
    decision: str = "pending"
    roi: Optional[dict] = None
    telemetry: Optional[dict] = None
    
    @property
    def is_accepted(self) -> bool:
        """Retorna True se o dicionário foi aceito (treinado ou cacheado)."""
        return self.decision in ("trained", "cached")
    
    @property 
    def efficiency(self) -> float:
        """Bytes economizados por byte de dicionário (ROI real)."""
        if self.dict_size == 0:
            return 0.0
        gain = (self.roi or {}).get("net_gain", 0)
        return max(0.0, gain / self.dict_size)


_DICT_OBJECT_CACHE: Dict[str, zstd.ZstdCompressionDict] = {}

# ═══════════════════════════════════════════════════════════════
# CACHE LRU COM LIMITE (substitui dict global infinito)
# ═══════════════════════════════════════════════════════════════

@lru_cache(maxsize=32)
def _get_dict_object_cached(dict_path: str, dict_sha256: str) -> Optional[zstd.ZstdCompressionDict]:
    """
    Cache LRU de dicionários Zstd.
    
    Usa SHA256 como parte da chave para invalidação automática
    quando o dicionário muda (mesmo path, conteúdo diferente).
    """
    try:
        path = Path(dict_path)
        if not path.exists():
            return None
        return zstd.ZstdCompressionDict(path.read_bytes())
    except Exception as e:
        logger.warning("Falha ao carregar dicionário %s: %s", dict_path, e)
        return None

@contextmanager
def _time_limit(seconds: int):
    """
    Context manager para timeout em operações bloqueantes.
    
    No Windows, usa threading.Timer (SIGALRM não existe).
    No Unix, usa signal.SIGALRM (mais preciso).
    """
    if os.name == 'nt':
        # Windows: usa threading.Timer + exceção customizada
        import threading
        
        class TimeoutError(Exception):
            pass
        
        timer = None
        
        def raise_timeout():
            raise TimeoutError(f"Operação excedeu {seconds}s")
        
        timer = threading.Timer(seconds, raise_timeout)
        timer.start()
        try:
            yield
        finally:
            timer.cancel()
    else:
        # Unix: usa signal.SIGALRM
        def handler(signum, frame):
            raise TimeoutError(f"Operação excedeu {seconds}s")
        
        old_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

def safe_ext(ext: str) -> str:
    """
    Sanitiza extensão para uso seguro em nomes de arquivo.
    
    Protege contra:
    - Path traversal: ".foo/../../../etc" → "foo______etc"
    - Caracteres especiais: ".c++" → "c__"
    - Extensões vazias: "" → "noext"
    """
    if not ext:
        return "noext"
    
    # Remove ponto inicial e converte para lowercase
    cleaned = ext.lstrip(".").lower()
    
    # Substitui qualquer caractere não-alfanumérico por underscore
    sanitized = re.sub(r'[^a-z0-9]', '_', cleaned)
    
    # Remove underscores consecutivos
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    
    return sanitized or "noext"

def calculate_entropy(data: bytes) -> float:
    """Calcula entropia de Shannon em bits por byte."""
    if not data:
        return 0.0
    freq = [0] * 256
    for byte in data:
        freq[byte] += 1
    length = len(data)
    entropy = 0.0
    for count in freq:
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)
    return entropy


def choose_dict_size(corpus_bytes: int, spec: DictSizeSpec = "auto") -> int:
    """Escolhe tamanho de dicionário por tamanho do corpus."""
    if isinstance(spec, int):
        return max(1024, int(spec))
    
    s = str(spec).strip().lower()
    if s.isdigit():
        return max(1024, int(s))
    if s.endswith("k"):
        try:
            return max(1024, int(float(s[:-1]) * 1024))
        except Exception:
            pass
    if s.endswith("kb"):
        try:
            return max(1024, int(float(s[:-2]) * 1024))
        except Exception:
            pass
    
    if corpus_bytes < 1_000_000:
        return 16 * 1024
    if corpus_bytes < 5_000_000:
        return 32 * 1024
    if corpus_bytes < 25_000_000:
        return 64 * 1024
    if corpus_bytes < 200_000_000:
        return 112 * 1024
    return 256 * 1024


def make_corpus_hash(files: List[Path], hashes: Dict[Path, str]) -> str:
    """Hash estável do corpus."""
    h = hashlib.sha256()
    h.update(f"sysutils-dict-learner:{LEARNER_VERSION}".encode("utf-8"))
    
    for f in sorted(files, key=lambda p: p.as_posix()):
        file_hash = hashes.get(f)
        if not file_hash:
            continue
        h.update(f.as_posix().encode("utf-8", "replace"))
        h.update(file_hash.encode("ascii", "replace"))
        try:
            h.update(str(f.stat().st_size).encode("ascii"))
        except OSError:
            h.update(b"0")
    
    return h.hexdigest()


def select_top_extensions(
    files: List[Path],
    top_n: int = 3,
) -> List[Tuple[str, dict]]:
    """Seleciona as maiores extensões por bytes totais."""
    stats: Dict[str, dict] = defaultdict(lambda: {"files": [], "bytes": 0})
    
    for f in files:
        try:
            size = f.stat().st_size
        except OSError:
            continue
        
        ext = f.suffix.lower() or ".noext"
        stats[ext]["files"].append(f)
        stats[ext]["bytes"] += size
    
    ranked = sorted(
        stats.items(),
        key=lambda kv: (kv[1]["bytes"], kv[0]),
        reverse=True,
    )
    
    return ranked[:max(0, int(top_n))]


def collect_samples(
    files: List[Path],
    seed: str,
    max_files: int = MAX_SAMPLE_FILES,
    max_bytes: int = MAX_SAMPLE_BYTES,
) -> Tuple[List[bytes], int]:
    """
    Coleta amostras com weighted sampling (prioriza arquivos médios).
    
    Estratégia:
    - Arquivos < 1KB: peso 0.1 (muito pequenos, pouco padrão)
    - Arquivos 1KB-100KB: peso 1.0 (tamanho ideal)
    - Arquivos > 100KB: peso 0.3 (muito grandes, dominam o corpus)
    """
    rng = random.Random(seed)
    
    # Classifica arquivos por tamanho e atribui pesos
    weighted_candidates = []
    for f in files:
        try:
            size = f.stat().st_size
            if size < MIN_FILE_SIZE or size > MAX_FILE_SIZE:
                continue
            
            # Calcula peso baseado no tamanho
            if size < 1024:
                weight = 0.1
            elif size < 100 * 1024:
                weight = 1.0
            else:
                weight = 0.3
            
            weighted_candidates.append((size, f, weight))
        except OSError:
            continue
    
    # Ordena por peso (maior primeiro) e depois embaralha dentro de cada peso
    weighted_candidates.sort(key=lambda x: (-x[2], rng.random()))
    
    samples = []
    total_bytes = 0
    
    for size, path, weight in weighted_candidates[:max_files]:
        if total_bytes + size > max_bytes:
            break
        try:
            data = path.read_bytes()
            samples.append(data)
            total_bytes += len(data)
        except (OSError, MemoryError):
            continue
    
    return samples, total_bytes


def _compressor(level: int = DEFAULT_COMPRESS_LEVEL) -> zstd.ZstdCompressor:
    """Cria compressor Zstd com parâmetros padrão."""
    return zstd.ZstdCompressor(level=level, threads=1)


def compress_bytes(data: bytes, level: int = DEFAULT_COMPRESS_LEVEL) -> bytes:
    """Comprime bytes com Zstd."""
    return _compressor(level).compress(data)


def decompress_bytes(data: bytes) -> bytes:
    """Descomprime bytes Zstd."""
    return zstd.ZstdDecompressor().decompress(data)


def train_zstd_dictionary(
    samples: List[bytes],
    dict_size: int = DEFAULT_DICT_SIZE,
    level: int = DEFAULT_TRAIN_LEVEL,
) -> zstd.ZstdCompressionDict:
    """
    Treina um dicionário Zstd com timeout de segurança.
    
    Raises:
        TimeoutError: Se o treinamento exceder TRAIN_TIMEOUT_SECONDS.
        Exception: Se o Zstd falhar no treinamento.
    """
    with _time_limit(TRAIN_TIMEOUT_SECONDS):
        return zstd.train_dictionary(dict_size, samples, level=level)


def _extract_dict_id(dict_obj: zstd.ZstdCompressionDict) -> int:
    """Extrai ID do dicionário."""
    return dict_obj.dict_id()


def _baseline_compressed_size(
    samples: List[bytes],
    level: int = DEFAULT_COMPRESS_LEVEL,
) -> int:
    """Calcula tamanho total comprimido sem dicionário."""
    cctx = _compressor(level)
    total = 0
    for sample in samples:
        total += len(cctx.compress(sample))
    return total


def evaluate_dictionary_roi(
    samples: List[bytes],
    dict_obj: zstd.ZstdCompressionDict,
    dict_bytes: bytes,
    level: int = DEFAULT_COMPRESS_LEVEL,
    total_corpus_bytes: int = 0,  # NOVO: tamanho total do corpus
) -> dict:
    """Avalia o ROI de um dicionário com payback adaptativo."""
    baseline_size = _baseline_compressed_size(samples, level)
    
    cctx = zstd.ZstdCompressor(level=level, dict_data=dict_obj, threads=1)
    dict_compressed_size = sum(len(cctx.compress(s)) for s in samples)
    
    dict_overhead = len(dict_bytes)
    net_gain = baseline_size - dict_compressed_size - dict_overhead
    payback_ratio = net_gain / dict_overhead if dict_overhead > 0 else 0.0
    
    # Payback adaptativo: projetos pequenos são mais permissivos
    if total_corpus_bytes > 5_000_000:
        required_payback = 2.0  # Projetos grandes: exigente
    elif total_corpus_bytes > 1_000_000:
        required_payback = 1.5  # Projetos médios: moderado
    else:
        required_payback = 1.0  # Projetos pequenos: permissivo
    
    decision = "accept" if (
        net_gain >= MIN_NET_GAIN_BYTES and payback_ratio >= required_payback
    ) else "reject"
    
    return {
        "baseline_size": baseline_size,
        "dict_compressed_size": dict_compressed_size,
        "dict_overhead": dict_overhead,
        "net_gain": net_gain,
        "payback_ratio": payback_ratio,
        "required_payback": required_payback,
        "decision": decision,
    }


class DictLearner:
    """Treinador de dicionários Zstd com ROI adaptativo."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.cache_dir = self.project_root / ".doxoade" / "compression" / "dictionaries"
        self.manifest_path = self.project_root / ".doxoade" / "compression" / "manifest.json"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def dict_cache_dir(self) -> Path:
        return self.cache_dir
    
    def _load_manifest(self) -> dict:
        """Carrega manifesto de dicionários."""
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"version": LEARNER_VERSION, "dictionaries": {}}
    
    def _save_manifest(self, manifest: dict):
        """Salva manifesto de dicionários."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def prepare_dictionaries(
        self,
        files: List[Path],
        file_hashes: Dict[Path, str],
        top_n: int = 3,
        dict_size: DictSizeSpec = "auto",
        retrain: bool = False,
        roi_guard: bool = True,
        log_func=None,  # NOVO: callback para logging
    ) -> Dict[str, DictManifest]:
        """
        Prepara dicionários para as top N extensões.
        
        Args:
            log_func: Função callback para logs (ex: _safe_log do engine.py)
        """
        def log(msg, level="info"):
            if log_func:
                log_func(msg)
            else:
                print(f"[DICT] {msg}")

        manifest = self._load_manifest()
        result: Dict[str, DictManifest] = {}
        
        top_exts = select_top_extensions(files, top_n)
        
        for ext, stats in top_exts:
            ext_files = stats["files"]
            ext_bytes = stats["bytes"]
            
            if len(ext_files) < MIN_TRAIN_FILES:
                continue
            if ext_bytes < MIN_CORPUS_BYTES_FOR_DICT:
                continue
            
            corpus_hash = make_corpus_hash(ext_files, file_hashes)
            safe_name = safe_ext(ext)
            
            cached = manifest.get("dictionaries", {}).get(ext)
            if cached and not retrain:
                if cached.get("corpus_sha256") == corpus_hash:
                    dict_path = Path(cached["dict_path"])
                    if dict_path.exists():
                        dm = DictManifest(
                            ext=ext,
                            corpus_sha256=corpus_hash,
                            dict_sha256=cached.get("dict_sha256", ""),
                            dict_size=cached.get("dict_size", DEFAULT_DICT_SIZE),
                            stored_size=cached.get("stored_size", 0),
                            sample_count=cached.get("sample_count", 0),
                            trained_bytes=cached.get("trained_bytes", 0),
                            train_level=cached.get("train_level", DEFAULT_TRAIN_LEVEL),
                            compress_level=cached.get("compress_level", DEFAULT_COMPRESS_LEVEL),
                            learner_version=cached.get("learner_version", LEARNER_VERSION),
                            dict_path=str(dict_path),
                            decision=cached.get("decision", "cached"),
                            roi=cached.get("roi"),
                        )
                        result[ext] = dm
                        continue
            
            target_size = choose_dict_size(ext_bytes, dict_size)
            seed = f"{ext}:{corpus_hash}"
            samples, sample_bytes = collect_samples(ext_files, seed)
            
            if not samples or sample_bytes < MIN_TRAIN_BYTES:
                continue
            
            try:
                dict_obj = train_zstd_dictionary(samples, target_size, DEFAULT_TRAIN_LEVEL)
            except Exception as e:
                logger.warning("Falha ao treinar dicionário para %s: %s", ext, e)
                continue
            
            dict_bytes = dict_obj.as_bytes()
            dict_sha = hashlib.sha256(dict_bytes).hexdigest()[:16]
            
            roi = evaluate_dictionary_roi(
                samples, dict_obj, dict_bytes,
                DEFAULT_COMPRESS_LEVEL,
                total_corpus_bytes=ext_bytes,  # NOVO
            )
            
            if roi_guard and roi["decision"] == "reject":
                log(f"{ext}: ROI insuficiente (gain={roi['net_gain']}, payback={roi['payback_ratio']:.2f})")
                continue
                
            dict_filename = f"{safe_name}_{dict_sha}.dict"
            dict_path = self.cache_dir / dict_filename
            dict_path.write_bytes(dict_bytes)
            
            dm = DictManifest(
                ext=ext,
                corpus_sha256=corpus_hash,
                dict_sha256=dict_sha,
                dict_size=len(dict_bytes),
                stored_size=dict_path.stat().st_size,
                sample_count=len(samples),
                trained_bytes=sample_bytes,
                train_level=DEFAULT_TRAIN_LEVEL,
                compress_level=DEFAULT_COMPRESS_LEVEL,
                learner_version=LEARNER_VERSION,
                dict_path=str(dict_path),
                decision="trained",
                roi=roi,
            )
            
            result[ext] = dm
            
            if "dictionaries" not in manifest:
                manifest["dictionaries"] = {}
            manifest["dictionaries"][ext] = asdict(dm)
        
        self._save_manifest(manifest)
        return result
    
    def get_dict_object(self, ext: str) -> Optional[zstd.ZstdCompressionDict]:
        """Retorna objeto de dicionário para uma extensão."""
        if ext in _DICT_OBJECT_CACHE:
            return _DICT_OBJECT_CACHE[ext]
        
        manifest = self._load_manifest()
        cached = manifest.get("dictionaries", {}).get(ext)
        if not cached:
            return None
        
        dict_path = Path(cached.get("dict_path", ""))
        if not dict_path.exists():
            return None
        
        try:
            dict_bytes = dict_path.read_bytes()
            dict_obj = zstd.ZstdCompressionDict(dict_bytes)
            _DICT_OBJECT_CACHE[ext] = dict_obj
            return dict_obj
        except Exception:
            return None
    
    def print_plan(self, manifests: Dict[str, DictManifest], log_func=None):
        """Imprime plano de dicionários treinados."""
        if not manifests:
            if log_func: log_func("[DICT] Nenhum dicionário treinado.")
            return
        
        # Se não houver log_func, usa print padrão (fallback)
        out = log_func if log_func else print
        
        out(f"\n{'='*60}")
        out("DICIONÁRIOS TREINADOS")
        out(f"{'='*60}")
        out(f"{'EXT':<10} | {'TAMANHO':>10} | {'GANHO':>10} | {'PAYBACK':>8} | {'DECISÃO'}")
        out("-" * 60)
        
        for ext, dm in sorted(manifests.items()):
            roi = dm.roi or {}
            gain = roi.get("net_gain", 0)
            payback = roi.get("payback_ratio", 0)
            out(f"{ext:<10} | {dm.dict_size:>10,} | {gain:>10,} | {payback:>8.2f} | {dm.decision}")
        
        out(f"{'='*60}\n")