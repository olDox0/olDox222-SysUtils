# doxbackup/core/compression/adaptive_roi.py
"""
Adaptive ROI - Ajuste dinâmico do tamanho do dicionário baseado em payback.

Estratégia:
1. Começa com tamanho padrão (64KB)
2. Treina e mede o ganho real
3. Se payback_ratio > 2.0 e net_gain > 8KB:
   - Se ganho foi muito bom (>3x payback), tenta aumentar para 112KB
   - Se ganho foi marginal (2-2.5x payback), mantém 64KB
4. Se payback_ratio < 2.0 ou net_gain < 8KB:
   - Tenta diminuir para 32KB ou 16KB
   - Se ainda não pagar, desativa dicionário para essa extensão
5. Salva a decisão no manifest para o próximo backup
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
# [DOX-UNUSED] import zstandard as zstd


@dataclass
class ROIResult:
    """Resultado da avaliação de ROI para um dicionário."""
    dict_size: int
    baseline_size: int  # tamanho sem dicionário
    dict_size_bytes: int  # tamanho do dicionário
    compressed_size: int  # tamanho com dicionário
    net_gain: int  # baseline - compressed - dict_size
    payback_ratio: float  # net_gain / dict_size
    decision: str  # "accept", "increase", "decrease", "disable"
    recommended_size: Optional[int] = None


class AdaptiveROI:
    """
    Avaliador de ROI adaptativo para dicionários Zstd.
    
    Ajusta dinamicamente o tamanho do dicionário baseado em:
    - Ganho líquido (net_gain)
    - Payback ratio
    - Contexto da extensão (Python, C, config, etc.)
    """
    
    # Thresholds para decisões
    EXCELLENT_PAYBACK = 3.0  # pode aumentar
    GOOD_PAYBACK = 2.0  # mantém
    MIN_PAYBACK = 1.5  # tenta diminuir
    
    # Tamanhos disponíveis
    SIZES = [16 * 1024, 32 * 1024, 64 * 1024, 112 * 1024]
    
    def __init__(self):
        pass
        
    def evaluate_roi(
        self,
        dict_size: int,
        baseline_compressed: bytes,
        dict_compressed: bytes,
        dict_bytes: bytes,
        ext_context: str = "general",
    ) -> ROIResult:
        """
        Avalia o ROI de um dicionário e decide o próximo tamanho.
        
        PLACEHOLDER - implementação completa na Fase 1.
        """
        raise NotImplementedError("AdaptiveROI.evaluate_roi será implementado na Fase 1")
        
    def recommend_size(self, current_result: ROIResult) -> int:
        """
        Recomenda o próximo tamanho de dicionário baseado no resultado atual.
        
        PLACEHOLDER - implementação completa na Fase 1.
        """
        raise NotImplementedError("AdaptiveROI.recommend_size será implementado na Fase 1")