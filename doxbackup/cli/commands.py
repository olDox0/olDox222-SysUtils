# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

import click, os, time
from doxbackup.core import engine

@click.group()
def cli():
    """DoxBackup — Sistema de backup eficiente e seguro."""
    pass

@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--diff", is_flag=True, help="Apenas modificados.")
@click.option("--hint", default="", help="Dica de senha.")
# Mantemos o prompt automático apenas no pack porque é onde você define a senha
@click.password_option("--password", prompt="Defina a senha do backup", confirmation_prompt=True)
def pack(source, diff, hint, password):
    """Cria backup comprimido e criptografado."""
    source_path = os.path.abspath(source.rstrip(os.sep))
    output = f"backup_{os.path.basename(source_path)}.dox"
    ts = engine.get_last_backup_time(source_path) if diff else 0
    
    click.echo(f"[DoxBackup] Processando: {source_path}")
    try:
        engine.backup_data(source_path, output, password, timestamp=ts, hint=hint)
        engine.update_last_backup_time(source_path)
        size = os.path.getsize(output) / (1024 * 1024)
        click.secho(f"\n[SUCESSO] Tamanho: {size:.2f} MB", fg="green", bold=True)
    except Exception as e:
        click.secho(f"\n[ERRO] {e}", fg="red")

@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--exclude", "-e", multiple=True, help="Excluir extensões.")
@click.option("--password", help="Senha (opcional se quiser passar via linha de comando).")
def list(file, exclude, password):
    """Lista o conteúdo e mostra a dica ANTES da senha."""
    from doxbackup.core.security import get_hint_from_file
    
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