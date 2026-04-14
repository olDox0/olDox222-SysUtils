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