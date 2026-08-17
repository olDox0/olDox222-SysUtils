# -*- coding: utf-8 -*-
# doxbackup/core/verify.py
"""
Verify — Análise leve de diretório para planejamento de backup.
Usa streaming e pouca memória (não carrega arquivos inteiros).
"""

import click
import os
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from utils.path_utils import is_ignored_folder


@dataclass
class VerifyReport:
    """Relatório de verificação de diretório."""
    source: str
    total_files: int = 0
    total_size: int = 0
    included_files: int = 0
    included_size: int = 0
    excluded_files: int = 0
    excluded_size: int = 0
    
    ext_stats: Dict[str, Dict] = field(default_factory=dict)
    large_files: List[Tuple[str, int]] = field(default_factory=list)
    folder_stats: Dict[str, Dict] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "source": self.source,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "included_files": self.included_files,
            "included_size": self.included_size,
            "excluded_files": self.excluded_files,
            "excluded_size": self.excluded_size,
            "ext_stats": self.ext_stats,
            "large_files": self.large_files[:20],
            "folder_stats": self.folder_stats,
        }


def format_size(size: int) -> str:
    """Formata tamanho em bytes para string legível."""
    if size is None:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def verify_directory(source_path: str, top_n: int = 15) -> VerifyReport:
    """
    Escaneia diretório e gera relatório de estatísticas.
    Usa o MESMO filtro do backup (get_file_list) para consistência.
    """
    from doxbackup.core.engine import get_file_list
    
    source = Path(source_path).resolve()
    report = VerifyReport(source=str(source))
    
    if not source.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {source}")
    
    if not source.is_dir():
        raise NotADirectoryError(f"Não é um diretório: {source}")
    
    # ═══ USA O MESMO FILTRO DO BACKUP ═══
    filtered_files = get_file_list(str(source))
    filtered_set = set(filtered_files)
    
    ext_data = defaultdict(lambda: {"count": 0, "size": 0})
    large_files = []
    folder_data = defaultdict(lambda: {"count": 0, "size": 0})
    
    # Escaneia TODOS os arquivos para contar excluídos
    for root, dirs, files in os.walk(str(source)):
        dirs[:] = [d for d in dirs if not is_ignored_folder(d)]
        
        for f in files:
            full_path = os.path.join(root, f)
            
            try:
                size = os.path.getsize(full_path)
            except (OSError, PermissionError):
                continue
            
            report.total_files += 1
            report.total_size += size
            
            # Verifica se está na lista filtrada do backup
            if full_path in filtered_set:
                report.included_files += 1
                report.included_size += size
                
                ext = os.path.splitext(f)[1].lower() or ".noext"
                ext_data[ext]["count"] += 1
                ext_data[ext]["size"] += size
                
                if size > 1024 * 1024:
                    large_files.append((full_path, size))
                
                try:
                    rel = os.path.relpath(root, str(source))
                    top_folder = rel.split(os.sep)[0] if rel != "." else "(raiz)"
                    folder_data[top_folder]["count"] += 1
                    folder_data[top_folder]["size"] += size
                except ValueError:
                    folder_data["(raiz)"]["count"] += 1
                    folder_data["(raiz)"]["size"] += size
            else:
                report.excluded_files += 1
                report.excluded_size += size
    
    report.ext_stats = dict(
        sorted(ext_data.items(), key=lambda x: x[1]["size"], reverse=True)[:top_n]
    )
    report.large_files = sorted(large_files, key=lambda x: x[1], reverse=True)[:top_n]
    report.folder_stats = dict(
        sorted(folder_data.items(), key=lambda x: x[1]["size"], reverse=True)[:top_n]
    )
    
    return report


