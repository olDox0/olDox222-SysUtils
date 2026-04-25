# install.py
import os
import sys
import subprocess
import shutil

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def main():
    print("--- [VULCAN] Reparador e Instalador SysUtils ---")
    
    # 1. Tentar reparar o pip corrompido
    print("[1/3] Verificando integridade do PIP...")
    repair_pip = [sys.executable, "-m", "ensurepip", "--upgrade"]
    subprocess.run(repair_pip, capture_output=True)
    
    # 2. Garantir que __init__.py existam
    print("[2/3] Verificando estruturas de pacotes...")
    for folder in ['netdiag', 'sysdiag', 'diskdiag', 'ramdiag', 'doxbackup', 'bloatbreaker', 'cli']:
        init_file = os.path.join(folder, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f: pass
            print(f"  [+] Criado {init_file}")

    # 3. Instalar via PIP
    print("[3/3] Registrando comando 'sysutils'...")
    try:
        # Tentativa direta de instalação editável
        cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
        result = subprocess.run(cmd, check=True)
        print("\n" + "="*50)
        print("[SUCESSO] SysUtils Chief-Gold instalado!")
        print("Digite 'sysutils' para testar.")
        print("="*50)
    except subprocess.CalledProcessError:
        print("\n[ERRO] O PIP ainda está falhando.")
        print("Tente resetar o venv: python -m venv venv --clear")

if __name__ == '__main__':
    main()