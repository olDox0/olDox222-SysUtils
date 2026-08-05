# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]
# -*- coding: utf-8 -*-
# test_vulcan_real.py
import os
import sys
from diskdiag.core import vulcan_dict
from utils.doxcolors import Fore, Style

def run_integration_test():
    print(f"{Fore.CYAN}🚀 [INTEGRATION TEST] Testando VulcanDict com dados REAIS...{Style.RESET_ALL}")

    # 1. Coleta caminhos reais do seu diretório atual
    real_paths = []
    for root, _, files in os.walk("."):
        for f in files:
            full_p = os.path.join(root, f)
            real_paths.append(full_p)
            if len(real_paths) >= 100: break
        if len(real_paths) >= 100: break

    # 2. Treina o dicionário com a sua estrutura de pastas
    print(f"[*] Treinando com {len(real_paths)} arquivos locais...")
    my_dict = vulcan_dict.train_dictionary(real_paths)

    # 3. Teste Visual
    target = real_paths[0] # Pega o primeiro arquivo (ex: ./main.py)
    compressed = vulcan_dict.compress_with_dict(target, my_dict)
    recovered = vulcan_dict.decompress_with_dict(compressed, my_dict)

    print(f"\n{Fore.YELLOW}RESULTADO VISUAL:{Style.RESET_ALL}")
    print(f"  Entrada : {target}")
    print(f"  Saída   : {Fore.GREEN}V!{compressed}{Style.RESET_ALL}")
    print(f"  Retorno : {recovered}")

    # 4. Verificação de integridade total
    print(f"\n[*] Validando integridade de toda a massa...")
    success = True
    for p in real_paths:
        c = vulcan_dict.compress_with_dict(p, my_dict)
        r = vulcan_dict.decompress_with_dict(c, my_dict)
        if r != p:
            print(f"{Fore.RED}✘ FALHA EM: {p}{Style.RESET_ALL}")
            success = False
            break
    
    if success:
        print(f"{Fore.GREEN}✅ SUCESSO ABSOLUTO: Todos os caminhos reais foram recuperados sem perdas.{Style.RESET_ALL}")

if __name__ == "__main__":
    run_integration_test()