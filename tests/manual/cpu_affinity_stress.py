#!/usr/bin/env python3
"""Gerador controlado de carga de CPU para testes manuais de afinidade.

Uso:
    python cpu_affinity_stress.py
    python cpu_affinity_stress.py --workers 2 --duration 90
    python cpu_affinity_stress.py --workers 4 --duration 0

O programa mantém um único PID e usa threads. Cada thread calcula SHA-256
sobre um bloco em memória; hashlib libera o GIL em atualizações grandes.
Nenhum arquivo, rede ou dado externo é utilizado.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import signal
import sys
import threading
import time
from typing import Sequence


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("informe um número inteiro") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("o valor deve ser maior que zero")
    return number


def non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("informe um número inteiro") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("use zero ou um valor positivo")
    return number


def worker(
    index: int,
    payload: bytes,
    stop_event: threading.Event,
    counters: list[int],
    counters_lock: threading.Lock,
) -> None:
    """Executa hashing contínuo e publica contagens periodicamente."""
    local_count = 0
    last_publish = time.monotonic()

    while not stop_event.is_set():
        digest = hashlib.sha256()
        digest.update(payload)
        digest.digest()
        local_count += 1

        now = time.monotonic()
        if now - last_publish >= 0.5:
            with counters_lock:
                counters[index] += local_count
            local_count = 0
            last_publish = now

    if local_count:
        with counters_lock:
            counters[index] += local_count


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    cpu_count = os.cpu_count() or 1
    parser = argparse.ArgumentParser(
        description="Gera carga de CPU para testes de afinidade (P-Core/E-Core)."
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=min(2, cpu_count),
        help=f"quantidade de threads (padrão: {min(2, cpu_count)})",
    )
    parser.add_argument(
        "--duration",
        type=non_negative_int,
        default=60,
        help="duração em segundos; 0 mantém o teste até Ctrl+C",
    )
    parser.add_argument(
        "--block-mib",
        type=positive_int,
        default=4,
        help="tamanho do bloco SHA-256 em MiB (padrão: 4)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    cpu_count = os.cpu_count() or 1
    if args.workers > cpu_count:
        print(
            f"Aviso: {args.workers} threads para {cpu_count} CPUs lógicas.",
            file=sys.stderr,
        )

    payload = b"A" * (args.block_mib * 1024 * 1024)
    stop_event = threading.Event()
    counters = [0 for _ in range(args.workers)]
    counters_lock = threading.Lock()
    threads = [
        threading.Thread(
            target=worker,
            args=(index, payload, stop_event, counters, counters_lock),
            name=f"cpu-stress-{index + 1}",
            daemon=True,
        )
        for index in range(args.workers)
    ]

    started = time.monotonic()
    previous_time = started
    previous_cpu = time.process_time()
    previous_hashes = 0
    deadline = started + args.duration if args.duration else None

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    old_sigint = signal.signal(signal.SIGINT, request_stop)
    old_sigterm = None
    if hasattr(signal, "SIGTERM"):
        old_sigterm = signal.signal(signal.SIGTERM, request_stop)

    print("=== CPU AFFINITY STRESS TEST ===", flush=True)
    print(f"PID             : {os.getpid()}", flush=True)
    print(f"Python          : {sys.version.split()[0]}", flush=True)
    print(f"CPUs lógicas    : {cpu_count}", flush=True)
    print(f"Threads de carga: {args.workers}", flush=True)
    print(f"Bloco por hash  : {args.block_mib} MiB", flush=True)
    print(
        f"Duração         : {'até Ctrl+C' if args.duration == 0 else f'{args.duration} s'}",
        flush=True,
    )
    print("Use esse PID com 'sysutils energy programs --pid <PID> --perf/--eco'.", flush=True)
    print("Pressione Ctrl+C para encerrar.\n", flush=True)

    try:
        for thread in threads:
            thread.start()

        while not stop_event.wait(1.0):
            now = time.monotonic()
            if deadline is not None and now >= deadline:
                stop_event.set()
                break

            cpu_now = time.process_time()
            with counters_lock:
                total_hashes = sum(counters)

            elapsed = max(now - previous_time, 1e-9)
            cpu_elapsed = max(cpu_now - previous_cpu, 0.0)
            cpu_percent = (cpu_elapsed / elapsed) * 100.0
            rate = (total_hashes - previous_hashes) / elapsed

            print(
                f"t={now - started:7.1f}s | CPU={cpu_percent:6.1f}% "
                f"| hashes/s={rate:8.2f} | hashes={total_hashes}",
                flush=True,
            )
            previous_time = now
            previous_cpu = cpu_now
            previous_hashes = total_hashes

    finally:
        stop_event.set()
        for thread in threads:
            thread.join(timeout=5)
        signal.signal(signal.SIGINT, old_sigint)
        if old_sigterm is not None:
            signal.signal(signal.SIGTERM, old_sigterm)

    with counters_lock:
        total_hashes = sum(counters)
    elapsed = max(time.monotonic() - started, 1e-9)
    print(
        f"\nEncerrado: {elapsed:.1f}s, {total_hashes} hashes "
        f"({total_hashes / elapsed:.2f} hashes/s).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
