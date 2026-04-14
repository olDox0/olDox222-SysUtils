# utils/error_handler.py

import traceback
import logging
import sys
import click

logging.basicConfig(
    filename="diskdiag.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def handle_error(error: Exception):
    error_type = type(error).__name__
    message = str(error)

    print(f"[ERRO] {error_type}: {message}")

    # log completo
    logging.error("Erro capturado", exc_info=True)


def debug_trace():
    """Usar apenas em modo debug"""
    traceback.print_exc(file=sys.stderr)
    
def handle_cli_error(e):
    click.echo(f"[ERRO] {type(e).__name__}: {e}")
