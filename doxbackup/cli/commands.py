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
from pathlib import Path

@click.group()
def cli():
    """DoxBackup — Sistema de backup eficiente e seguro."""
    pass

@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", default="backup.dox", help="Nome do arquivo de saída.")
@click.option("--quantum", is_flag=True, help="Ativa Criptografia Híbrida Pós-Quântica (Kyber-768).")
@click.option("--hint", default="", help="Dica de senha para o container.")
@click.password_option(prompt="Defina a senha do container", confirmation_prompt=True)
def pack(source, output, quantum, hint, password):
    """Cria um container de backup ultra-seguro e otimizado."""
    from doxbackup.core.engine import run_quantum_backup, get_file_list
    from diskdiag.core.storage import init_db
    
    source_path = Path(source).resolve()
    click.echo(f"[VULCAN] Analisando e filtrando arquivos em: {source_path}")
    
    # 1. Coleta lista de arquivos (podemos usar o indexer que já temos)
    db_path = "data/db/files.db"
    
    click.echo(f"[VULCAN] Coletando arquivos de: {source_path}")
    # Simulação de coleta (ou use a função get_file_list do engine.py anterior)
    files = get_file_list(str(source_path))
#    files = [p for p in source_path.rglob('*') if p.is_file()]
    
    if not files:
        click.secho("[AVISO] Nenhum arquivo válido restou após a filtragem.", fg="yellow")
        return

    # 2. Executa o Packer Nativo
    mode = "PÓS-QUÂNTICO" if quantum else "CLÁSSICO"
    click.secho(f"[INICIANDO] Arquivos selecionados: {len(files)}", fg="cyan", bold=True)
    
    success = run_quantum_backup(output, source_path, files, password, hint=hint, quantum=quantum)
#    success = run_quantum_backup(output, files, password, hint=hint, quantum=quantum)
    
    if success:
        size = os.path.getsize(output) / (1024 * 1024)
        click.secho(f"\n[SUCESSO] Container '{output}' criado ({size:.2f} MB).", fg="green", bold=True)
        if quantum:
            click.secho("🛡️ Proteção Kyber-768 (ML-KEM) aplicada ao cabeçalho.", fg="magenta")
    else:
        click.secho("\n[FALHA] Erro ao gerar o container de backup.", fg="red")

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