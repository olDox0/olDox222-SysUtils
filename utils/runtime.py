# doxoade/tools/vulcan/runtime.py
"""
Runtime bridge para consumir binários Vulcan em projetos externos.
Pipeline de 3 Camadas (Tier):
  Tier 1 — Binário Nativo (.pyd/.so)
  Tier 2 — Python Otimizado (.py)
  Tier 3 — Python Puro (source original)
"""
from __future__ import annotations
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import inspect
import os
import struct
import sys
from pathlib import Path
from types import ModuleType
from typing import MutableMapping, Optional

_OPTIMIZED_SUFFIX = '_vulcan_optimized'
_BINARY_EXT = '.pyd' if os.name == 'nt' else '.so'
_VERBOSE = os.environ.get('VULCAN_VERBOSE', '').strip() == '1'

def _vlog(msg: str) -> None:
    if _VERBOSE:
        sys.stderr.write(f'[VULCAN:REDIRECT] {msg}\n')

def _load_isolated_module(path: Path, native_name: str, package_name: str = "") -> Optional[ModuleType]:
    """Carrega o módulo de forma isolada, respeitando a assinatura C do PyInit."""
    if not path.exists():
        return None
        
    try:
        # Registramos com o prefixo do pacote para o Python se localizar
        full_module_name = f"{package_name}.{native_name}" if package_name else native_name
        
        if full_module_name in sys.modules:
            return sys.modules[full_module_name]

        # Spec criado apontando pro .pyd ou opt_.py
        spec = importlib.util.spec_from_file_location(full_module_name, str(path))
        if not spec or not spec.loader:
            return None
            
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = package_name
        
        sys.modules[full_module_name] = mod
        
        try:
            spec.loader.exec_module(mod)
        except ImportError as e:
            # Fallback gracioso: Se o Cython reclamar de import relativo, abortamos o Tier 1
            sys.modules.pop(full_module_name, None)
            raise RuntimeError(f"Constraint de import relativo do Cython: {e}")
            
        return mod
    except Exception as e:
        sys.modules.pop(full_module_name, None)
        raise e

def _binary_ext() -> str:
    return _BINARY_EXT

def _is_binary_valid_for_host(bin_path: Path) -> bool:
    try:
        if not bin_path.exists() or bin_path.stat().st_size < 4096:
            return False
        with bin_path.open('rb') as f:
            head = f.read(64)
        if os.name == 'nt':
            if not head.startswith(b'MZ'):
                return False
            with bin_path.open('rb') as f:
                f.seek(60)
                e_lfanew = struct.unpack('<I', f.read(4))[0]
                f.seek(e_lfanew + 4)
                machine = struct.unpack('<H', f.read(2))[0]
            host_bits = struct.calcsize('P') * 8
            if host_bits == 64 and machine != 34404:
                return False
            if host_bits == 32 and machine != 332:
                return False
        elif not head.startswith(b'ELF'):
            return False
        return True
    except Exception:
        return False

def _is_binary_stale(bin_path: Path, source_path: Optional[Path]) -> bool:
    if not source_path or not source_path.exists():
        return False
    try:
        return source_path.stat().st_mtime > bin_path.stat().st_mtime
    except OSError:
        return False

def _find_pyd_for_source(bin_dir: Path, source_path: Path) -> Optional[Path]:
    stem = source_path.stem
    ext = _binary_ext()
    
    try:
        content = source_path.read_text(encoding='utf-8', errors='ignore').replace('\r\n', '\n')
        abs_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:6]
    except:
        abs_hash = "000000"
        
    _vlog(f'LOOKUP {stem} hash={abs_hash} in {bin_dir}')
    candidate = bin_dir / f'v_{stem}_{abs_hash}{ext}'
    if candidate.exists():
        return candidate
        
    matches = sorted(bin_dir.glob(f'v_{stem}_*{ext}'), key=lambda p: p.stat().st_mtime, reverse=True)
    if matches:
        return matches[0]
    legacy = bin_dir / f'v_{stem}{ext}'
    if legacy.exists():
        return legacy
    return None

def _safe_call(py_fn, native_fn):
    def wrapper(*args, **kwargs):
        try:
            return native_fn(*args, **kwargs)
        except TypeError:
            return py_fn(*args, **kwargs)
        except Exception:
            return py_fn(*args, **kwargs)
    wrapper.__name__ = getattr(py_fn, '__name__', '')
    wrapper.__doc__ = getattr(py_fn, '__doc__', '')
    return wrapper

