# diskdiag/core/vulcan_index.py

from pathlib import Path

import sqlite3
import sys
import os

project_root = str(Path(__file__).parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from diskdiag.core.storage import get_all_files, init_db
from diskdiag.core.storage import init_db
from diskdiag.core.tokenizer import tokenize_path
from engine.tools.inverted_index import InvertedIndexBuilder



def compress_db_to_vulcan(sqlite_db_path, output_dir):
    conn = init_db(sqlite_db_path)
    builder = InvertedIndexBuilder()
    
    # Mapeamento de termos para IDs (para economizar no builder)
    term_to_id = {}
    next_term_id = 0
    
    print(f"[VULCAN] Lendo registros do SQLite...")
    files = conn.execute("SELECT id, path, size FROM files").fetchall()
    
    for doc_id, path, size in files:
        tokens = tokenize_path(path)
        token_ids = []
        
        for t in tokens:
            if t not in term_to_id:
                term_to_id[t] = next_term_id
                next_term_id += 1
            token_ids.append(term_to_id[t])
            
        # Adiciona ao índice binário
        builder.add_document(doc_id, token_ids)

    print(f"[VULCAN] Gerando arquivos binários em {output_dir}...")
    dest = Path(output_dir)
    builder.write(dest)
    
    # Salva o mapa de termos para o Searcher conseguir traduzir queries
    import json
    with open(dest / "terms.json", "w") as f:
        json.dump(term_to_id, f)
        
    print(f"[SUCESSO] Índice Vulcan gerado. Termos únicos: {next_term_id}")