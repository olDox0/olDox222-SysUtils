# doxbackup/core/fidelity.py
import hashlib
# [DOX-UNUSED] import json
# [DOX-UNUSED] import os
# [DOX-UNUSED] import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

CHUNK_SIZE = 1024 * 1024


@dataclass
class FidelityReport:
    ok: bool = True
    mode: str = "full"
    backup_file: str = ""
    source_dir: str = ""
    total_source: int = 0
    total_archived: int = 0
    verified: int = 0
    missing: List[str] = field(default_factory=list)
    size_mismatch: List[Dict[str, Any]] = field(default_factory=list)
    hash_mismatch: List[str] = field(default_factory=list)
    unreadable_source: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)

    def fail(self, message: str):
        self.ok = False
        self.messages.append(message)


def sha256_file(path: Path) -> str:
    """
    Gera SHA-256 em chunks para não estourar RAM.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def normalize_rel(name: str) -> str:
    """
    Normaliza caminhos de dentro do backup.
    Ex.: 'pasta\\arquivo.txt' vira 'pasta/arquivo.txt'
    """
    return Path(name.replace("\\", "/")).as_posix().lstrip("./")


def relative_to_source(path: Path, source: Path) -> str:
    """
    Retorna caminho relativo seguro em relação ao source.
    """
    path = path.resolve()
    source = source.resolve()

    try:
        return path.relative_to(source).as_posix()
    except ValueError:
        # Fallback raro: arquivo fora da raiz informada.
        return path.name


def build_source_manifest(source_path: Path, files: List[str]) -> Dict[str, Any]:
    """
    Constrói o manifesto da origem:
    - caminho relativo
    - tamanho
    - mtime
    - sha256
    """
    source = Path(source_path).resolve()
    entries = []

    for file_path in files:
        p = Path(file_path)

        rel = relative_to_source(p, source)

        try:
            if not p.is_file():
                continue

            st = p.stat()

            entries.append(
                {
                    "path": rel,
                    "size": st.st_size,
                    "mtime": int(st.st_mtime),
                    "sha256": sha256_file(p),
                }
            )
        except Exception as e:
            entries.append(
                {
                    "path": rel,
                    "error": f"{type(e).__name__}: {e}",
                }
            )

    return {
        "version": 1,
        "algorithm": "sha256",
        "source": str(source),
        "entries": entries,
    }

def verify_backup_integrity_full(backup_file: str, source_path: Path, files: list, password: str) -> dict:
    """
    Verificação completa de integridade pós-backup.
    - Descompacta o backup
    - Compara bit a bit com a fonte
    - Verifica que não há perda (lossy)
    - Gera relatório de integridade
    """
    import tempfile
    from pathlib import Path
    
    report = {
        "backup_file": backup_file,
        "source": str(source_path),
        "total_files": len(files),
        "verified_ok": 0,
        "verified_fail": 0,
        "errors": [],
        "is_fully_integral": False,
    }
    
    with tempfile.TemporaryDirectory(prefix="dox_integrity_") as temp_dir:
        temp_dir = Path(temp_dir)
        
        # Descompacta o backup
        from doxbackup.core.engine import restore_data
        try:
            restore_data(backup_file, temp_dir, password)
        except Exception as e:
            report["errors"].append(f"Restore failed: {e}")
            return report
        
        # Verifica cada arquivo bit a bit
        for file_path in files:
            file_path = Path(file_path)
            
            # Calcula caminho relativo
            try:
                rel_path = file_path.relative_to(source_path)
            except ValueError:
                continue
            
            original_file = file_path
            restored_file = temp_dir / rel_path
            
            if not restored_file.exists():
                report["errors"].append(f"Missing in backup: {rel_path}")
                report["verified_fail"] += 1
                continue
            
            # Verificação anti-lossy
            integrity = verify_no_lossy(original_file, restored_file)
            
            if integrity["is_identical"]:
                report["verified_ok"] += 1
            else:
                report["verified_fail"] += 1
                report["errors"].append(
                    f"Integrity mismatch: {rel_path} "
                    f"(size: {integrity['original_size']} -> {integrity['restored_size']}, "
                    f"hash: {integrity['original_sha256'][:16]}... -> {integrity['restored_sha256'][:16]}...)"
                )
    
    report["is_fully_integral"] = report["verified_fail"] == 0 and len(report["errors"]) == 0
    
    return report

def verify_no_lossy(original_file: Path, restored_file: Path) -> dict:
    """
    Verifica bit a bit que não houve perda (lossy).
    Retorna dict com: is_identical, size_match, hash_match.
    """
    result = {
        "path": str(original_file),
        "is_identical": False,
        "size_match": False,
        "hash_match": False,
        "original_size": 0,
        "restored_size": 0,
        "original_sha256": "",
        "restored_sha256": "",
    }
    
    try:
        original_size = original_file.stat().st_size
        restored_size = restored_file.stat().st_size
        
        result["original_size"] = original_size
        result["restored_size"] = restored_size
        
        # Verificação 1: Tamanho exato
        result["size_match"] = original_size == restored_size
        
        if not result["size_match"]:
            return result
        
        # Verificação 2: Hash SHA256
        original_hash = sha256_file(original_file)
        restored_hash = sha256_file(restored_file)
        
        result["original_sha256"] = original_hash
        result["restored_sha256"] = restored_hash
        result["hash_match"] = original_hash == restored_hash
        
        # Verificação 3: Identidade total (tamanho + hash)
        result["is_identical"] = result["size_match"] and result["hash_match"]
        
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["is_identical"] = False
    
    return result

def compare_against_listing(manifest: Dict[str, Any], contents: List[tuple]):
    """
    Compara o manifesto contra o retorno de list_backup_contents().
    Verifica presença e tamanho.
    """
    archived = {}

    for path, size in contents:
        archived[normalize_rel(path)] = size

    missing = []
    size_mismatch = []

    for entry in manifest["entries"]:
        if "error" in entry:
            continue

        rel = entry["path"]

        if rel not in archived:
            missing.append(rel)
            continue

        if archived[rel] != entry["size"]:
            size_mismatch.append(
                {
                    "path": rel,
                    "expected_size": entry["size"],
                    "archived_size": archived[rel],
                }
            )

    return missing, size_mismatch, archived


def compare_against_restored_dir(manifest: Dict[str, Any], restore_dir: Path):
    """
    Compara o manifesto contra os arquivos restaurados em pasta temporária.
    """
    missing = []
    size_mismatch = []
    hash_mismatch = []
    verified = 0

    for entry in manifest["entries"]:
        if "error" in entry:
            continue

        rel = entry["path"]
        restored_path = restore_dir / rel

        if not restored_path.exists() or not restored_path.is_file():
            missing.append(rel)
            continue

        try:
            st = restored_path.stat()

            if st.st_size != entry["size"]:
                size_mismatch.append(
                    {
                        "path": rel,
                        "expected_size": entry["size"],
                        "restored_size": st.st_size,
                    }
                )
                continue

            restored_hash = sha256_file(restored_path)

            if restored_hash != entry["sha256"]:
                hash_mismatch.append(rel)
                continue

            verified += 1

        except Exception as e:
            size_mismatch.append(
                {
                    "path": rel,
                    "error": f"{type(e).__name__}: {e}",
                }
            )

    return verified, missing, size_mismatch, hash_mismatch


def verify_backup_fidelity(
    backup_file: str,
    source_path: Path,
    files: List[str],
    password: str,
    full: bool = True,
) -> FidelityReport:
    """
    Auditoria principal.

    full=False:
        - abre o backup
        - lista conteúdo
        - compara nomes/tamanhos

    full=True:
        - faz tudo acima
        - restaura em pasta temporária
        - compara SHA-256 arquivo por arquivo
    """
    from doxbackup.core import engine

    report = FidelityReport(
        mode="full" if full else "quick",
        backup_file=str(backup_file),
        source_dir=str(source_path),
    )

    # 1. Manifesto da origem
    manifest = build_source_manifest(source_path, files)

    valid_entries = [e for e in manifest["entries"] if "error" not in e]
    invalid_entries = [e for e in manifest["entries"] if "error" in e]

    report.total_source = len(valid_entries)

    if invalid_entries:
        report.ok = False
        report.unreadable_source = [e["path"] for e in invalid_entries]
        report.messages.append(
            "Alguns arquivos de origem não puderam ser lidos durante a auditoria."
        )

    # 2. Abrir e listar o backup
    try:
        contents = engine.list_backup_contents(str(backup_file), password)
        report.total_archived = len(contents)
    except Exception as e:
        report.fail(f"Falha ao abrir/listar o container: {type(e).__name__}: {e}")
        return report

    # 3. Comparar inventário e tamanhos
    missing_list, size_list, archived_map = compare_against_listing(
        manifest, contents
    )

    if missing_list:
        report.ok = False
        report.missing.extend(missing_list)

    if size_list:
        report.ok = False
        report.size_mismatch.extend(size_list)

    if not full:
        return report

    # 4. Restaurar em pasta temporária e comparar hash
    with tempfile.TemporaryDirectory(prefix="dox_fidelity_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        try:
            # Ajuste caso a assinatura real do restore_data seja diferente.
            engine.restore_data(str(backup_file), str(tmp_path), password)
        except TypeError:
            # Fallback se restore_data receber Path em vez de str.
            engine.restore_data(Path(backup_file), tmp_path, password)
        except Exception as e:
            report.fail(f"Falha ao restaurar backup para auditoria: {type(e).__name__}: {e}")
            return report

        verified, missing_rest, size_rest, hash_rest = compare_against_restored_dir(
            manifest, tmp_path
        )

        report.verified = verified

        # Consolidar sem repetir
        report.missing = sorted(set(report.missing + missing_rest))
        report.size_mismatch += size_rest
        report.hash_mismatch += hash_rest

    if report.missing:
        report.ok = False

    if report.size_mismatch:
        report.ok = False

    if report.hash_mismatch:
        report.ok = False

    if report.verified != report.total_source:
        report.ok = False
        report.messages.append(
            f"Nem todos os arquivos foram verificados: {report.verified}/{report.total_source}"
        )

    return report


def print_report(report: FidelityReport):
    import click

    click.echo()
    click.echo("=" * 75)
    click.echo("AUDITORIA DE FIDELIDADE DOXBACKUP".center(75))
    click.echo("=" * 75)

    click.echo(f"  Backup:        {report.backup_file}")
    click.echo(f"  Origem:        {report.source_dir}")
    click.echo(f"  Modo:          {report.mode}")
    click.echo(f"  Arquivos origem:   {report.total_source}")
    click.echo(f"  Arquivos no backup: {report.total_archived}")
    click.echo(f"  Verificados:       {report.verified}")

    if report.missing:
        click.secho(f"\n  [FALHA] Arquivos ausentes: {len(report.missing)}", fg="red")
        for item in report.missing[:20]:
            click.secho(f"    - {item}", fg="red")

    if report.size_mismatch:
        click.secho(f"\n  [FALHA] Divergência de tamanho: {len(report.size_mismatch)}", fg="red")
        for item in report.size_mismatch[:20]:
            click.secho(f"    - {item}", fg="red")

    if report.hash_mismatch:
        click.secho(f"\n  [FALHA] Hash divergente: {len(report.hash_mismatch)}", fg="red")
        for item in report.hash_mismatch[:20]:
            click.secho(f"    - {item}", fg="red")

    if report.unreadable_source:
        click.secho(f"\n  [AVISO] Origem ilegível: {len(report.unreadable_source)}", fg="yellow")
        for item in report.unreadable_source[:20]:
            click.secho(f"    - {item}", fg="yellow")

    if report.messages:
        click.echo()
        for msg in report.messages:
            click.secho(f"  [LOG] {msg}", fg="yellow")

    click.echo()
    if report.ok:
        click.secho("  [OK] FIDELIDADE VALIDADA: backup íntegro e completo.", fg="green", bold=True)
    else:
        click.secho("  [FALHA] Backup reprovado na auditoria de fidelidade.", fg="red", bold=True)

    click.echo("=" * 75)