class VulcanLoader(importlib.abc.Loader):
    """Loader que realiza o Hot-Swap de 3 camadas."""
    def __init__(self, original_loader, bin_path, native_module_name, opt_py_path=None):
        self._original_loader = original_loader
        self._bin_path = bin_path
        self._native_name = native_module_name
        self._opt_py_path = opt_py_path

    def create_module(self, spec) -> Optional[ModuleType]:
        if hasattr(self._original_loader, 'create_module'):
            return self._original_loader.create_module(spec)
        return None

    def exec_module(self, module: ModuleType) -> None:
        if not getattr(module, '__file__', None):
            origin = getattr(module.__spec__, 'origin', None)
            if origin:
                module.__file__ = str(origin)
                
        if not getattr(module, '__loader__', None):
            module.__loader__ = self._original_loader
            
        # TIER 3 - Base Original
        try:
            self._original_loader.exec_module(module)
        except Exception as e:
            _vlog(f"FATAL: Falha na base Tier 3 para {module.__name__} - {e}")
            raise

        # TIER 2 - Python Otimizado
        if self._opt_py_path and Path(self._opt_py_path).exists():
            self._overlay_opt_py(module)
            
        # TIER 1 - Binário Cython
        if self._bin_path and Path(self._bin_path).exists():
            self._inject_pyd(module)

    def _overlay_opt_py(self, module: ModuleType) -> None:
        try:
            pkg = getattr(module, '__package__', '')
            opt_stem = Path(self._opt_py_path).stem
            
            opt_mod = _load_isolated_module(Path(self._opt_py_path), opt_stem, package_name=pkg)
            if not opt_mod: return

            replaced = 0
            for attr in dir(opt_mod):
                if attr.startswith('__'): continue
                
                opt_obj = getattr(opt_mod, attr, None)
                orig_obj = getattr(module, attr, None)
                
                if opt_obj is None or orig_obj is None: continue
                if not (callable(opt_obj) and callable(orig_obj)): continue
                
                try:
                    if inspect.isfunction(opt_obj) and inspect.isfunction(orig_obj):
                        def _required_params(fn):
                            return {
                                n for n, p in inspect.signature(fn).parameters.items()
                                if p.default is inspect.Parameter.empty
                                   and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                            }

                        if _required_params(orig_obj) != _required_params(opt_obj):
                            continue
                except (ValueError, TypeError): pass
                
                setattr(module, attr, opt_obj)
                replaced += 1
                
            _vlog(f'OPT  {module.__name__} ← {Path(self._opt_py_path).name} ({replaced} funcs)')
        except Exception as exc:
            _vlog(f'OPT-FAIL {module.__name__} — {exc}')

    def _inject_pyd(self, module: ModuleType) -> None:
        try:
            pkg = getattr(module, '__package__', '')
            
            # MANTÉM o self._native_name para o PyInit_ satisfazer o Cython em C
            native_mod = _load_isolated_module(Path(self._bin_path), self._native_name, package_name=pkg)
            if not native_mod:
                _vlog(f'SKIP {module.__name__} — não foi possível isolar.')
                return
                
            injected = []
            for attr in dir(native_mod):
                if not attr.endswith(_OPTIMIZED_SUFFIX): continue
                orig_name = attr[:-len(_OPTIMIZED_SUFFIX)]
                if not hasattr(module, orig_name): continue
                    
                py_fn = getattr(module, orig_name)
                native_fn = getattr(native_mod, attr)
                
                try:
                    inspect.signature(py_fn)
                    inspect.signature(native_fn)
                    setattr(module, orig_name, native_fn)
                except (ValueError, TypeError):
                    setattr(module, orig_name, _safe_call(py_fn, native_fn))
                injected.append(orig_name)
                
            if not injected:
                for attr in dir(native_mod):
                    if not attr.startswith('_') and hasattr(module, attr):
                        native_func = getattr(native_mod, attr)
                        if callable(native_func):
                            setattr(module, attr, native_func)
                            injected.append(attr)

            if injected:
                _vlog(f"HIT DIRECT {module.__name__} ← {Path(self._bin_path).name} ({len(injected)} funções)")
                module.__file__ = str(self._bin_path)
            else:
                _vlog(f'LOAD {module.__name__} ← {Path(self._bin_path).name} (sem funções integradas)')
                
        except Exception as exc:
            _vlog(f'FAIL {module.__name__} ← {Path(self._bin_path).name} — {exc}')

