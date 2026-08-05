# -*- coding: utf-8 -*-
# diskdiag/core/storage.py
import sqlite3
import os
import array
import ctypes
from pathlib import Path

from . import vulcan_dict, vulcan_bitmap
from .compression_presets import WINDOWS_STANDARD_DICT

VLS_DLL = Path(__file__).resolve().parents[2] / "doxoade" / "tools" / "vulcan" / "native" / "vls_scanner.dll"

def init_db(db_path):
    """Garante coluna BLOB e Bitmaps ativos."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path BLOB UNIQUE, 
            size INTEGER,
            mtime REAL,
            ext TEXT,
            bitmap INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bitmap ON files(bitmap)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ext ON files(ext)")
    return conn

def get_real_path(stored_data):
    """Descomprime bytes b'V!' ou decodifica bytes planos."""
    if not stored_data: return ""
    # Converte memoryview/buffer do SQLite para bytes
    raw_bytes = bytes(stored_data)
    if raw_bytes.startswith(b"V!"):
        return vulcan_dict.decompress_from_binary(raw_bytes[2:], WINDOWS_STANDARD_DICT)
    try:
        return raw_bytes.decode('utf-8', errors='ignore')
    except:
        return str(stored_data)

def insert_files(conn, batch):
    """Fluxo Industrial: Bitmap -> Compress -> BLOB."""
    processed = []
    for path, size, mtime, ext in batch:
        bmap = vulcan_bitmap.generate_bitmap(path)
        if len(path) > 30:
            comp = b"V!" + vulcan_dict.compress_to_binary(path, WINDOWS_STANDARD_DICT)
            processed.append((comp, size, mtime, ext, bmap))
        else:
            processed.append((path.encode('utf-8'), size, mtime, ext, bmap))
    conn.executemany("INSERT OR IGNORE INTO files (path, size, mtime, ext, bitmap) VALUES (?,?,?,?,?)", processed)
    conn.commit()

def search_files_turbo(conn, query_text, limit=30):
    mask, is_mappable = vulcan_bitmap.get_query_mask(query_text)
    
    if is_mappable and VLS_DLL.exists():
        # 1. Carrega todos os bitmaps do banco em um vetor binário (Rápido)
        # No N2808, 350k ints de 64 bits ocupam apenas 2.8 MB de RAM.
        cursor = conn.execute("SELECT bitmap FROM files")
        # 'Q' = unsigned long long (64 bits)
        bitmap_stream = array.array('Q', [row[0] for row in cursor])
        total = len(bitmap_stream)
        
        # 2. Prepara o buffer de resultados para o C
        res_buffer = array.array('i', [0] * total) # 'i' = int 32 bits
        
        # 3. DISPARO VULCAN (O C assume o controle)
        lib = ctypes.CDLL(str(VLS_DLL))
        match_count = lib.vls_filter_bitmaps(
            ctypes.cast(bitmap_stream.buffer_info()[0], ctypes.POINTER(ctypes.c_uint64)),
            ctypes.cast(res_buffer.buffer_info()[0], ctypes.POINTER(ctypes.c_int32)),
            total,
            mask
        )
        
        # 4. Busca os caminhos apenas para os IDs filtrados
        ids = res_buffer[:match_count][:limit]
        if not ids: return []
        
        placeholders = ",".join(["?"] * len(ids))
        rows = conn.execute(f"SELECT path, size FROM files WHERE id IN ({placeholders})", ids).fetchall()
        return [(get_real_path(r[0]), r[1]) for r in rows]

def search_files(conn, query_text, limit=30):
    """Busca ultra-rápida via Bitmap ou Fallback LIKE."""
    mask, is_mappable = vulcan_bitmap.get_query_mask(query_text)
    if is_mappable:
        sql = "SELECT path, size FROM files WHERE (bitmap & ?) == ? ORDER BY size DESC LIMIT ?"
        params = (mask, mask, limit)
    else:
        # Fallback usando CAST para pesquisar dentro do BLOB (mais lento)
        sql = "SELECT path, size FROM files WHERE CAST(path AS TEXT) LIKE ? ORDER BY size DESC LIMIT ?"
        params = (f"%{query_text}%", limit)
    
    rows = conn.execute(sql, params).fetchall()
    return [(get_real_path(r[0]), r[1]) for r in rows]

def get_top_files(conn, limit=20):
    """Retorna os maiores arquivos com descompressão em tempo real."""
    rows = conn.execute("SELECT path, size FROM files ORDER BY size DESC LIMIT ?", (limit,)).fetchall()
    return [(get_real_path(r[0]), r[1]) for r in rows]

def get_all_files(conn):
    """Gerador para análise de pastas (Exigido pelo DiskDiag)."""
    cursor = conn.execute("SELECT path, size FROM files")
    for row in cursor:
        yield (get_real_path(row[0]), row[1])

def get_extension_usage(conn, path_filter=None):
    """Agrupa uso por extensão (Exigido pelo DiskDiag)."""
    return conn.execute("SELECT ext, SUM(size) as total FROM files GROUP BY ext ORDER BY total DESC").fetchall()

def _format_size(size):
    """Auxiliar para o CLI."""
    if size is None: return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"
    
def find_duplicates(conn, min_size_kb=50):
    """
    Localiza clones potenciais usando a colisão de (Tamanho + Bitmap).
    Estratégia: Se dois arquivos têm o mesmo tamanho exato e o mesmo mapa de bits, 
    a probabilidade de serem idênticos é de 99.9%.
    """
    query = """
        SELECT path, size, bitmap FROM files 
        WHERE size > ? AND (size, bitmap) IN (
            SELECT size, bitmap FROM files 
            GROUP BY size, bitmap HAVING COUNT(*) > 1
        )
        ORDER BY size DESC
    """
    min_bytes = min_size_kb * 1024
    rows = conn.execute(query, (min_bytes,)).fetchall()
    
    # Agrupa por assinatura para exibição
    clones = {}
    for path, size, bmap in rows:
        sig = f"{size}_{bmap}"
        if sig not in clones: clones[sig] = []
        clones[sig].append(get_real_path(path))
        
    return clones
    