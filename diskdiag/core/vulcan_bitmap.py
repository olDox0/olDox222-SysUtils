# -*- coding: utf-8 -*-
# diskdiag/core/vulcan_bitmap.py

BITMAP_TERMS = [
    "windows", "system32", "program files", "appdata", "local", "roaming",
    "microsoft", "temp", "drivers", "winsxs", "users", "common", "cache",
    "utils", "diskdiag", "core", "cli", "bloatbreaker", "doxbackup", # <--- Termos do seu projeto
    ".py", ".dll", ".exe", ".sys", ".log", ".bak", ".tmp", ".json"
]

def generate_bitmap(path: str) -> int:
    path_low = path.lower()
    bitmap = 0
    for i, term in enumerate(BITMAP_TERMS):
        if term in path_low:
            bitmap |= (1 << i)
    return bitmap

def get_query_mask(query_str: str) -> tuple:
    query_low = query_str.lower()
    mask = 0
    # Se a busca contém qualquer um dos termos mapeados, ativamos o modo Bitmap
    for i, term in enumerate(BITMAP_TERMS):
        if term in query_low:
            mask |= (1 << i)

    return mask, (mask > 0)