class VulcanBinaryFinder(importlib.abc.MetaPathFinder):
    _BYPASS_PREFIXES = (
        'doxoade.tools.', 'doxoade.database.', 'doxoade.rescue',
        'encodings.', 'codecs.', '_', 'builtins',
        'importlib', 'sys', 'os', 'pathlib', 'abc',
    )
    _VULCAN_FINDER_MARKER = True

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.bin_dir = self.project_root / '.doxoade' / 'vulcan' / 'bin'
        self._cache: dict[str, tuple | None] = {}

    def _resolve_original_spec(self, fullname: str, path):
        for finder in sys.meta_path:
            if finder is self or getattr(finder, '_VULCAN_FINDER_MARKER', False) or "Shadow" in str(finder):
                continue
            if hasattr(finder, 'find_spec'):
                try:
                    spec = finder.find_spec(fullname, path, None)
                    if spec and spec.origin and (spec.origin not in ('built-in', 'frozen')):
                        if str(spec.origin).endswith('.py'):
                            return spec
                except Exception:
                    continue
        return None

    def find_spec(self, fullname: str, path, target=None):
        if any(fullname.startswith(p) for p in self._BYPASS_PREFIXES): return None
        
        original_spec = self._resolve_original_spec(fullname, path)
        if not original_spec or not original_spec.loader: return None
        
        source = Path(original_spec.origin)
        
        bin_path = _find_pyd_for_source(self.bin_dir, source) if self.bin_dir.exists() else None
        opt_path = self._find_or_generate_opt(source)
        
        if not bin_path and not opt_path:
            return None
            
        if bin_path:
            if not _is_binary_valid_for_host(bin_path) or _is_binary_stale(bin_path, source):
                bin_path = None
                
        native_name = bin_path.stem.split('.')[0] if bin_path else ""
        
        _vlog(f'INTERCEPT {fullname} → ' + (bin_path.name if bin_path else 'None') + (' + OPT' if opt_path else ''))
        
        loader = VulcanLoader(
            original_loader=original_spec.loader,
            bin_path=bin_path,
            native_module_name=native_name,
            opt_py_path=opt_path,
        )
        new_spec = importlib.machinery.ModuleSpec(fullname, loader, origin=original_spec.origin)
        new_spec.has_location = True
        return new_spec

    def _find_or_generate_opt(self, source_path: Path) -> Optional[Path]:
        try:
            from .opt_cache import find_opt_py, generate_opt_py, find_project_root_for
            root = find_project_root_for(source_path) or self.project_root
            return find_opt_py(root, source_path) or generate_opt_py(root, source_path)
        except Exception:
            return None

_installed_finders: dict[str, VulcanBinaryFinder] = {}


def install_meta_finder(project_root: str | Path) -> VulcanBinaryFinder:
    """
    Instala VulcanBinaryFinder no sys.meta_path do projeto.

    Idempotente — seguro para múltiplas chamadas com o mesmo project_root.
    Retorna o finder ativo (novo ou existente).
    """
    root_str = str(Path(project_root).resolve())
    for existing in sys.meta_path:
        if isinstance(existing, VulcanBinaryFinder) or getattr(existing, '_VULCAN_FINDER_MARKER', False):
            if str(getattr(existing, 'project_root', '')) == root_str:
                return existing
    finder = VulcanBinaryFinder(root_str)
    sys.meta_path.insert(0, finder)
    _installed_finders[root_str] = finder
    return finder


def uninstall_meta_finder(project_root: str | Path | None = None) -> None:
    """Remove VulcanBinaryFinder(s) do sys.meta_path."""
    root_str = str(Path(project_root).resolve()) if project_root else None
    sys.meta_path[:] = [
        f for f in sys.meta_path
        if not (
            isinstance(f, VulcanBinaryFinder)
            and (root_str is None or str(f.project_root) == root_str)
        )
    ]
    if root_str:
        _installed_finders.pop(root_str, None)
    else:
        _installed_finders.clear()


def find_vulcan_project_root(start: str | Path) -> Optional[Path]:
    """Localiza a raiz de projeto com ``.doxoade/vulcan/bin``."""
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    for node in [current, *current.parents]:
        if (node / '.doxoade' / 'vulcan' / 'bin').exists():
            return node
    return None


