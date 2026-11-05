# debug_sleepstudy.py
import re
from pathlib import Path
from bs4 import BeautifulSoup

def analyze_html(file_path):
    print(f"--- DIAGNÓSTICO DO ARQUIVO: {file_path} ---")
    path = Path(file_path)
    if not path.exists():
        print("Arquivo não encontrado.")
        return

    # Tenta ler em UTF-8 e UTF-16
    for enc in ["utf-8", "utf-16"]:
        try:
            content = path.read_text(encoding=enc, errors="ignore")
            if len(content) > 1000:
                print(f"[OK] Lido com encoding: {enc}")
                break
        except:
            continue
    else:
        print("Não foi possível ler o arquivo.")
        return

    print(f"Tamanho do arquivo: {len(content)} caracteres")

    # 1. Remove scripts e styles
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    
    text_clean = soup.get_text(separator="\n", strip=True)
    print(f"Tamanho do texto limpo: {len(text_clean)} caracteres")

    # 2. Procura por palavras-chave
    keywords = ["Drain", "Top Offenders", "Percent", "Active Time", "Energy"]
    for kw in keywords:
        idx = text_clean.find(kw)
        if idx != -1:
            print(f"\n[ENCONTRADO] Palavra '{kw}' na posição {idx}")
            print("Contexto (500 caracteres antes e depois):")
            print("-" * 60)
            start = max(0, idx - 500)
            end = min(len(text_clean), idx + 500)
            print(text_clean[start:end])
            print("-" * 60)
            break
    else:
        print("\n[AVISO] Nenhuma das palavras-chave foi encontrada no texto limpo.")

    # 3. Procura por '%' no texto limpo
    idx_pct = text_clean.find("%")
    if idx_pct != -1:
        print(f"\n[ENCONTRADO] Símbolo '%' na posição {idx_pct}")
        print("Contexto (300 caracteres antes e depois):")
        print("-" * 60)
        start = max(0, idx_pct - 300)
        end = min(len(text_clean), idx_pct + 300)
        print(text_clean[start:end])
        print("-" * 60)
    else:
        print("\n[AVISO] Nenhum símbolo '%' encontrado no texto limpo.")

    # 4. Conta quantas tabelas existem
    tables = soup.find_all("table")
    print(f"\nNúmero de tabelas encontradas: {len(tables)}")
    for i, table in enumerate(tables[:3]): # Mostra as 3 primeiras
        rows = table.find_all("tr")
        print(f"  Tabela {i+1}: {len(rows)} linhas")
        if rows:
            first_row_cells = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]
            print(f"    Cabeçalho: {first_row_cells}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        analyze_html(sys.argv[1])
    else:
        print("Uso: python debug_sleepstudy.py <caminho_do_arquivo>")