def print_verify_report(report: VerifyReport, verbose: bool = False):
    """Imprime relatório de verificação formatado."""
    print("\n" + "=" * 70)
    print("🔍 RELATÓRIO DE VERIFICAÇÃO DE DIRETÓRIO")
    print("=" * 70)
    print(f"Fonte: {report.source}")
    print(f"\n📊 RESUMO GERAL:")
    print(f"   Total de arquivos: {report.total_files}")
    print(f"   Tamanho total: {format_size(report.total_size)}")
    print(f"   Incluídos no backup: {report.included_files} ({format_size(report.included_size)})")
    print(f"   Excluídos (filtros): {report.excluded_files} ({format_size(report.excluded_size)})")
    
    if report.ext_stats:
        print(f"\n📁 EXTENSÕES (top {len(report.ext_stats)} por tamanho):")
        print(f"   {'EXT':<12} | {'QTD':>6} | {'TAMANHO':>12} | {'MÉDIA':>10}")
        print("   " + "-" * 55)
        for ext, stats in report.ext_stats.items():
            avg = stats["size"] // stats["count"] if stats["count"] > 0 else 0
            print(f"   {ext:<12} | {stats['count']:>6} | {format_size(stats['size']):>12} | {format_size(avg):>10}")
    
    if report.large_files:
        print(f"\n🐘 ARQUIVOS GRANDES (top {len(report.large_files)}):")
        print(f"   {'TAMANHO':>12} | {'CAMINHO'}")
        print("   " + "-" * 65)
        for path, size in report.large_files:
            # Trunca caminho longo
            display_path = path if len(path) < 60 else "..." + path[-57:]
            print(f"   {format_size(size):>12} | {display_path}")
    
    if report.folder_stats:
        print(f"\n📂 PASTAS (top {len(report.folder_stats)} por tamanho):")
        print(f"   {'PASTA':<30} | {'QTD':>6} | {'TAMANHO':>12}")
        print("   " + "-" * 55)
        for folder, stats in report.folder_stats.items():
            print(f"   {folder:<30} | {stats['count']:>6} | {format_size(stats['size']):>12}")
    
    print("\n" + "=" * 70)
    
    # Recomendações
    print("\n💡 RECOMENDAÇÕES:")
    if report.included_size > 500 * 1024 * 1024:
        print(f"   ⚠️  Backup grande ({format_size(report.included_size)}). Considere usar --dct1 para compressão máxima.")
    elif report.included_size > 100 * 1024 * 1024:
        print(f"   ℹ️  Backup médio ({format_size(report.included_size)}). Use compressão padrão.")
    else:
        print(f"   ✅ Backup pequeno ({format_size(report.included_size)}). Compressão rápida.")
    
    # Verifica se há muitos arquivos de código
    code_exts = {".py", ".c", ".h", ".cpp", ".js", ".ts", ".java", ".go", ".rs"}
    code_count = sum(
        stats["count"] for ext, stats in report.ext_stats.items() if ext in code_exts
    )
    if code_count > 50:
        print(f"   📚 Muitos arquivos de código ({code_count}). Use --learned para dicionários Zstd.")
    
    print("=" * 70)
    
@click.group()
def cli():
    """DoxBackup — Sistema de backup eficiente e seguro."""
    pass
    
@cli.command('check')
@click.argument('path', type=click.Path(exists=True))
@click.option('--top', '-t', default=15, 
    help="Número de itens no top (padrão: 15)")
@click.option('--json', 'json_out', type=click.Path(dir_okay=False), default=None, 
    help="Salva relatório JSON")
def verify(path, top, json_out):
    """Verifica um diretório e mostra estatísticas para planejamento de backup."""
    from doxbackup.core.verify import verify_directory, print_verify_report
    
    try:
        report = verify_directory(path, top_n=top)
        print_verify_report(report)
        
        if json_out:
            import json as json_mod
            from pathlib import Path as P
            out_path = P(json_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json_mod.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            click.secho(f"\n[OK] Relatório JSON salvo em: {out_path}", fg="green")
            
    except Exception as e:
        click.secho(f"[ERRO] Falha na verificação: {e}", fg="red", bold=True)
        if "--debug" in sys.argv:
            import traceback
            click.echo(traceback.format_exc())
        sys.exit(1)
        
@cli.command(name='verify-integrity')
@click.argument('file', type=click.Path(exists=True))
@click.argument('source', type=click.Path(exists=True))
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
@click.option('--verbose', is_flag=True,
    help="Mostra todos os arquivos verificados")
def verify_integrity(file, source, password, verbose):
    """Verifica bit a bit que o backup não corrompeu dados (anti-lossy)."""
    from doxbackup.core.fidelity import verify_backup_integrity_full
    from doxbackup.core.engine import get_file_list
    
    source_path = Path(source).resolve()
    
    # ═══ CORREÇÃO: Usa o MESMO filtro do backup ═══
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
        for error in report["errors"][:20]:
            print(f"   ❌ {error}")
        if len(report["errors"]) > 20:
            print(f"   ... e mais {len(report['errors']) - 20} erros")
    
    print("=" * 60)
    
    if report["is_fully_integral"]:
        click.secho("✅ BACKUP ÍNTEGRO: Nenhum dado corrompido ou perdido.", fg="green", bold=True)
    else:
        click.secho("❌ BACKUP CORROMPIDO: Há arquivos com perda de dados!", fg="red", bold=True)
        sys.exit(2)