from diskdiag.core.storage import init_db, get_top_files, get_extension_usage, get_all_files
from diskdiag.analysis.heuristics import classify_file, category_label

def _format_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

def show_cleanup_candidates(conn):
    print("\n" + "="*40 + "\n CANDIDATOS PARA LIMPEZA \n" + "="*40)
    results = []
    for path, size in get_all_files(conn):
        cat = classify_file(path, size)
        if cat in ("junk", "heavy", "large"):
            results.append((path, size, cat))
    
    results.sort(key=lambda x: x[1], reverse=True)
    for path, size, cat in results[:20]:
        print(f"  {_format_size(size):>10} | {category_label(cat):<7} | {path}")

def run_analysis(db_path):
    conn = init_db(db_path)
    print(f"\n[INFO] Analisando banco: {db_path}")
    
    # Maiores arquivos
    print("\n--- TOP 10 MAIORES ---")
    for path, size in get_top_files(conn, 10):
        print(f"  {_format_size(size):>10} | {path}")
        
    show_cleanup_candidates(conn)