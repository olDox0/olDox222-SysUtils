# -*- coding: utf-8 -*-
# doxbackup/core/compression/__init__.py
"""
Sistema de Compressão Aprendida para DoxBackup V3.

Arquitetura:
- dict_learner: Treinamento de dicionários Zstd por extensão
- adaptive_roi: Ajuste dinâmico do tamanho do dicionário baseado em payback
- codec_manager: Seleção de codec por arquivo
"""

from .dict_learner import DictLearner, DictManifest
from .codec_manager import CodecManager

__all__ = [
    'DictLearner',
    'DictManifest',
    'CodecManager',
]