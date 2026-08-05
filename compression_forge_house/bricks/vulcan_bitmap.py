# -*- coding: utf-8 -*-
from .compression_presets import VULCAN_LEXICON

def generate_bitmap(path: str) -> int:
    path_low = path.lower()
    bitmap = 0
    for i, term in enumerate(VULCAN_LEXICON):
        if term.lower() in path_low:
            bitmap |= (1 << i)
    return bitmap

def get_query_mask(query_str: str) -> tuple:
    query_low = query_str.lower()
    mask = 0
    for i, term in enumerate(VULCAN_LEXICON):
        if term.lower() in query_low:
            mask |= (1 << i)
    return mask, (mask > 0)