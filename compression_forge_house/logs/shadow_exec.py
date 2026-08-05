import time, sys
from doxoade.tools.telemetry_tools.logger import chief_heartbeat
if '_MACRO_METRICS' not in globals(): _MACRO_METRICS = []

# Macrothon Blueprint: compression_forge


# 1. Massa de Dados e Dicionário
print(Fore.CYAN + "[*] Iniciando Auditoria de Integridade Binária...")
data = generate_mock_paths(5000) + generate_edge_cases()
my_dict = TRAIN(data)

# 2. Ciclo de Auditoria
total_tested = 0
failed_hashes = 0

for path in data:
    total_tested += 1
    
    # Compressão
    compressed = COMPRESS(path, my_dict)
    
    # Descompressão
    recovered = DECOMPRESS(compressed, my_dict)
    
    # Teste de colisão SHA-256
    if not verify_binary_integrity(path, recovered):
        failed_hashes += 1

# 3. Laudo Técnico
if failed_hashes == 0:
    print(Fore.GREEN + "\n✅ LAUDO: TECNOLOGIA 100% LOSSLESS")
    print(Fore.WHITE + "   Amostras: " + str(total_tested))
    print(Fore.WHITE + "   Integridade Criptográfica: Válida")
    print(Fore.YELLOW + "   Risco de Corrupção: Zero (0.000%)")
else:
    print(Fore.RED + "\n✘ ALERTA: CORRUPÇÃO DETECTADA EM " + str(failed_hashes) + " CASOS!")
    
# No final do seu Blueprint compression_forge.macrothon
print(Fore.CYAN + "\n--- AMOSTRA TÉCNICA (ORIGINAL vs COMPACTADO) ---")
for i in range(5):
    path = data[i]
    comp = COMPRESS(path, my_dict)
    print(Fore.WHITE + "  ORG: " + path)
    print(Fore.GREEN + "  V! : " + comp)
    print(Style.DIM + "  " + "-" * 50)