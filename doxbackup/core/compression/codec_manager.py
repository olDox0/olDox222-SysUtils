# -*- coding: utf-8 -*-
# doxbackup/core/compression/codec_manager.py
""" Codec Manager — Seleção de codec por arquivo. """

from pathlib import Path
from typing import Optional
import zstandard as zstd

from .dict_learner import DictLearner


STORE_ONLY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
    ".mp3", ".mp4", ".avi", ".mkv", ".mov", ".wav", ".flac", ".ogg",
    ".zip", ".gz", ".tar", ".tgz", ".7z", ".rar", ".zst", ".bz2", ".xz",
    ".exe", ".dll", ".so", ".dylib", ".pyd", ".obj", ".o", ".bin",
    ".db", ".sqlite", ".sqlite3", ".dox", ".iso", ".whl", ".gguf", ".zim",
    ".tmp", ".temp", ".bak", ".old", ".log",
}


class CodecManager:
    """Gerenciador de codecs de compressão."""
    
    def __init__(self, project_root: Path, compress_level: int = 19):
        self.project_root = Path(project_root).resolve()
        self.compress_level = compress_level
        self.learner = DictLearner(project_root)
        self._dict_cache = {}
    
    def should_store(self, ext: str) -> bool:
        """Verifica se extensão deve ser armazenada sem compressão."""
        return ext.lower() in STORE_ONLY_EXTS
    
    def select_codec(
        self,
        path: Path,
        size: int,
        manifests: Optional[dict] = None,
    ) -> tuple:
        """
        Seleciona codec para um arquivo.
        
        Retorna: (codec_name, dict_obj_or_none)
        - ("store", None): não comprimir
        - ("zstd", None): compressão Zstd pura
        - ("zstd+dict", dict_obj): compressão com dicionário
        """
        ext = path.suffix.lower() or ".noext"
        
        if self.should_store(ext):
            return ("store", None)
        
        if size < 256:
            return ("store", None)
        
        if manifests and ext in manifests:
            dict_obj = self.learner.get_dict_object(ext)
            if dict_obj:
                return ("zstd+dict", dict_obj)
        
        return ("zstd", None)
    
    def compress_file(
        self,
        path: Path,
        codec: str,
        dict_obj: Optional[zstd.ZstdCompressionDict] = None,
    ) -> bytes:
        """Comprime arquivo usando codec especificado."""
        data = path.read_bytes()
        
        if codec == "store":
            return data
        
        if codec == "zstd+dict" and dict_obj:
            cctx = zstd.ZstdCompressor(
                level=self.compress_level,
                dict_data=dict_obj,
                threads=1
            )
        else:
            cctx = zstd.ZstdCompressor(level=self.compress_level, threads=1)
        
        return cctx.compress(data)