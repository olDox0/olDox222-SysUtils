# diskdiag/core/vulcan_search.py
import json
import sqlite3
import sys
import os

from pathlib import Path

# --- INJEÇÃO DE PATH VULCAN ---
# Garante que o motor encontre a pasta 'engine' na raiz do projeto
project_root = str(Path(__file__).parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ------------------------------

from diskdiag.core.tokenizer import tokenize_path
from engine.tools.inverted_index import InvertedIndexSearcher
from diskdiag.analysis.disk_analysis import _format_size

def run_vulcan_find(query_str, index_dir, sqlite_db, limit=15):
    idx_path = Path(index_dir)
    terms_path = idx_path / "terms.json"
    
    if not terms_path.exists():
        print("[ERRO] Índice não encontrado. Rode 'sysutils disk optimize' primeiro.")
        return

    # 1. Carrega o dicionário de termos (String -> ID)
    with open(terms_path, "r") as f:
        term_to_id = json.load(f)

    # 2. Tokeniza a busca do usuário
    query_tokens = tokenize_path(query_str)
    token_ids = [term_to_id[t] for t in query_tokens if t in term_to_id]

    if not token_ids:
        print(f"[INFO] Nenhum arquivo encontrado para: {query_str}")
        return

    # 3. Busca no Índice Binário (OLINE Tech)
    print(f"[VULCAN] Pesquisando binários por: {query_tokens}...")
    with InvertedIndexSearcher(idx_path) as searcher:
        # Usamos o algoritmo BM25 de relevância que já está na sua engine
        results = searcher.search_bm25(token_ids, limit=limit)

    if not results:
        print("[INFO] Nada encontrado no índice binário.")
        return

    # 4. Reconstrói os caminhos via SQLite (Staging Area)
    # Buscamos apenas os IDs que o índice retornou (muito rápido)
    doc_ids = [r["doc_id"] for r in results]
    conn = sqlite3.connect(sqlite_db)
    placeholders = ",".join(["?"] * len(doc_ids))
    
    # Mantemos a ordem de relevância do índice
    path_map = {row[0]: (row[1], row[2]) for row in conn.execute(
        f"SELECT id, path, size FROM files WHERE id IN ({placeholders})", doc_ids
    ).fetchall()}

    print("\n" + "="*60)
    print(f"{'RESULTADOS DA BUSCA VULCAN':^60}")
    print("="*60)
    print(f"  {'SCORE':<8} | {'TAMANHO':>10} | {'CAMINHO'}")
    print(f"  {'-'*8} | {'-'*10} | {'-'*35}")

    for r in results:
        doc_id = r["doc_id"]
        if doc_id in path_map:
            path, size = path_map[doc_id]
            print(f"  {r['score']:<8.2f} | {_format_size(size):>10} | {path}")
    
    print("="*60)