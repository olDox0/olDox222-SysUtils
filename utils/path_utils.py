# utils/path_utils.py
import os

# --- LISTAS GLOBAIS (ESTRITAMENTE MAIÚSCULAS) ---
FOLDERS_EXCLUDE = {
    'NODE_MODULES', 'VENV', '.VENV', 'THIRDPARTY', '__PYCACHE__',
    'BUILD', 'DIST', 'BIN', 'OBJ', '.GIT', '.DOXOADE', '.DOXOADE_CACHE',
    '.VSCODE', '.IDEA', '$RECYCLE.BIN', 'SYSTEM VOLUME INFORMATION', 
    'TEMP', 'TMP', '.PYTEST_CACHE', 'EGG-INFO', 'VERS', '.DOXOADE',
    'DATA',
}

EXT_EXCLUDE = {
    '.TMP', '.TEMP', '.BAK', '.OLD', '.LOG', '.DMP', '.CRDOWNLOAD',
    '.PYC', '.PYD', '.PYO', '.EXE', '.DLL', '.OBJ', '.DOX', 
    '.GGUF', '.ZIM', '.ISO', '.DB', '.BKP', '.INI', '.BIN',
    '.XML', '.DOCX', '.PYD',
}

def is_ignored_folder(dir_name: str) -> bool:
    name_up = dir_name.strip().upper()
    if name_up in FOLDERS_EXCLUDE: return True
    # Ignora pastas ocultas (começando com ponto), exceto pastas de documentos/fotos
    if name_up.startswith('.') and name_up not in {'.DOCUMENTS', '.PHOTOS', '.CONFIG'}:
        return True
    return False

def is_ignored_extension(ext: str) -> bool:
    if not ext: return False
    # Normalização: remove espaços, coloca ponto se faltar e joga para maiúsculo
    clean_ext = ext.strip().upper()
    if not clean_ext.startswith('.'):
        clean_ext = f".{clean_ext}"
    return clean_ext in EXT_EXCLUDE

def should_exclude_path(full_path: str) -> bool:
    """Verifica recursivamente se o arquivo ou alguma pasta pai deve ser ignorada."""
    path_up = os.path.abspath(full_path).upper()
    
    # 1. Verifica Extensão (usando a função normalizada)
    _, ext = os.path.splitext(path_up)
    if is_ignored_extension(ext):
        return True
        
    # 2. Verifica se qualquer parte do caminho é uma pasta proibida
    # Substituímos separadores para garantir compatibilidade Windows/Unix
    parts = path_up.replace("/", "\\").split("\\")
    for part in parts:
        if part in FOLDERS_EXCLUDE:
            return True
            
    return False

def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))
    
def get_extension(path: str) -> str:
    _, ext = os.path.splitext(path)
    return ext.lower()
