# [DOXOADE:VULCAN]
# [VULCAN-SKIP] Proteção contra introspecção Click
import os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")
if os.path.exists(_b):
    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)
    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())
# [/DOXOADE:VULCAN]

# doxbackup/cli/commands.py

import os
import sys
import time
import json
import click
import traceback
from utils.doxcolors import colors, NexusUI

from doxbackup.cli.watermelon_commands import audit_extensions, fidelity_watermelon

from pathlib import Path
SYS_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = str(SYS_ROOT / "data" / "db" / "files.db")

# [DOX-UNUSED] from utils.doxcolors import NexusUI


@click.group()
def cli():
    """DoxBackup — Sistema de backup eficiente e seguro."""
    pass

@cli.command()
@click.argument('source', type=click.Path(exists=True))
@click.option('--output', '-o', default='backup.dox', help="Nome do arquivo de saída.")
@click.option('--quantum', is_flag=True, help="Ativa Criptografia Híbrida Pós-Quântica.")
@click.option('--dct1', is_flag=True, help="Ativa DCT1: compressão extrema lossless.")
@click.option('--dct1-extreme', is_flag=True, help="DCT1 em modo extremo (mais CPU/RAM).")
@click.option('--learned', is_flag=True, help="Ativa compressão aprendida com dicionários Zstd.")
@click.option('--retrain-dict', is_flag=True, help="Força retreino de dicionários.")
@click.option('--dict-top', type=int, default=3, help="Treina dicionários para top N extensões.")
@click.option('--fidelity', 'fidelity_full', is_flag=True, help="Auditoria completa de fidelidade pós-backup.")
@click.option('--fidelity-quick', 'fidelity_quick', is_flag=True, help="Auditoria rápida de fidelidade.")
@click.option('--hint', default='', help="Dica de senha.")
@click.option('--debug', is_flag=True, help="Mostra traceback completo em caso de erro.")
@click.password_option(prompt='Defina a senha do container', confirmation_prompt=True)
def pack(source, output, quantum, dct1, dct1_extreme, learned, retrain_dict, dict_top,
         fidelity_full, fidelity_quick, hint, password, debug):
    """Cria um container de backup ultra-seguro e otimizado."""
    from doxbackup.core.engine import run_quantum_backup, get_file_list
    
    source_path = Path(source).resolve()
    
    click.secho("SISTEMA DE BACKUP VULCAN V3", fg="cyan", bold=True)
    click.echo(f"[VULCAN] Analisando: {source_path}")
    
    files = get_file_list(str(source_path))
    if not files:
        click.secho("[AVISO] Nenhum arquivo válido encontrado.", fg="yellow")
        return
    
    click.echo(f"Preparando compressão de {len(files)} arquivos...")
    
    success = False
    crash_log_path = SYS_ROOT / ".doxoade" / "logs" / "backup_crash.log"
    
    try:
        # SEM ANIMAÇÃO - logs diretos e legíveis
        success = run_quantum_backup(
            output, source_path, files, password,
            hint=hint, quantum=quantum,
            dct1=dct1, dct1_extreme=dct1_extreme,
            learned=learned,
            retrain_dict=retrain_dict,
            dict_top_n=dict_top,
            anim=None  # SEM ANIMAÇÃO
        )
        
        if success:
            click.secho("[LOG] Camada de criptografia selada.", fg="green")
            
    except Exception as e:
        success = False
        import traceback as _tb
        _err_msg = f"[FALHA CRÍTICA] {type(e).__name__}: {str(e)}\n{_tb.format_exc()}"
        
        try:
            crash_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(crash_log_path, "a", encoding="utf-8") as _f:
                _f.write(f"\n{'='*60}\n")
                _f.write(f"CRASH EM: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                _f.write(f"SOURCE: {source_path}\n")
                _f.write(f"OUTPUT: {output}\n")
                _f.write(f"{'='*60}\n")
                _f.write(_err_msg)
        except Exception:
            pass
        
        click.echo()
        click.secho(f"[BOX] Erro gravado em: {crash_log_path}", fg="magenta", bold=True)
        click.secho(f"[FALHA CRÍTICA] {type(e).__name__}: {str(e)}", fg="red", bold=True)
        
        if debug:
            click.echo(_tb.format_exc())
        else:
            click.secho("  Dica: use --debug para traceback completo.", fg="yellow")
    
    if not success:
        click.secho("\n[ERRO] Falha ao gerar o container de backup.", fg="red", bold=True)
        sys.exit(1)
    
    size = os.path.getsize(output) / (1024 * 1024)
    print()
    print("=" * 60)
    print(f"BACKUP CONCLUÍDO: {output} ({size:.2f} MB)")
    if quantum:
        print("🛡️ Proteção Kyber-768 aplicada com sucesso.")
    print("=" * 60)
    
    if fidelity_full or fidelity_quick:
        from doxbackup.core.fidelity import verify_backup_fidelity, print_report
        click.secho("\n[ANÚBIS] Iniciando auditoria de fidelidade...", fg="cyan", bold=True)
        report = verify_backup_fidelity(
            backup_file=output,
            source_path=source_path,
            files=files,
            password=password,
            full=fidelity_full,
        )
        print_report(report)
        if not report.ok:
            sys.exit(2)

@cli.command(name="verify-integrity")
@click.argument('file', type=click.Path(exists=True))
@click.argument('source', type=click.Path(exists=True))
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
@click.option('--verbose', is_flag=True, help='Mostra todos os arquivos verificados')
def verify_integrity(file, source, password, verbose):
    """Verifica bit a bit que o backup não corrompeu dados (anti-lossy)."""
    from doxbackup.core.fidelity import verify_backup_integrity_full
    from doxbackup.core.engine import get_file_list
    
    source_path = Path(source).resolve()
    files = get_file_list(str(source_path))
    
    if not files:
        click.secho("[AVISO] Nenhum arquivo encontrado na fonte.", fg="yellow")
        return
    
    click.echo(f"🔍 Verificando integridade de {len(files)} arquivos...")
    click.echo(f"   Backup: {file}")
    click.echo(f"   Fonte: {source_path}")
    
    report = verify_backup_integrity_full(file, source_path, files, password)
    
    # Exibe relatório
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO DE INTEGRIDADE")
    print("=" * 60)
    print(f"   Arquivos verificados: {report['verified_ok']}")
    print(f"   Arquivos falhos: {report['verified_fail']}")
    
    if report["errors"]:
        print(f"\n   Erros ({len(report['errors'])}):")
        for error in report["errors"][:20]:  # Limita a 20 erros
            print(f"   ❌ {error}")
        if len(report["errors"]) > 20:
            print(f"   ... e mais {len(report['errors']) - 20} erros")
    
    print("=" * 60)
    
    if report["is_fully_integral"]:
        click.secho("✅ BACKUP ÍNTEGRO: Nenhum dado corrompido ou perdido.", fg="green", bold=True)
    else:
        click.secho("❌ BACKUP CORROMPIDO: Há arquivos com perda de dados!", fg="red", bold=True)
        sys.exit(2)

@cli.command(name="fidelity")
@click.argument("file", type=click.Path(exists=True))
@click.argument("source", type=click.Path(exists=True), required=False)
@click.option("--quick", is_flag=True, help="Verificação rápida, sem restauração completa.")
@click.password_option(prompt="Senha do backup", confirmation_prompt=False)
def fidelity(file, source, quick, password):
    """
    Audita a fidelidade de um backup DoxBackup.

    Exemplos:

        sysutils backup fidelity backup.dox

        sysutils backup fidelity backup.dox "C:\\MeuProjeto"

        sysutils backup fidelity backup.dox "C:\\MeuProjeto" --quick
    """
    from doxbackup.core import engine
    from doxbackup.core.fidelity import verify_backup_fidelity, print_report

    file = Path(file).resolve()

    if not source:
        click.secho("\n[ANÚBIS] Testando abertura do container...", fg="cyan")

        try:
            contents = engine.list_backup_contents(str(file), password)
        except Exception as e:
            click.secho(f"[FALHA] Não foi possível abrir o backup: {e}", fg="red", bold=True)
            sys.exit(2)

        click.secho("[OK] Container aberto com sucesso.", fg="green")
        click.echo(f"Arquivos listados: {len(contents)}")

        for path, size in contents[:20]:
            click.echo(f"  {size:>12} | {path}")

        if len(contents) > 20:
            click.echo(f"  ... e mais {len(contents) - 20} arquivos.")

        return

    source_path = Path(source).resolve()

    click.secho(f"\n[ANÚBIS] Auditoria de fidelidade contra: {source_path}", fg="cyan", bold=True)

    files = engine.get_file_list(str(source_path))

    if not files:
        click.secho("[AVISO] Nenhum arquivo válido na origem.", fg="yellow")
        return

    report = verify_backup_fidelity(
        backup_file=str(file),
        source_path=source_path,
        files=files,
        password=password,
        full=not quick,
    )

    print_report(report)

    if not report.ok:
        sys.exit(2)

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
    except Exception as e:
        err_msg = traceback.format_exc()
        click.secho(f"[ERRO] Senha incorreta ou arquivo corrompido. \n. err: {err_msg}", fg="red")

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
        
@click.command(name='audit-extensions')
@click.argument('source', type=click.Path(exists=True))
@click.option('--sample-bytes',default=4 * 1024 * 1024,show_default=True,
    help="Máximo de bytes amostrados por arquivo.")
@click.option('--max-files',type=int,default=None,
    help="Limite de arquivos analisados.")
@click.option('--include-decisions',is_flag=True,
    help="Inclui decisão por arquivo no relatório.")
@click.option('--json-out',type=click.Path(dir_okay=False),default=None,
    help="Salva relatório JSON.")
def audit_extensions(source, sample_bytes, max_files, include_decisions, json_out):
    """ Avalia extensões para o DCT1 Watermelon. Operação somente leitura. """
    from doxbackup.core.watermelon_ext import audit_extensions as audit
    report = audit(source,sample_bytes=sample_bytes,max_files=max_files,
                   include_decisions=include_decisions)
    if json_out:
        out = Path(json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                       encoding="utf-8")
        click.secho(f"[OK] Relatório salvo em: {out}", fg="green")

    click.echo()
    click.secho("DCT1 WATERMELON — AUDITORIA DE EXTENSÕES", fg="cyan", bold=True)
    click.echo("=" * 60)
    click.echo(f"Fonte: {report.source}"
               f"Arquivos vistos: {report.total_files}"
               f"Ignorados: {report.ignored_files}"
               f"Ilegíveis: {report.unreadable_files}"
               f"Extensões distintas: {len(report.extensions)}" )
    click.echo()

    if not report.extensions:
        click.secho("[OK] Nenhuma extensão analisada.", fg="yellow")
        return

    click.echo(f"{'EXT':<10} | {'ARQ':>5} | {'MODO':<12} | {'CONF':<6} | BYTES")
    click.echo("-" * 70)

    for ext, stats in sorted(
        report.extensions.items(),
        key=lambda kv: kv[1].total_bytes,
        reverse=True,
    ):
        click.echo(
            f"{ext:<10} | {stats.count:>5} | "
            f"{stats.recommended_mode:<12} | {stats.confidence:<6} | "
            f"{stats.total_bytes}"
        )
        
@click.command(name='fidelity-watermelon')
@click.argument('file', type=click.Path(exists=True))
@click.argument('source', type=click.Path(exists=True), required=False)
@click.option('--mode',type=click.Choice(['quick', 'standard', 'full']),default='full',show_default=True)
@click.option('--json-out',type=click.Path(dir_okay=False),default=None,
    help="Salva relatório JSON.")
@click.option('--restore-base',type=click.Path(file_okay=False),default=None,
    help="Diretório base para restauração temporária.")
@click.option('--password',default=None,
    help="Senha do backup, se necessário.")
def fidelity_watermelon(file, source, mode, json_out, restore_base, password):
    """ Auditoria avançada de fidelidade para backups DCT1 Watermelon.
    Não sobrescreve a fonte. """
    from doxbackup.core.watermelon_fidelity import (verify_backup_fidelity_watermelon)
    if not source:
        click.secho("[ERRO] SOURCE ainda é obrigatório para o Fidelity Watermelon.", fg="red")
        sys.exit(1)
    source_path = Path(source).resolve()
    if restore_base:
        restore_base_path = Path(restore_base).resolve()
        if restore_base_path == source_path:
            click.secho("[ERRO] restore-base não pode ser igual ao source.", fg="red")
            sys.exit(1)

    # Adapter precisa existir no seu projeto.
    from doxbackup.core.watermelon_fidelity_adapter import DoxBackupAdapter
    adapter = DoxBackupAdapter(file, password=password)
    result = verify_backup_fidelity_watermelon(backup_file=file,source_dir=source,
                                adapter=adapter,mode=mode,restore_base=restore_base)
    if json_out:
        out = Path(json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                       encoding="utf-8")
    click.echo()
    click.secho("DCT1 WATERMELON — FIDELITY", fg="cyan", bold=True)
    click.echo("=" * 60)
    click.echo(f"Backup: {result.backup_file}"
               f"Source: {result.source_dir}"
               f"Modo: {result.mode}"
               f"OK: {result.ok}"
               f"Arquivos fonte: {result.total_source_files}"
               f"Arquivos archive: {result.total_archive_files}"
               f"Verificados: {result.verified_files}"
               f"Missing: {len(result.missing_in_archive)}"
               f"Size mismatch: {len(result.size_mismatch)}"
               f"Hash mismatch: {len(result.hash_mismatch)}"
               f"Policy violations: {len(result.policy_violations)}")
    if result.messages:
        click.echo()
        for msg in result.messages:
            click.echo(f"  MSG: {msg}")
    if result.warnings:
        click.echo()
        for warn in result.warnings[:20]:
            click.secho(f"  WARN: {warn}", fg="yellow")
    sys.exit(0 if result.ok else 2)
    
# --- DCT1 WATERMELON FIX -------------------------------------------------
# Registro direto do audit-extensions para não depender de watermelon_commands.py

@cli.command(name="audit-extensions")
@click.argument("source", type=click.Path(exists=True))
@click.option(
    "--sample-bytes",
    default=4 * 1024 * 1024,
    show_default=True,
    help="Máximo de bytes amostrados por arquivo.",
)
@click.option(
    "--max-files",
    type=int,
    default=None,
    help="Limite de arquivos analisados.",
)
@click.option(
    "--include-decisions",
    is_flag=True,
    help="Inclui decisão por arquivo no relatório.",
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False),
    default=None,
    help="Salva relatório JSON completo.",
)
@click.option(
    "--policy-out",
    type=click.Path(dir_okay=False),
    default=None,
    help="Salva política de extensão JSON.",
)
def watermelon_audit_extensions(
    source,
    sample_bytes,
    max_files,
    include_decisions,
    json_out,
    policy_out,
):
    """
    DCT1 Watermelon: auditoria de extensões.

    Operação somente leitura.
    """
    import json as _json
    from pathlib import Path as _Path

    from doxbackup.core.watermelon_ext import (
        audit_extensions as _audit_fn,
        report_to_policy as _report_to_policy,
    )

    report = _audit_fn(
        source,
        sample_bytes=sample_bytes,
        max_files=max_files,
        include_decisions=include_decisions,
    )

    if json_out:
        out = _Path(json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            _json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        click.secho(f"[OK] Relatório JSON salvo em: {out}", fg="green")

    if policy_out:
        out = _Path(policy_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            _json.dumps(_report_to_policy(report), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        click.secho(f"[OK] Política JSON salva em: {out}", fg="green")

    click.echo()
    click.secho("DCT1 WATERMELON — AUDITORIA DE EXTENSÕES", fg="cyan", bold=True)
    click.echo("=" * 60)
    click.echo(f"Fonte: {report.source}")
    click.echo(f"Arquivos vistos: {report.total_files}")
    click.echo(f"Ignorados: {report.ignored_files}")
    click.echo(f"Ilegíveis: {report.unreadable_files}")
    click.echo(f"Extensões distintas: {len(report.extensions)}")
    click.echo()

    if not report.extensions:
        click.secho("[OK] Nenhuma extensão analisada.", fg="yellow")
        return

    click.echo(f"{'EXT':<10} | {'ARQ':>5} | {'MODO':<12} | {'CONF':<6} | BYTES")
    click.echo("-" * 70)

    for ext, stats in sorted(
        report.extensions.items(),
        key=lambda kv: kv[1].total_bytes,
        reverse=True,
    ):
        click.echo(
            f"{ext:<10} | {stats.count:>5} | "
            f"{stats.recommended_mode:<12} | {stats.confidence:<6} | "
            f"{stats.total_bytes}"
        )

@cli.command(name='fidelity-watermelon')
@click.argument('file', type=click.Path(exists=True))
@click.argument('source', type=click.Path(exists=True))
@click.option('--mode', type=click.Choice(['quick', 'full']), default='full', show_default=True)
@click.option('--json-out', type=click.Path(dir_okay=False), default=None, 
    help="Salva relatório JSON.")
@click.option('--restore-base', type=click.Path(file_okay=False), default=None, 
    help="Diretório base para restauração temporária.")
@click.option('--password', default=None, 
    help="Senha do backup.")
@click.option('--ask-password', is_flag=True, 
    help="Pergunta a senha interativamente.")
def watermelon_fidelity_watermelon(file, source, mode, json_out, restore_base, password, ask_password):
    """
    DCT1 Watermelon: Auditoria avançada de fidelidade.
    Não sobrescreve a fonte. Restaura apenas em temp.
    """
    import json as _json
    from pathlib import Path as _Path
    from doxbackup.core.watermelon_adapter import DoxBackupAdapter
    from doxbackup.core.watermelon_fidelity import verify_backup_fidelity_watermelon

    if ask_password:
        password = click.prompt("Senha do backup", hide_input=True, default="", show_default=False)
        if password == "": password = None

    adapter = DoxBackupAdapter(file, password=password)
    result = verify_backup_fidelity_watermelon(
        backup_file=file, source_dir=source, adapter=adapter,
        mode=mode, restore_base=restore_base
    )

    if json_out:
        out = _Path(json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        click.secho(f"[OK] Relatório JSON salvo em: {out}", fg="green")

    click.echo()
    click.secho("DCT1 WATERMELON — FIDELITY", fg="cyan", bold=True)
    click.echo("=" * 60)
    click.echo(f"Backup: {result.backup_file}")
    click.echo(f"Source: {result.source_dir}")
    click.echo(f"Modo: {result.mode} | OK: {result.ok}")
    click.echo(f"Arquivos fonte (filtrados): {result.total_source_files} | Archive: {result.total_archive_files}")
    click.echo(f"Verificados (Hash OK): {result.verified_files}")
    click.echo(f"Missing: {len(result.missing_in_archive)} | Size Mismatch: {len(result.size_mismatch)} | Hash Mismatch: {len(result.hash_mismatch)}")

    if result.restore_dir:
        click.echo(f"Restore dir: {result.restore_dir}")

    if not result.ok:
        click.secho("\n[FALHA] A integridade do backup não pôde ser garantida.", fg="red", bold=True)
        if result.hash_mismatch:
            click.echo(f"  Hash Mismatch: {result.hash_mismatch[:5]}...")
        if result.missing_in_archive:
            click.echo(f"  Missing: {result.missing_in_archive[:5]}...")
        sys.exit(2)
    else:
        click.secho("\n[SUCESSO] Integridade Watermelon verificada.", fg="green", bold=True)
        
@cli.command(name="debug-archive")
@click.argument("file", type=click.Path(exists=True))
@click.option("--password", default=None, help="Senha do backup.")
@click.option("--ask-password", is_flag=True, help="Pergunta a senha interativamente.")
def debug_archive(file, password, ask_password):
    """Raio-X do formato .dox e teste de descriptografia."""
    # [DOX-UNUSED] import struct
    from pathlib import Path as _Path
    
    if ask_password:
        password = click.prompt("Senha do backup", hide_input=True, default="", show_default=False)
        if password == "": password = None

    p = _Path(file)
    size = p.stat().st_size
    click.echo(f"Arquivo: {p}")
    click.echo(f"Tamanho: {size} bytes")
    
    with open(p, "rb") as f:
        header = f.read(128)
        
    click.echo(f"\n--- HEADER (primeiros 64 bytes) ---")
    click.echo(f"Hex: {header[:64].hex()}")
    
    if len(header) >= 32:
        salt = header[0:16]
        nonce = header[16:32]
        click.echo(f"Salt:  {salt.hex()}")
        click.echo(f"Nonce: {nonce.hex()}")
        
        # Verifica se tem shield de 1088 bytes (DoxEncryptor XOR)
        if size > 1120:
            with open(p, "rb") as f:
                f.seek(32)
                maybe_shield = f.read(16)
                if maybe_shield == b'\x00' * 16:
                    click.secho("Formato detectado: DoxEncryptor (XOR Stream + Shield 1088 bytes)", fg="yellow")
                else:
                    click.secho("Formato detectado: encrypt_file_stream (AES-GCM, sem shield)", fg="cyan")

    click.echo(f"\n--- TESTE 1: list_backup_contents ---")
    try:
        from doxbackup.core.engine import list_backup_contents
        import inspect
        sig = inspect.signature(list_backup_contents)
        click.echo(f"Assinatura: {sig}")
        
        result = None
        try:
            result = list_backup_contents(str(p), password=password)
            click.secho(f"Sucesso com password={'Sim' if password else 'Não'}", fg="green")
        except TypeError as e:
            err_msg = traceback.format_exc()
            click.echo(f"Erro TypeError: {e}. err: \n {err_msg}")
            result = list_backup_contents(str(p))
                
        if result is not None:
            click.echo(f"Tipo do retorno: {type(result)}")
            if isinstance(result, (list, tuple)):
                click.echo(f"Quantidade de itens: {len(result)}")
                if len(result) > 0:
                    click.echo(f"Primeiro item: {result[0]}")
            else:
                click.echo(f"Retorno cru: {result}")
    except Exception as e:
        import traceback
        click.secho(f"Exceção: {type(e).__name__}: {e}", fg="red")
        click.echo(traceback.format_exc())

    click.echo(f"\n--- TESTE 2: DoxDecryptorStream (XOR) ---")
    try:
        from doxbackup.core.security import DoxDecryptorStream
        dec = DoxDecryptorStream(str(p), password or "")
        chunk = dec.read(1024)
        click.echo(f"Leu {len(chunk)} bytes descriptografados")
        click.echo(f"Primeiros 32 bytes (hex): {chunk[:32].hex()}")
        dec.f_in.close()
    except Exception as e:
        err_msg = traceback.format_exc()
        click.secho(f"Erro no DoxDecryptorStream: {type(e).__name__}: {e}.\n. err: {err_msg}", fg="red")
        
