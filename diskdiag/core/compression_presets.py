# -*- coding: utf-8 -*-
from . import vulcan_dict

# A ORDEM É SAGRADA: Novos itens devem entrar apenas no FINAL da lista.
VULCAN_LEXICON = [
    "C:\\Windows\\", "System32", "Program Files", "AppData\\Local\\", "AppData\\Roaming\\", 
    "Microsoft\\", "WinSxS\\", "amd64_", "servicingstack_", "drivers", "utils", "diskdiag", 
    "core", "cli", "bloatbreaker", "doxbackup", "venv", ".py", ".dll", ".exe", ".sys", 
    ".log", ".bak", ".tmp", ".json", "google", "chrome", "users", "common"
]

# Dicionário estático para o motor Zlib
WINDOWS_STANDARD_DICT = vulcan_dict.train_dictionary(VULCAN_LEXICON)