def load_vulcan_binary(module_name: str, project_root: str | Path) -> Optional[ModuleType]:
    """
    Carrega um binário Vulcan pelo nome nativo (ex: ``v_engine_abc123``).

    Uso direto — para injeção manual de símbolos via activate_vulcan.
    O nome deve ser apenas a parte base sem tag de plataforma.
    """
    root = Path(project_root).resolve()
    bin_dir = root / '.doxoade' / 'vulcan' / 'bin'
    ext = _binary_ext()
    bin_path = bin_dir / f'{module_name}{ext}'
    if not bin_path.exists():
        matches = sorted(
            bin_dir.glob(f'{module_name}*{ext}'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not matches:
            return None
        bin_path = matches[0]
    if not _is_binary_valid_for_host(bin_path):
        return None
    old_path = sys.path.copy()
    try:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
        venv = root / 'venv'
        if venv.exists():
            if os.name == 'nt':
                sp = venv / 'Lib' / 'site-packages'
            else:
                pyver = f'python{sys.version_info.major}.{sys.version_info.minor}'
                sp = venv / 'lib' / pyver / 'site-packages'
            if sp.exists():
                sp_str = str(sp)
                if sp_str not in sys.path:
                    sys.path.insert(1, sp_str)
        spec = importlib.util.spec_from_file_location(module_name, str(bin_path))
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None
    finally:
        sys.path = old_path


def _resolve_opt_path(source_path: Path, root: Path) -> Optional[Path]:
    """Localiza/gera opt_py — local primeiro, doxoade como fallback."""
    try:
        local_oc = _load_local_module(
            root / '.doxoade' / 'vulcan' / 'opt_cache.py',
            '_vulcan_local_opt_cache',
        )
        if local_oc:
            find = getattr(local_oc, 'find_opt_py', None)
            gen = getattr(local_oc, 'generate_opt_py', None)
            fpr = getattr(local_oc, 'find_project_root_for', None)
            opt_root = (fpr(source_path) if fpr else None) or root
            cached = find(opt_root, source_path) if find else None
            if cached:
                return cached
            return gen(opt_root, source_path) if gen else None
    except Exception:
        pass
    try:
        from .opt_cache import find_opt_py, find_project_root_for, generate_opt_py
        opt_root = find_project_root_for(source_path) or root
        return find_opt_py(opt_root, source_path) or generate_opt_py(opt_root, source_path)
    except Exception:
        return None


def _load_opt_module(opt_path: Path, source_path: Path, globs: MutableMapping) -> Optional[ModuleType]:
    """Carrega opt_py em namespace isolado com contexto de globs. None em falha."""
    spec = importlib.util.spec_from_file_location(f'_vulcan_opt_{source_path.stem}', str(opt_path))
    if not spec or not spec.loader:
        return None
    opt_mod = importlib.util.module_from_spec(spec)
    for k, v in globs.items():
        try:
            setattr(opt_mod, k, v)
        except (AttributeError, TypeError):
            pass
    spec.loader.exec_module(opt_mod)
    return opt_mod


def _inject_opt_callables(opt_mod: ModuleType, globs: MutableMapping) -> int:
    """Substitui callables de mesmo nome em globs pelo equivalente otimizado."""
    replaced = 0
    for attr in dir(opt_mod):
        if attr.startswith('__'):
            continue
        opt_obj = getattr(opt_mod, attr, None)
        orig_obj = globs.get(attr)
        if opt_obj and orig_obj and callable(opt_obj) and callable(orig_obj):
            globs[attr] = opt_obj
            replaced += 1
    return replaced


def _activate_tier2(globs: MutableMapping[str, object], source_path: Path, root: Path) -> int:
    """
    Injeção de Tier 2 (Python Otimizado) em globs.

    Retorna o número de callables substituídos. Silencioso em qualquer falha.
    """
    try:
        opt_path = _resolve_opt_path(source_path, root)
        if not opt_path or not opt_path.exists():
            return 0
        opt_mod = _load_opt_module(opt_path, source_path, globs)
        if not opt_mod:
            return 0
        return _inject_opt_callables(opt_mod, globs)
    except Exception:
        return 0


def _activate_tier1(
    globs: MutableMapping[str, object],
    source_path: Path,
    root: Path,
    optimized_suffix: str,
) -> int:
    """
    Injeção de Tier 1 (Binário Nativo) em globs.

    Retorna o número de símbolos substituídos. Silencioso em qualquer falha.
    """
    bin_dir = root / '.doxoade' / 'vulcan' / 'bin'
    bin_path = _find_pyd_for_source(bin_dir, source_path)
    if not bin_path:
        return 0
    if not _is_binary_valid_for_host(bin_path):
        return 0
    if _is_binary_stale(bin_path, source_path):
        return 0
    native_name = bin_path.stem.split('.')[0]
    module = load_vulcan_binary(native_name, root)
    if not module:
        return 0
    injected = 0
    for attr in dir(module):
        if not attr.endswith(optimized_suffix):
            continue
        orig_name = attr[:-len(optimized_suffix)]
        globs[orig_name] = getattr(module, attr)
        injected += 1
    return injected


def _probe_resolve_root(project_root: Optional[str | Path]) -> Optional[Path]:
    """Resolve a raiz de projeto para probe_embedded."""
    if project_root:
        return Path(project_root).resolve()
    main = sys.modules.get('__main__')
    main_file = getattr(main, '__file__', None)
    return find_vulcan_project_root(main_file) if main_file else None


def _probe_dir_count(directory: Optional[Path], pattern: str) -> int:
    """Conta arquivos em ``directory`` que batem com ``pattern``. Seguro."""
    if directory and directory.exists():
        return len(list(directory.glob(pattern)))
    return 0


def activate_vulcan(
    globs: MutableMapping[str, object],
    source_file: str,
    *,
    project_root: str | Path | None = None,
    optimized_suffix: str = _OPTIMIZED_SUFFIX,
) -> bool:
    """
    Ativa funções otimizadas do Vulcan no escopo informado.

    Pipeline de 3 camadas aplicado ao ``source_file``:
      1. Instala MetaFinder global (redirecionamento automático de imports).
      2. Tenta carregar opt_py e injetar callables otimizados em globs (Tier 2).
      3. Tenta carregar o PYD e injetar *_vulcan_optimized em globs (Tier 1).

    Retorna True quando ao menos um símbolo foi injetado (em qualquer tier).
    """
    root = Path(project_root).resolve() if project_root else find_vulcan_project_root(source_file)
    if not root:
        return False
    install_meta_finder(root)
    source_path = Path(source_file)
    injected = _activate_tier2(globs, source_path, root)
    injected += _activate_tier1(globs, source_path, root, optimized_suffix)
    return injected > 0


def _probe_vulcan_dirs(root: Optional[Path]) -> tuple:
    """Resolve os 3 diretórios Vulcan a partir de root. Retorna (bin, lib, opt)."""
    if not root:
        return (None, None, None)
    return (
        root / '.doxoade' / 'vulcan' / 'bin',
        root / '.doxoade' / 'vulcan' / 'lib_bin',
        root / '.doxoade' / 'vulcan' / 'opt_py',
    )


def _probe_finder_stats() -> dict:
    """Coleta info dos VulcanFinders ativos no sys.meta_path."""
    finders = [f for f in sys.meta_path if getattr(f, '_VULCAN_FINDER_MARKER', False)]
    return {
        'finder_installed': bool(finders),
        'finder_count': len(finders),
        'meta_path': [type(f).__name__ for f in sys.meta_path],
    }


def _probe_dir_entry(directory: Optional[Path], pattern: str, label: str) -> dict:
    """Gera o bloco de diagnóstico de um diretório Vulcan."""
    return {
        f'{label}_dir': str(directory) if directory else None,
        f'{label}_exists': bool(directory and directory.exists()),
        f'{label}_count': _probe_dir_count(directory, pattern),
    }


def probe_embedded(project_root: str | Path | None = None) -> dict:
    """Probe leve para depurar estado do runtime embedded no processo atual."""
    root = _probe_resolve_root(project_root)
    ext = _binary_ext()
    bin_dir, lib_dir, opt_dir = _probe_vulcan_dirs(root)
    result = {'project_root': str(root) if root else None}
    result.update(_probe_finder_stats())
    result.update(_probe_dir_entry(bin_dir, f'*{ext}', 'bin'))
    result.update(_probe_dir_entry(lib_dir, f'*{ext}', 'lib_bin'))
    result.update(_probe_dir_entry(opt_dir, 'opt_*.py', 'opt_py'))
    return result
