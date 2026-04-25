# cli/rescue.py
import sys
import os
import click
from utils.doxcolors import Fore, Style, init

init(autoreset=True)

def analyze_crash(traceback_text):
    lines = traceback_text.splitlines()
    info = {'error': lines[-1] if lines else 'Unknown', 'file': None, 'line': None}
    for line in reversed(lines):
        if 'File "' in line:
            parts = line.split('"')
            info['file'] = parts[1]
            info['line'] = line.split('line ')[1].split(',')[0]
            break
    return info

def activate_protocol(error_text):
    click.clear()
    print(Fore.RED + Style.BRIGHT + "!" * 60)
    print("   [SISTEMA RESGATE: PROTOCOLO LAZARUS ATIVADO]")
    print("!" * 60)
    
    info = analyze_crash(error_text)
    
    click.secho(f"\nFALHA CRÍTICA: {info['error']}", fg='red', bold=True)
    click.echo(f"LOCAL: {info['file']} (Linha {info['line']})")
    
    print(f"\n{Fore.WHITE}--- OPÇÕES DE EMERGÊNCIA ---")
    print(f"{Fore.YELLOW}1.{Fore.RESET} Reverter arquivo via Git (se disponível)")
    print(f"{Fore.YELLOW}2.{Fore.RESET} Abrir código no Notepad++ para correção")
    print(f"{Fore.YELLOW}3.{Fore.RESET} Mostrar Traceback completo")
    
    choice = click.prompt("\nEscolha uma opção", type=int, default=3)
    
    if choice == 1:
        os.system(f"git checkout {info['file']}")
        click.secho("Arquivo revertido para o último commit estável.", fg='green')
    elif choice == 2:
        npp = r"C:\Program Files\Notepad++\notepad++.exe"
        if os.path.exists(npp):
            subprocess.Popen([npp, "-n" + str(info['line']), info['file']])
        else:
            os.system(f"notepad {info['file']}")
    else:
        print(f"\n{Fore.RED}{error_text}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            activate_protocol(f.read())