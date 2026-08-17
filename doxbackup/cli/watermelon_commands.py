# -*- coding: utf-8 -*-
# doxbackup/cli/watermelon_commands.py
"""
Comandos CLI do DCT1 Watermelon.

Comandos:
- audit-extensions
- fidelity-watermelon
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click


def _write_json(path, data) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _is_within(child, parent) -> bool:
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


@click.command(name="audit-extensions")
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
def audit_extensions(
    source,
    sample_bytes,
    max_files,
    include_decisions,
    json_out,
    policy_out,
):
    """
    Avalia extensões para o DCT1 Watermelon.

    Operação somente leitura.
    """
    from doxbackup.core.watermelon_ext import (
        audit_extensions as audit_fn,
        report_to_policy,
    )

    report = audit_fn(
        source,
        sample_bytes=sample_bytes,
        max_files=max_files,
        include_decisions=include_decisions,
    )

    if json_out:
        _write_json(json_out, report.to_dict())
        click.secho(f"[OK] Relatório JSON salvo em: {json_out}", fg="green")

    if policy_out:
        _write_json(policy_out, report_to_policy(report))
        click.secho(f"[OK] Política JSON salva em: {policy_out}", fg="green")

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


@click.command(name="fidelity-watermelon")
@click.argument("file", type=click.Path(exists=True))
@click.argument("source", type=click.Path(exists=True), required=False)
@click.option(
    "--mode",
    type=click.Choice(["quick", "standard", "full"]),
    default="full",
    show_default=True,
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False),
    default=None,
    help="Salva relatório JSON.",
)
@click.option(
    "--restore-base",
    type=click.Path(file_okay=False),
    default=None,
    help="Diretório base para restauração temporária.",
)
@click.option(
    "--password",
    default=None,
    help="Senha do backup, se necessário.",
)
@click.option(
    "--ask-password",
    is_flag=True,
    help="Pergunta a senha interativamente.",
)
@click.option(
    "--policy-report",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="JSON do Extension Auditor para validar política de compressão.",
)
def fidelity_watermelon(
    file,
    source,
    mode,
    json_out,
    restore_base,
    password,
    ask_password,
    policy_report,
):
    """
    Auditoria avançada de fidelidade para backups DCT1 Watermelon.

    Não sobrescreve a fonte.
    """
    from types import SimpleNamespace

    from doxbackup.core.watermelon_adapter import DoxBackupAdapter
    from doxbackup.core.watermelon_fidelity import (
        verify_backup_fidelity_watermelon,
    )

    if ask_password:
        password = click.prompt(
            "Senha do backup",
            hide_input=True,
            default="",
            show_default=False,
        )

        if password == "":
            password = None

    if not source:
        click.secho(
            "[ERRO] SOURCE ainda é obrigatório para o Fidelity Watermelon.",
            fg="red",
        )
        sys.exit(1)

    source_path = Path(source).resolve()

    if restore_base:
        restore_base_path = Path(restore_base).resolve()

        if (
            restore_base_path == source_path
            or _is_within(source_path, restore_base_path)
            or _is_within(restore_base_path, source_path)
        ):
            click.secho(
                "[ERRO] restore-base não pode ser igual, pai ou filho do source.",
                fg="red",
            )
            sys.exit(1)

    adapter = DoxBackupAdapter(file, password=password)

    expected = None

    if policy_report:
        data = json.loads(Path(policy_report).read_text(encoding="utf-8"))
        expected = SimpleNamespace(extensions=data.get("extensions", {}))

    result = verify_backup_fidelity_watermelon(
        backup_file=file,
        source_dir=source,
        adapter=adapter,
        mode=mode,
        expected_ext_report=expected,
        restore_base=restore_base,
    )

    if json_out:
        _write_json(json_out, result.to_dict())

    click.echo()
    click.secho("DCT1 WATERMELON — FIDELITY", fg="cyan", bold=True)
    click.echo("=" * 60)
    click.echo(f"Backup: {result.backup_file}")
    click.echo(f"Source: {result.source_dir}")
    click.echo(f"Modo: {result.mode}")
    click.echo(f"OK: {result.ok}")
    click.echo(f"Arquivos fonte: {result.total_source_files}")
    click.echo(f"Arquivos archive: {result.total_archive_files}")
    click.echo(f"Verificados: {result.verified_files}")
    click.echo(f"Missing in archive: {len(result.missing_in_archive)}")
    click.echo(f"Missing restored: {len(result.missing_restored)}")
    click.echo(f"Size mismatch: {len(result.size_mismatch)}")
    click.echo(f"Hash mismatch: {len(result.hash_mismatch)}")
    click.echo(f"Path safety violations: {len(result.path_safety_violations)}")
    click.echo(f"Policy violations: {len(result.policy_violations)}")

    if result.restore_dir:
        click.echo(f"Restore dir: {result.restore_dir}")

    if result.messages:
        click.echo()
        for msg in result.messages:
            click.echo(f"  MSG: {msg}")

    if result.warnings:
        click.echo()
        for warn in result.warnings[:20]:
            click.secho(f"  WARN: {warn}", fg="yellow")

    sys.exit(0 if result.ok else 2)