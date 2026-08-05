# diskdiag/core/db_optimizer.py
import sqlite3
from diskdiag.core import vulcan_dict
from pathlib import Path

# Dicionário treinado previamente com padrões comuns do Windows
# No futuro, você pode treinar isso dinamicamente usando a House
WINDOWS_PATH_DICT = vulcan_dict.train_dictionary([
    "C:\\Windows\\System32\\",
    "C:\\Program Files\\",
    "C:\\Users\\",
    "AppData\\Local\\",
    ".exe", ".dll", ".sys", ".tmp"
])

def compress_database_paths(db_path):
    """
    Percorre o banco de dados e substitui caminhos planos 
    pela versão compactada com o vulcan_dict.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("[VULCAN] Iniciando compressão de caminhos no banco...")
    
    # 1. Busca todos os caminhos
    files = cursor.execute("SELECT id, path FROM files").fetchall()
    
    updated_count = 0
    for file_id, raw_path in files:
        # Só compactamos se o caminho for longo o suficiente para valer a pena
        if len(raw_path) > 20:
            compressed = vulcan_dict.compress_with_dict(raw_path, WINDOWS_PATH_DICT)
            
            # Marcamos com um prefixo [V!] para o descompactador saber
            cursor.execute("UPDATE files SET path = ? WHERE id = ?", (f"[V!]{compressed}", file_id))
            updated_count += 1
            
    conn.commit()
    conn.close()
    print(f"[SUCESSO] {updated_count} caminhos otimizados com Vulcan Dictionary.")

def decompress_path(compressed_path):
    """Lógica de leitura transparente."""
    if compressed_path.startswith("[V!]"):
        pure_data = compressed_path.replace("[V!]", "")
        return vulcan_dict.decompress_with_dict(pure_data, WINDOWS_PATH_DICT)
    return compressed_path