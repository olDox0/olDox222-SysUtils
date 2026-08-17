# utils/doxoade_bridge.py
# Gerado/auditado por Doxoade Init --commands
# Objetivo: expor comandos Doxoade dentro do CLI do Silo.

import importlib
import os
import click

_CANDIDATES = (
    ("doxoade.cli", "cli"),
    ("doxoade.cli.main", "cli"),
    ("doxoade", "cli"),
)


def _load_doxoade_cli():
    """Carrega o grupo principal do Doxoade."""
    errors = []

    for module_name, attr_name in _CANDIDATES:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr_name)
        except Exception as e:
            errors.append(f"{module_name}:{attr_name} -> {type(e).__name__}: {e}")

    @click.group()
    def _fallback():
        click.secho("[DOX BRIDGE] CLI do Doxoade não disponível.", fg="red", bold=True)
        for err in errors:
            click.echo(err)

    return _fallback


def load_command(name: str):
    """
    Retorna um comando Doxoade para ser anexado ao CLI do projeto.
    Garante que o cwd do projeto externo seja respeitado.
    """
    base_cli = _load_doxoade_cli()

    try:
        ctx = click.Context(base_cli, info_name="doxoade")
        cmd = base_cli.get_command(ctx, name)
    except Exception:
        cmd = None

    if cmd is None:
        @click.command(name=name)
        def _missing():
            click.secho(
                f"[DOX BRIDGE] Comando '{name}' não encontrado no Doxoade.",
                fg="red",
                bold=True
            )
        return _missing

    return cmd