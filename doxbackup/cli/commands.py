# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

# doxbackup/cli/commands.py

import click
import os
import time
import traceback
from utils.doxcolors import colors, NexusUI

from pathlib import Path
SYS_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = str(SYS_ROOT / "data" / "db" / "files.db")

from utils.doxcolors import colors, NexusUI


@click.group()
def cli():
    """DoxBackup — Sistema de backup eficiente e seguro."""
    pass

@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", default="backup.dox", help="Nome do arquivo de saída.")
@click.option("--quantum", is_flag=True, help="Ativa Criptografia Híbrida Pós-Quântica.")
@click.option("--hint", default="", help="Dica de senha.")
@click.password_option(prompt="Defina a senha do container", confirmation_prompt=True)
def pack(source, output, quantum, hint, password):
    """Cria um container de backup ultra-seguro e otimizado."""
    from doxbackup.core.engine import run_quantum_backup, get_file_list
    
    source_path = Path(source).resolve()
    
    # Efeito inicial de decodificação no título
    NexusUI.decode_effect("SISTEMA DE BACKUP VULCAN V3", duration=0.4)
    
    click.echo(f"{colors.Fore.PRIMARY}[VULCAN]{colors.Fore.RESET} Analisando: {source_path}")
    
    # Coleta de arquivos (fase rápida)
    files = get_file_list(str(source_path))
    
    if not files:
        click.secho("[AVISO] Nenhum arquivo válido encontrado.", fg="yellow")
        return

    # --- INÍCIO DA ANIMAÇÃO ASSÍNCRONA ---
    # Carregamos os frames do arquivo .nxa
    # Se o arquivo não existir, o AsyncAnimation lida graciosamente
    animation_path = SYS_ROOT / "data" / "assets" / "backup_processing.nxa" #animation_path = os.path.join("data", "assets", "backup_processing.nxa")
    
    # Se não tiver o arquivo .nxa, podemos usar frames manuais simples
    frames = NexusUI.load_animation(str(animation_path)) or [" [■□□] ", " [■■□] ", " [■■■] "] #    frames = NexusUI.load_animation(animation_path) or [" [■□□] ", " [■■□] ", " [■■■] "]

    click.echo(f"{colors.Fore.CYAN}Preparando compressão de {len(files)} arquivos...{colors.Fore.RESET}")

    success = False
    # O bloco 'with' garante que a animação pare mesmo se o backup falhar
    with colors.AsyncAnimation(frames, interval=0.05, base_color=colors.Fore.PRIMARY) as anim:
        try:
            # Enquanto a animação roda na Thread B, o backup roda na Thread A
            success = run_quantum_backup(output, source_path, files, password, hint=hint, quantum=quantum)
            
            # Podemos injetar logs na tela sem quebrar a animação usando anim.print()
            if success:
                anim.print(f"<{colors.Fore.SUCCESS}>[LOG] Camada de criptografia selada.")
            
        except Exception as e:
           # EXIBIÇÃO VERBOSA DO ERRO (Chief-Gold Standard)
            anim.print(f"<{colors.Fore.ERROR}>[FALHA CRÍTICA] {type(e).__name__}: {str(e)}")
            if "--debug" in sys.argv: # Opcional: mostrar traceback se quiser
                anim.print(traceback.format_exc())
            success = False

    # --- FIM DA ANIMAÇÃO ---

    if success:
        size = os.path.getsize(output) / (1024 * 1024)
        print("\n" + "="*60)
        print(NexusUI.gradient_text(f"BACKUP CONCLUÍDO: {output} ({size:.2f} MB)"))
        if quantum:
            print(f"{colors.Fore.MAGENTA}🛡️ Proteção Kyber-768 aplicada com sucesso.{colors.Fore.RESET}")
        print("="*60)
    else:
        click.secho("\n[ERRO] Falha ao gerar o container de backup.", fg="red", bold=True)

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--exclude", "-e", multiple=True, help="Excluir extensões.")
@click.option("--password", help="Senha (opcional se quiser passar via linha de comando).")
def list(file, exclude, password):
    """Lista o conteúdo e mostra a dica ANTES da senha."""
    from doxbackup.core.security import get_hint_from_file
    from doxbackup.core import engine
    
    # 1. Mostra a dica primeiro
    hint = get_hint_from_file(file)
    click.secho(f"\n[Dica de Senha]: {hint}", fg="yellow", bold=True)
    
    # 2. Se a senha não foi passada via flag, pede agora de forma oculta
    if not password:
        password = click.prompt("Digite a senha para abrir o cofre", hide_input=True)
    
    try:
        contents = engine.list_backup_contents(file, password)
        exc = [f.lower() for f in exclude]
        click.echo(f"\n{'TAMANHO':>12} | {'ARQUIVO'}")
        click.echo("-" * 65)
        count = 0
        for path, size in contents:
            if any(path.lower().endswith(f) for f in exc): continue
            count += 1
            size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
            click.echo(f"{size_str:>12} | {path}")
        click.secho(f"\n[OK] {count} arquivos encontrados.", fg="cyan")
    except Exception:
        click.secho(f"[ERRO] Senha incorreta ou arquivo corrompido.", fg="red")

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("dest", default=".")
@click.option("--password", help="Senha.")
def unpack(file, dest, password):
    """Extrai o backup e mostra a dica ANTES da senha."""
    from doxbackup.core.security import get_hint_from_file
    from doxbackup.core import engine
    
    hint = get_hint_from_file(file)
    click.secho(f"\n[Dica de Senha]: {hint}", fg="yellow", bold=True)
    
    if not password:
        password = click.prompt("Digite a senha para descriptografar", hide_input=True)
        
    base_name = os.path.basename(file).replace(".dox", "")
    output_folder = os.path.join(dest, f"{base_name}_extracted")
    if not os.path.exists(output_folder): os.makedirs(output_folder)
    
    try:
        engine.restore_data(file, output_folder, password)
        click.secho(f"\n[SUCESSO] Extraído em: {output_folder}", fg="green", bold=True)
    except Exception as e:
        click.secho(f"\n[ERRO] Falha: {e}", fg="red")