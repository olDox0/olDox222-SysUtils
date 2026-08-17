# doxbackup/core/compression/pipeline.py
"""
Compression Pipeline - Orquestrador assíncrono "can't stop".

Estratégia "can't stop":
- Enquanto comprime o arquivo N, já está preparando o N+1
- Enquanto treina dicionário da extensão X, já está coletando samples da Y
- Pipeline em 3 estágios:
  1. COLECT: Coleta arquivos e calcula hashes
  2. PREPARE: Prepara dicionários e compressores
  3. COMPRESS: Comprime e empacota
  
Usa asyncio.Queue para passar dados entre estágios.
"""

from __future__ import annotations
import asyncio
from pathlib import Path
from typing import List, AsyncIterator
from dataclasses import dataclass


@dataclass
class FileTask:
    """Tarefa de compressão para um arquivo."""
    path: Path
    rel_path: str
    size: int
    ext: str
    hash: str


@dataclass
class CompressionResult:
    """Resultado da compressão de um arquivo."""
    path: Path
    rel_path: str
    original_size: int
    compressed_size: int
    codec: str  # "zstd", "zstd+dict", "store"
    dict_sha256: str = ""
    data: bytes = b""


class CompressionPipeline:
    """
    Pipeline assíncrono de compressão com estratégia "can't stop".
    
    Exemplo de uso:
        pipeline = CompressionPipeline(project_root, files)
        async for result in pipeline.run():
            # Processa resultado enquanto próximo arquivo já está sendo preparado
            process(result)
    """
    
    def __init__(
        self,
        project_root: Path,
        files: List[Path],
        compress_level: int = 19,
        use_dicts: bool = True,
        dict_top_n: int = 3,
    ):
        self.project_root = Path(project_root).resolve()
        self.files = files
        self.compress_level = compress_level
        self.use_dicts = use_dicts
        self.dict_top_n = dict_top_n
        
        # Filas para comunicação entre estágios
        self.collect_queue: asyncio.Queue[FileTask] = asyncio.Queue(maxsize=100)
        self.prepare_queue: asyncio.Queue[FileTask] = asyncio.Queue(maxsize=100)
        self.compress_queue: asyncio.Queue[CompressionResult] = asyncio.Queue(maxsize=100)
        
    async def run(self) -> AsyncIterator[CompressionResult]:
        """
        Executa o pipeline e yields resultados conforme ficam prontos.
        
        PLACEHOLDER - implementação completa na Fase 1.
        """
        raise NotImplementedError("CompressionPipeline.run será implementado na Fase 1")
        
    async def _collect_stage(self):
        """
        Estágio 1: Coleta arquivos, calcula hashes e classifica.
        
        PLACEHOLDER - implementação completa na Fase 1.
        """
        raise NotImplementedError("_collect_stage será implementado na Fase 1")
        
    async def _prepare_stage(self):
        """
        Estágio 2: Prepara dicionários e compressores para cada extensão.
        
        PLACEHOLDER - implementação completa na Fase 1.
        """
        raise NotImplementedError("_prepare_stage será implementado na Fase 1")
        
    async def _compress_stage(self):
        """
        Estágio 3: Comprime arquivos usando o codec apropriado.
        
        PLACEHOLDER - implementação completa na Fase 1.
        """
        raise NotImplementedError("_compress_stage será implementado na Fase 1")