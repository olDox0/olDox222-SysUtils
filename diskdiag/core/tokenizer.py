# diskdiag/core/tokenizer.py
import re

def tokenize_path(path):
    # Remove a letra da unidade e quebra por separadores comuns
    path = path.lower()
    tokens = re.split(r'[\\/._ \-]', path)
    # Filtra tokens vazios ou muito curtos
    return [t for t in tokens if len(t) > 1]