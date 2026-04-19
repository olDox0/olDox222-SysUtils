import os

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

def is_safe_to_delete(path):
    path_up = path.upper()
    
    # 1. Regra de Ouro: Se estiver em zona crítica, ignore
    for zone in CRITICAL_ZONES:
        if zone.upper() in path_up:
            return False
            
    # 2. Se for Temp de usuário, só limpamos se você estiver na "Zona de Documentos" 
    # ou se o arquivo for muito antigo (opcional).
    # Por segurança agora, vamos focar apenas no que o find revelou como "abandonado".
    return True

def classify_file(path: str, size: int) -> str:
    path_lower = path.lower()
    filename = os.path.basename(path_lower)
    _, ext = os.path.splitext(filename)

    if ext in JUNK_EXTENSIONS: return "junk"
    
    for pattern in HEAVY_DIR_PATTERNS:
        if (os.sep + pattern + os.sep) in path_lower or path_lower.endswith(os.sep + pattern):
            return "heavy"

    for name in JUNK_DIR_NAMES:
        if (os.sep + name + os.sep) in path_lower:
            return "junk"

    if size >= SIZE_LARGE: return "large"
    return "normal"

def category_label(category: str) -> str:
    labels = {"junk": "LIXO", "heavy": "PESADO", "large": "GRANDE", "normal": "OK"}
    return labels.get(category, category.upper())