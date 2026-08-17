# doxoade/doxoade/tools/vulcan/opt_cache.py
"""
OptCache — Cache de Python Otimizado para o sistema Vulcan de 3 camadas.
=========================================================================

Gerencia arquivos Python pré-otimizados em ``.doxoade/vulcan/opt_py/``.

Pipeline de 3 camadas (prioridade decrescente):
  Tier 1 — Binário Nativo (.pyd/.so)   : máxima performance, Cython compilado
  Tier 2 — Python Otimizado (.py)      : sem compilação, AST-limpo pelo LibOptimizer
  Tier 3 — Python Puro (.py)           : fonte original inalterado

Nomeclatura dos arquivos otimizados:
    opt_{stem}_{sha256(abs_path)[:6]}.py

    Usa o mesmo esquema de hash do PitStop → determinístico por path absoluto.

Invalidação:
    Um arquivo otimizado é considerado "stale" se o .py original foi modificado
    depois da última otimização (mtime comparison).

API pública:
    find_opt_py(project_root, source_path)  → Path | None
    generate_opt_py(project_root, source_path) → Path | None
    is_opt_stale(opt_path, source_path) → bool
    opt_dir(project_root) → Path

Compliance:
    OSL-5 : generate_opt_py() nunca levanta exceção — retorna None em falha
    PASC-6: falhas de otimização resultam em cópia do original (sempre válido)
"""
from __future__ import annotations
import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Optional
_OPT_SUBDIR = 'opt_py'

def opt_dir(project_root: Path) -> Path:
    """Retorna (e cria) o diretório opt_py do projeto."""
    d = Path(project_root) / '.doxoade' / 'vulcan' / _OPT_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d

def opt_module_name(source_path: Path) -> str:
    """
    Deriva o nome do módulo otimizado a partir do path absoluto da fonte.

    Usa o mesmo esquema de hash do PitStop para consistência:
        opt_{stem}_{sha256(abs_path)[:6]}
    """
    abs_hash = hashlib.sha256(str(source_path.resolve()).encode()).hexdigest()[:6]
    return f'opt_{source_path.stem}_{abs_hash}'

def is_opt_stale(opt_path: Path, source_path: Path) -> bool:
    """True se o .py fonte foi modificado depois do .py otimizado."""
    try:
        return source_path.stat().st_mtime > opt_path.stat().st_mtime
    except OSError:
        return True

def find_opt_py(project_root: Path, source_path: Path) -> Optional[Path]:
    """
    Localiza o Python otimizado para ``source_path`` no cache do projeto.

    Retorna o Path do .py otimizado se existir e estiver atualizado,
    ou None se ausente/stale.
    """
    d = Path(project_root) / '.doxoade' / 'vulcan' / _OPT_SUBDIR
    if not d.exists():
        return None
    candidate = d / f'{opt_module_name(source_path)}.py'
    if not candidate.exists():
        return None
    if is_opt_stale(candidate, source_path):
        return None
    return candidate

def find_project_root_for(source_path: Path) -> Optional[Path]:
    """
    Sobe a árvore a partir de ``source_path`` procurando ``.doxoade/vulcan/``.
    Retorna a raiz do projeto ou None.
    """
    cur = Path(source_path).resolve().parent
    while True:
        if (cur / '.doxoade' / 'vulcan').exists():
            return cur
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent

def generate_opt_py(project_root: Path, source_path: Path) -> Optional[Path]:
    """
    Gera o Python otimizado para ``source_path`` usando o LibOptimizer.

    Transformações aplicadas (em ordem):
      1. DocstringRemover    — remove docstrings de módulo/classe/função
      2. DeadBranchEliminator — elimina ``if False/True/0/1``
      3. UnusedImportRemover — remove ``import X`` não referenciado
      4. LocalNameMinifier   — renomeia vars locais para nomes curtos

    Se a otimização falhar ou reverter, copia o arquivo original sem
    modificação (garante que a cópia no cache é sempre válida).

    OSL-5: nunca levanta exceção — retorna None em falha crítica.
    """
    try:
        from .vulcan.lib_optimizer import LibOptimizer
        src = Path(source_path).resolve()
        if not src.exists():
            return None
        d = opt_dir(Path(project_root))
        name = f'{opt_module_name(src)}.py'
        dest = d / name
        if dest.exists() and (not is_opt_stale(dest, src)):
            return dest
        with tempfile.TemporaryDirectory(prefix='vulcan_opt_') as tmp:
            tmp_file = Path(tmp) / src.name
            shutil.copy2(str(src), str(tmp_file))
            optimizer = LibOptimizer()
            optimizer.optimize_file(tmp_file)
            shutil.copy(str(tmp_file), str(dest))
        return dest
    except Exception:
        return None

def generate_opt_py_batch(project_root: Path, source_paths: list[Path]) -> dict[str, Optional[Path]]:
    """
    Gera Python otimizado para uma lista de arquivos.
    Retorna dicionário {str(source_path) → opt_path | None}.
    """
    results: dict[str, Optional[Path]] = {}
    for src in source_paths:
        results[str(src)] = generate_opt_py(project_root, src)
    return results
