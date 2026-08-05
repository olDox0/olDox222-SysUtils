import os
import time
from collections import deque
from utils.path_utils import normalize_path, get_extension
from utils.file_utils import safe_stat
from diskdiag.core.storage import init_db, insert_files

def run_indexer(root_path, db_path):
    root_path = normalize_path(root_path)
    conn = init_db(db_path)
    
    print(f"[INFO] Iniciando varredura em: {root_path}")
    stack = deque([root_path])
    batch = []
    total = 0

    while stack:
        curr = stack.pop()
        try:
            with os.scandir(curr) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        stat = safe_stat(entry.path)
                        if stat:
                            batch.append((entry.path, stat.st_size, stat.st_mtime, get_extension(entry.path)))
                            total += 1
                    
                    if len(batch) >= 1000:
                        insert_files(conn, batch)
                        batch = []
        except PermissionError:
            continue

    if batch:
        insert_files(conn, batch)
    print(f"[SUCESSO] {total} arquivos indexados.")
    
def prune_database(db_path, root_filter=None):
    """Remove do banco de dados os arquivos que não existem mais no disco."""
    import sqlite3
    from diskdiag.core.storage import get_real_path
    
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT id, path FROM files")
    rows = cursor.fetchall()
    
    ids_to_delete = []
    checked = 0
    
    print(f"[SYNC] Iniciando auditoria de integridade em {len(rows)} registros...")
    
    for row_id, raw_path in rows:
        real_path = get_real_path(raw_path)
        if not real_path:
            ids_to_delete.append(row_id)
            continue
            
        # Se houver um filtro de raiz, só verifica arquivos dentro dela
        if root_filter:
            if not os.path.abspath(real_path).startswith(os.path.abspath(root_filter)):
                continue
                
        if not os.path.exists(real_path):
            ids_to_delete.append(row_id)
            
        checked += 1
        if checked % 5000 == 0:
            print(f"  [SYNC] Verificados {checked} registros...")

    if ids_to_delete:
        # Deleta em lotes para não travar o SQLite (Otimização Hades)
        for i in range(0, len(ids_to_delete), 1000):
            batch = ids_to_delete[i:i+1000]
            conn.executemany("DELETE FROM files WHERE id = ?", [(i,) for i in batch])
        conn.commit()
        print(f"[SUCESSO] {len(ids_to_delete)} registros fantasmas removidos do banco.")
    else:
        print("[INFO] Nenhum registro fantasma encontrado. Banco está limpo.")
    conn.close()