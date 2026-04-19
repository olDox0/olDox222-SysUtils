# diskdiag/analysis/disk_analysis.py

from collections import defaultdict
import os
from diskdiag.core.storage import init_db, get_top_files, get_all_files, get_extension_usage
from diskdiag.analysis.heuristics import classify_file, category_label

def _format_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

def show_top_folders(conn, limit=15):
    """Calcula o tamanho total de cada pasta baseada nos arquivos indexados."""
    print("\n" + "="*40 + "\n ANÁLISE DE PASTAS MAIS PESADAS \n" + "="*40)
    folder_sizes = defaultdict(int)
    
    # Agrega o tamanho de cada arquivo para todos os seus diretórios pais
    for path, size in get_all_files(conn):
        parent = os.path.dirname(path)
        # Adiciona o tamanho para a pasta imediata e todas as pastas acima dela
        while parent and parent != os.path.dirname(parent):
            folder_sizes[parent] += size
            parent = os.path.dirname(parent)

    # Ordena por tamanho
    sorted_folders = sorted(folder_sizes.items(), key=lambda x: x[1], reverse=True)
    
    print(f"  {'TAMANHO':>10} | {'CAMINHO DA PASTA'}")
    print("  " + "-"*60)
    for folder, size in sorted_folders[:limit]:
        print(f"  {_format_size(size):>10} | {folder}")

def show_extension_analysis(conn, path_filter=None, limit=20):
    header = "ANÁLISE POR TIPO DE ARQUIVO"
    if path_filter: header += f" EM: {path_filter}"
    
    print("\n" + "="*60 + f"\n {header} \n" + "="*60)
    
    results = get_extension_usage(conn, path_filter=path_filter)
    
    print(f"  {'EXTENSÃO':<10} | {'TAMANHO TOTAL'}")
    print("  " + "-"*30)
    
    for ext, size in results[:limit]:
        # Trata arquivos sem extensão
        display_ext = ext if ext else "SEM EXT"
        print(f"  {display_ext:<10} | {_format_size(size):>12}")

# Atualizando o orquestrador run_analysis
def run_analysis(db_path, path_filter=None, analyze_folders=False, analyze_extensions=False):
    conn = init_db(db_path)
    # Se o usuário passou um path, normalizamos para garantir o match no banco
    from utils.path_utils import normalize_path
    p_filter = normalize_path(path_filter) if path_filter else None
    
    if analyze_extensions:
        show_extension_analysis(conn, path_filter=p_filter)
    elif analyze_folders:
        # Aquela função que fizemos anteriormente
        from diskdiag.analysis.disk_analysis import show_top_folders # Caso esteja em outro local
        show_top_folders(conn)
    else:
        print("\n--- TOP 10 MAIORES ARQUIVOS ---")
        for path, size in get_top_files(conn, 10):
            print(f"  {_format_size(size):>10} | {path}")
        show_cleanup_candidates(conn)