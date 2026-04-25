# diskdiag/analysis/heuristics.py

import os
from utils.path_utils import should_exclude_path, is_ignored_extension

JUNK_EXTENSIONS = {".tmp", ".temp", ".bak", ".old", ".log", ".dmp", ".swp", ".crdownload"}
JUNK_DIR_NAMES = {"temp", "tmp", "logs", "$recycle.bin", ".trash"}
HEAVY_DIR_PATTERNS = {"node_modules", "__pycache__", "venv", ".venv", ".git", "build", "dist"}
SIZE_LARGE = 200 * 1024 * 1024  # 200 MB
CRITICAL_ZONES = [
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"AppData\Local\Microsoft", # Cache de busca e telemetria sensível
]

NON_BACKUP_PATTERNS = [
    "APPDATA\\LOCAL\\TEMP",
    "APPDATA\\LOCAL\\GOOGLE\\CHROME\\USER DATA\\DEFAULT\\CACHE",
    "__PYCACHE__",
    "NODE_MODULES",
    ".VENV",
    "VENV",
    ".GIT"
]

BACKUP_IGNORE_EXT = {
    ".tmp", ".temp", ".bak", ".old", ".log", ".dmp", ".swp", ".crdownload",
    ".pyc", ".pyd", ".obj", ".node", ".dox", ".iso", ".bin"
}

def should_exclude_from_backup(path):
    """Retorna True se o caminho bater com algum padrão de exclusão."""
    path_up = path.upper()
    parts = path_up.replace("/", "\\").split("\\")
    
    # 1. Verifica se alguma pasta no caminho está na lista negra
    if any(p in GLOBAL_EXCLUDE_DIRS for p in parts):
        return True
            
    # 2. Verifica extensão
    _, ext = os.path.splitext(path_up)
    if ext.lower() in BACKUP_IGNORE_EXT:
        return True
            
    return False

def is_safe_to_delete(path):
    """Regra de ouro: Nunca limpar nada em Windows ou Program Files."""
    path_up = path.upper()
    if "C:\\WINDOWS" in path_up or "PROGRAM FILES" in path_up:
        return False
    return True

def classify_file(path: str, size: int) -> str:
    """Classifica o arquivo baseando-se no filtro global e no tamanho."""
    # Se o filtro global ignorar, é lixo (Junk)
    if should_exclude_path(path):
        return "junk"

    # Se for muito grande (>200MB)
    if size >= (200 * 1024 * 1024): 
        return "large"
        
    return "normal"

def category_label(category: str) -> str:
    labels = {"junk": "LIXO", "heavy": "PESADO", "large": "GRANDE", "normal": "OK"}
    return labels.get(category, category.upper())
    
def should_ignore_dir(dir_name):
    """Verifica se uma pasta específica deve ser ignorada pelo nome."""
    name_up = dir_name.upper()
    # Ignora se estiver na lista ou se for uma pasta oculta de sistema/ferramenta
    if name_up in GLOBAL_EXCLUDE_DIRS:
        return True
    if name_up.startswith('.') and name_up not in {".DOCUMENTS", ".PHOTOS"}: # Proteção básica
        return True
    return False

def should_exclude_file(file_path):
    """Verifica se o arquivo individual deve ser ignorado."""
    path_up = file_path.upper()
    
    # 1. Checa extensões de lixo
    BACKUP_IGNORE_EXT = {".TMP", ".TEMP", ".BAK", ".OLD", ".LOG", ".PYC", ".PYX", ".DOX"}
    _, ext = os.path.splitext(path_up)
    if ext in BACKUP_IGNORE_EXT:
        return True
        
    # 2. Checa se o arquivo está dentro de alguma pasta proibida (redundância de segurança)
    parts = path_up.replace("/", "\\").split("\\")
    if any(p in GLOBAL_EXCLUDE_DIRS for p in parts):
        return True
        
    return False
