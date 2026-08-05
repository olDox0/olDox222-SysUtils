# diskdiag/analysis/disk_analysis.py

from collections import defaultdict
import os
from diskdiag.core.storage import init_db, get_top_files, get_all_files, get_extension_usage, get_real_path
from utils.doxcolors import colors

def _format_size(size):
    if size is None: return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

def show_top_folders(conn, limit=15):
    """Calcula o tamanho total de cada pasta baseada nos arquivos indexados."""
    print("\n" + "="*60 + "\n ANÁLISE DE PASTAS MAIS PESADAS \n" + "="*60)
    folder_sizes = defaultdict(int)
    
    for path, size in get_all_files(conn):
        parent = os.path.dirname(path)
        # Sobe a árvore de diretórios somando o tamanho
        while parent and len(parent) > 3: # Para no drive (ex: C:\)
            folder_sizes[parent] += size
            parent = os.path.dirname(parent)

    sorted_folders = sorted(folder_sizes.items(), key=lambda x: x[1], reverse=True)
    
    print(f"  {'TAMANHO':>10} | {'CAMINHO DA PASTA'}")
    print("  " + "-"*70)
    for folder, size in sorted_folders[:limit]:
        print(f"  {_format_size(size):>10} | {folder}")

def show_cleanup_candidates(conn, limit=12):
    """Identifica e categoriza candidatos a limpeza com segurança."""
    print("\n" + "="*70)
    print(f"{colors.UI.gradient_text(' ANÁLISE DE SEGURANÇA E LIMPEZA VULCAN '):^70}")
    print("="*70)
    query = """
    SELECT path, size, ext FROM files
    WHERE ext IN ('.tmp', '.log', '.bak', '.old', '.dmp', '.crdownload', '.driveupload')
    OR size > 104857600
    ORDER BY size DESC LIMIT ?
    """
    candidates = conn.execute(query, (limit,)).fetchall()
    if not candidates:
        print(f"  {colors.Fore.SUCCESS}[OK]{colors.Fore.RESET} Nenhum risco imediato encontrado.")
        return
        
    print(f"  {'TIPO':<10} | {'TAMANHO':>10} | {'RECOMENDAÇÃO / CAMINHO'}")
    print("  " + "-"*75)
    
    for raw_path, size, ext in candidates:
        # [FIX] Descomprime/Decodifica o BLOB para string real antes de analisar
        path = get_real_path(raw_path)
        path_up = path.upper()
        
        if "C:\\WINDOWS" in path_up or "PAGEFILE.SYS" in path_up or "WINDOWS.EDB" in path_up:
            tag = f"{colors.Fore.ERROR}SISTEMA{colors.Fore.RESET}"
            advice = f"{colors.Fore.DIM}[NÃO DELETAR - CRÍTICO]{colors.Fore.RESET}"
        elif any(x in path_up for x in ['.TMP', '.LOG', '.BAK', '.DRIVEUPLOAD', 'RECYCLE.BIN']):
            tag = f"{colors.Fore.SUCCESS}LIXO{colors.Fore.RESET}"
            advice = f"{colors.Fore.GREEN}[SEGURO PARA LIMPAR]{colors.Fore.RESET}"
        else:
            tag = f"{colors.Fore.WARNING}PESADO{colors.Fore.RESET}"
            advice = f"{colors.Fore.YELLOW}[ANALISAR MANUALMENTE]{colors.Fore.RESET}"
            
        print(f"  {tag:<19} | {_format_size(size):>10} | {advice}")
        print(f"             └─ {colors.Fore.DIM}{path}{colors.Fore.RESET}")
        
    print("\n" + colors.Fore.DIM + "DICA: Use 'sysutils win maintenance' para limpar arquivos de SISTEMA com segurança." + colors.Fore.RESET)

def show_extension_analysis(conn, path_filter=None, limit=20):
    header = "ANÁLISE POR TIPO DE ARQUIVO"
    if path_filter: header += f" EM: {path_filter}"
    print("\n" + "="*60 + f"\n {header} \n" + "="*60)
    
    results = get_extension_usage(conn, path_filter=path_filter)
    print(f"  {'EXTENSÃO':<10} | {'TAMANHO TOTAL'}")
    print("  " + "-"*35)
    
    for ext, size in results[:limit]:
        display_ext = ext if ext else "SEM EXT"
        print(f"  {display_ext:<10} | {_format_size(size):>12}")

def run_analysis(db_path, path_filter=None, analyze_folders=False, analyze_extensions=False):
    """Orquestrador da análise de disco."""
    conn = init_db(db_path)
    
    if analyze_extensions:
        show_extension_analysis(conn, path_filter=path_filter)
    elif analyze_folders:
        show_top_folders(conn)
    else:
        print("\n--- TOP 10 MAIORES ARQUIVOS ---")
        for path, size in get_top_files(conn, 10):
            print(f"  {_format_size(size):>10} | {path}")
        
        # AGORA A FUNÇÃO EXISTE:
        show_cleanup_candidates(conn)