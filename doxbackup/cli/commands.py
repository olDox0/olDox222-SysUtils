# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

import click
import os
import time
from doxbackup.core import engine

def count_files(directory):
    """Conta arquivos válidos (ignorando venv, etc) para a barra de progresso."""
    total = 0
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d.lower() not in engine.IGNORE_LIST]
        total += len(files)
    return total

@click.group()
def cli():
    """DoxBackup — Sistema de backup eficiente e seguro."""
    pass

@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.password_option("--password", prompt="Digite a senha para proteger o backup", confirmation_prompt=True)
def pack(source, password):
    """Backup Native de Alta Performance."""
    source = os.path.abspath(source)
    output = f"backup_{os.path.basename(source.rstrip(os.sep))}.dox"
    
    start_time = time.time()
    click.echo(f"[DoxBackup] Compactando {source} com acelerador Native...")
    
    try:
        # Rodamos sem o progress_callback para focar em velocidade bruta
        engine.backup_data(source, output, password)
        
        duration = time.time() - start_time
        size = os.path.getsize(output) / (1024 * 1024)
        
        click.secho(f"\n[SUCESSO] Backup Native concluído!", fg="green", bold=True)
        click.echo(f"  └─ Tamanho: {size:.2f} MB")
        click.echo(f"  └─ Tempo:   {duration:.2f}s")
    except Exception as e:
        click.secho(f"\n[ERRO] {e}", fg="red")

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("dest", default=".") # Agora o destino é opcional, padrão é a pasta atual
@click.password_option("--password", prompt="Digite a senha para descriptografar", confirmation_prompt=False)
def unpack(file, dest, password):
    """Descriptografa e Extrai um backup em uma subpasta segura."""
    # 1. Gera o nome da pasta de saída baseado no arquivo
    # backup_doxoade.dox -> backup_doxoade_extracted
    base_name = os.path.basename(file).replace(".dox", "")
    output_folder = os.path.join(dest, f"{base_name}_extracted")
    
    # 2. Cria a pasta se não existir
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    click.secho(f"[DoxBackup] Restaurando conteúdo em: {output_folder}", fg="yellow")
    
    try:
        engine.restore_data(file, output_folder, password)
        click.secho(f"\n[SUCESSO] Restauração concluída em: {output_folder}", fg="green", bold=True)
    except Exception as e:
        click.secho(f"\n[ERRO] Falha na restauração: {e}", fg="red")
        
@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--ext", "-x", help="Mostrar APENAS esta extensão (ex: .md).")
@click.option("--exclude", "-e", help="EXCLUIR esta extensão da lista (ex: .py).")
@click.password_option("--password", prompt="Digite a senha para abrir o cofre", confirmation_prompt=False)
def list(file, ext, exclude, password):
    """Lista o conteúdo do backup com filtros de inclusão e exclusão."""
    click.echo(f"[DoxBackup] Abrindo cofre: {file}...")
    try:
        contents = engine.list_backup_contents(file, password)
        
        click.echo(f"\n{'TAMANHO':>12} | {'ARQUIVO'}")
        click.echo("-" * 65)
        
        count = 0
        total_size = 0
        
        for path, size in contents:
            path_lower = path.lower()
            
            # Filtro de Inclusão (se definido, ignora o resto)
            if ext and not path_lower.endswith(ext.lower()):
                continue
            
            # Filtro de Exclusão (se definido, remove o que der match)
            if exclude and path_lower.endswith(exclude.lower()):
                continue
            
            count += 1
            total_size += size
            size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
            click.echo(f"{size_str:>12} | {path}")
            
        click.secho(f"\n[OK] {count} arquivos encontrados (Total visível: {total_size/(1024*1024):.2f} MB)", fg="cyan")
    except Exception as e:
        click.secho(f"[ERRO] {e}", fg="red")