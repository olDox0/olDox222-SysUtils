# diskdiag/core/cleaner.py
import sys
import os
import time
from pathlib import Path

from diskdiag.analysis.heuristics import should_exclude_from_backup

# --- INJEÇÃO DE PATH VULCAN ---
project_root = str(Path(__file__).parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ------------------------------

from engine.native.cleaner_helper import vulcan_batch_delete
from diskdiag.analysis.disk_analysis import _format_size

def is_safe(path):
    """
    Reforço de Segurança Vulcan.
    """
    # Se o arquivo deve ser excluído de operações de backup/preservação (é lixo)
    # Então, no contexto do CLEANER, ele é "safe" (seguro) para deletar.
    # Mas cuidado: aqui a lógica inverte. 
    
    path_up = path.upper()
    
    # Proteção absoluta: Nunca mexer no banco do próprio sistema
    if "FILES.DB" in path_up or "VULCAN_IDX" in path_up:
        return False

    # Se estiver em Windows ou Program Files, NÃO é seguro deletar
    if any(zone in path_up for zone in ["C:\\WINDOWS", "PROGRAM FILES"]):
        return False

    return True

def run_safe_cleanup(db_path, dry_run=True):
    import sqlite3
    from utils.vulcan_build import ensure_native_engine
    
    ensure_native_engine("vulcan_cleaner.dll")
    conn = sqlite3.connect(db_path)
    
    # Raw string r""" resolve o SyntaxWarning: invalid escape sequence '\T'
    query = r"""
    SELECT id, path, size FROM files 
    WHERE path LIKE '%\$RECYCLE.BIN\%' 
       OR path LIKE '%__pycache__%'
       OR ext IN ('.tmp', '.log', '.bak')
    """
    
    candidates = conn.execute(query).fetchall()
    valid_paths = []
    total_size = 0

    for _, path, size in candidates:
        if is_safe(path):
            valid_paths.append(path)
            total_size += size

    if not valid_paths:
        print("[INFO] Nenhum arquivo seguro para limpeza foi encontrado.")
        return

    if dry_run:
        # F-string corrigida (f"...") para o título
        print("\n" + "="*75)
        print(f"{f'MOSTRANDO PRIMEIROS 20 DE {len(valid_paths)} CANDIDATOS':^75}")
        print("="*75)
        for p in valid_paths:
            print(f"  [CANDIDATO] | {p}")
        print("...")
        print("="*75)
        print(f"RESUMO: {len(valid_paths)} arquivos | TOTAL: {_format_size(total_size)}")
        print(f"[AVISO] Modo Simulação. Use --force para disparar a limpeza assíncrona em C.")
    else:
        # ALTA PERFORMANCE: Sem prints dentro do processamento
        print(f"[VULCAN] Iniciando Batch Shredder em C para {len(valid_paths)} arquivos...")
        
        start_t = time.perf_counter()
        
        # Chama a DLL compilada (Parallel Threaded Delete)
        deleted_count = vulcan_batch_delete(valid_paths)
        
        end_t = time.perf_counter()
        
        print("\n" + "="*75)
        print(f"{'LIMPEZA NATIVA CONCLUÍDA':^75}")
        print("="*75)
        print(f"  Arquivos removidos:    {deleted_count}")
        print(f"  Espaço total liberado: {_format_size(total_size)}")
        print(f"  Tempo de execução:     {end_t - start_t:.4f}s")
        print("="*75)

    if not dry_run:
        print(f"[VULCAN] Executando e Sincronizando...")
        
        # 1. Chama o C e recebe quais caminhos foram apagados
        # (cleaner_helper deve ser ajustado para retornar a lista de sucessos)
        deleted_paths = vulcan_batch_delete_with_feedback(valid_paths)
        
        # 2. Auto-Sync: Remove do SQLite apenas o que foi apagado de verdade
        if deleted_paths:
            conn.executemany("DELETE FROM files WHERE path = ?", [(p,) for p in deleted_paths])
            conn.commit()
            print(f"[SYNC] {len(deleted_paths)} registros removidos do banco local.")

def run_cleanup(db_path, dump=True):
    import sqlite3
    
    conn = sqlite3.connect(db_path)
    print(f"[CLEANUP] Analisando candidatos a remoção...")

    # Buscamos arquivos que batem com padrões de lixo conhecidos
    # E também tudo que está na Lixeira ou em pastas Temp
    query = r"""
    SELECT id, path, size FROM files 
    WHERE path LIKE '%$RECYCLE.BIN%' 
       OR path LIKE r'%\Temp\%'
       OR ext IN ('.tmp', '.log', '.pyc', '.bak')
    """
    
    candidates = conn.execute(query).fetchall()
    
    total_trash_size = 0
    count = 0
    
    if dump:
        print("\n" + "="*70)
        print(f"{'DUMP DE LIMPEZA - ARQUIVOS IDENTIFICADOS':^70}")
        print("="*70)
        print(f"  {'TAMANHO':>10} | {'CAMINHO'}")
        print(f"  {'-'*10} | {'-'*55}")

    for _, path, size in candidates:
        # Validação extra via heurística
        cat = classify_file(path, size)
        if cat in ("junk", "heavy") or "$RECYCLE.BIN" in path.upper() or "\\TEMP\\" in path.upper():
            if dump:
                print(f"  {_format_size(size):>10} | {path}")
            total_trash_size += size
            count += 1

    print("="*70)
    print(f"[SUMÁRIO]")
    print(f"  Arquivos encontrados: {count}")
    print(f"  Espaço recuperável:  {_format_size(total_trash_size)}")
    print("="*70)
    
    if dump:
        print("\n[DICA] Para apagar de verdade, precisaremos implementar a flag --force.")
        print("Por enquanto, o Doxoade Vulcan recomenda apenas o --dump para segurança.")