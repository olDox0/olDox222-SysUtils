# -*- coding: utf-8 -*-
# doxoade/commands/macrothon_systems/bricks/stress_tester.py
import time
import random
import hashlib

def generate_mock_paths(count=10000):
    """Gera massa de dados para teste de vazão."""
    prefixes = [
        "C:\\Windows\\System32\\",
        "C:\\Program Files\\Common Files\\Microsoft Shared\\",
        "C:\\Users\\olDox222\\AppData\\Local\\Temp\\",
        "C:\\Windows\\WinSxS\\amd64_microsoft-windows-servicingstack_"
    ]
    suffixes = [".dll", ".exe", ".sys", ".tmp", ".log", ".dat"]
    paths = []
    for _ in range(count):
        p = random.choice(prefixes)
        mid = "".join(random.choices("abcdef0123456789", k=12))
        s = random.choice(suffixes)
        paths.append(f"{p}{mid}{s}")
    return paths

def generate_edge_cases():
    """Gera casos de borda para teste de integridade."""
    return [
        "C:\\", 
        "C:\\Windows\\System32\\" + "A"*500 + ".dll",
        "C:\\Usuários\\Acentuação\\Documentos\\arquivo.txt",
        "C:\\Program Files\\Special!@#$%^&*()_+.vpk",
        ""
    ]

def verify_binary_integrity(original, recovered):
    """Garante que a reconstrução é idêntica no nível de hash."""
    if original is None or recovered is None: return False
    h1 = hashlib.sha256(original.encode('utf-8', errors='ignore')).hexdigest()
    h2 = hashlib.sha256(recovered.encode('utf-8', errors='ignore')).hexdigest()
    return h1 == h2