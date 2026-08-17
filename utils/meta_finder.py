# doxoade/tools/vulcan/meta_finder.py
"""
VulcanMetaFinder - Hook Transparente de Importação.
v6.1:
[RAM Cache] Varredura ultra-rápida em memória para evitar estrangulamento
de I/O no disco durante a importação massiva.
Lógica de busca por padrão para bibliotecas (lib_bin), resolvendo a
falha de incompatibilidade de hash entre compilação e execução.
Debug controlado por variável de ambiente (VULCAN_META_DEBUG=1).
"""
import time
import sys
import struct
import os
import logging
import importlib.util
import importlib.abc
import importlib.machinery
import hashlib
import ctypes
from pathlib import Path
from .safe_loader import SafeExtensionLoader

GENERIC_NAMES = {'core', 'common', 'base', 'helpers', 'config'}
_VULCAN_FINDER_INSTANCE = None


def is_binary_candidate(fullname: str, pyd_path: Path) -> bool:
    basename = fullname.rsplit('.', 1)[-1]
    safe_full = fullname.replace('.', '__')
    stem_base = pyd_path.stem.split('.')[0]
    if basename in GENERIC_NAMES:
        return stem_base.startswith(f'v_{basename}') or stem_base.startswith(f'v{safe_full}')
    return (stem_base.startswith(f'v{basename}') or
            stem_base == f'v{basename}' or
            stem_base.startswith(f'v_{safe_full}') or
            stem_base == f'v{safe_full}')


def try_load_pyd(self, fullname, py_path, bin_path):
    try:
        loader = SafeExtensionLoader(fullname, bin_path, py_path)
        spec = importlib.machinery.ModuleSpec(name=fullname, loader=loader, origin=bin_path, is_package=False)
        if py_path:
            spec.submodule_search_locations = [os.path.dirname(py_path)]
        return spec
    except Exception as e:
        self.logger.debug(f'[SAFE-FALLBACK] .pyd ignorado → {fullname} ({e})')
        return None


def _ensure_vulcan_dirs(project_root: str) -> Path:
    base = Path(project_root) / '.doxoade' / 'vulcan'
    logs = base / 'logs'
    base.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    return base


def _setup_logger(logfile: str, level: int = logging.INFO):
    logger = logging.getLogger('vulcan.meta_finder')
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    fh = logging.FileHandler(logfile, encoding='utf-8')
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger

class HBC6BridgeLoader(importlib.abc.Loader):
    """Tier 0: Loader para bytecode HBC6 via Motor C (Hermes Bridge)."""
    def __init__(self, fullname: str, hbc6_path: str, gd_path: str):
        self.fullname = fullname
        self.hbc6_path = hbc6_path
        self.gd_path = gd_path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = self.hbc6_path
        module.__loader__ = self
        try:
            # 1. Importa o Motor C (hermes_bridge.pyd)
            from .hermes_systems.native.hermes_bridge import load_module
            # 2. O Motor C faz mmap, expansão DFS e retorna o CodeObject
            code_obj = load_module(self.hbc6_path, self.gd_path)
            if code_obj is None:
                raise ImportError("Motor C retornou NULL (HBC6 inválido)")
            
            # 3. Injeção segura no namespace (Aegis Nexus Exec)
            from .aegis.aegis_core import nexus_exec
            nexus_exec(code_obj, module.__dict__)
        except Exception as e:
            raise ImportError(f"[Vulcan Tier 0] Falha no Motor C (HBC6) para {self.fullname}: {e}")

class VulcanMetaFinder(importlib.abc.MetaPathFinder):
#    BYPASS = ('doxoade.tools.vulcan', 'encodings', 'codecs', '')
    BYPASS = ('doxoade.tools.vulcan', 'encodings', 'codecs', 'mercury_core', '')
    _path_hash_cache: dict[str, str] = {}
    _mtime_cache: dict[str, tuple[float, float]] = {}
    _MTIME_TTL = 2.0

    def __init__(self, project_root: str, logger=None):
        self.project_root = Path(project_root).resolve()
        self.build_dir = self.project_root / '.doxoade' / 'hermes' / 'build'  # ← ADICIONE se ausente
        self.logger = logger or logging.getLogger(__name__)
        self.lib_bin_dir = self.project_root / '.doxoade' / 'vulcan' / 'lib_bin'
        self.bin_dir = self.project_root / '.doxoade' / 'vulcan' / 'bin'
        self._spec_cache: dict[str, object] = {}
        self._ext = '.pyd' if os.name == 'nt' else '.so'
        self._host_validity_cache: dict[str, bool] = {}

        self._build_ram_index()
        self._dlog('[VULCAN DEBUG] MetaFinder initialized with RAM Cache.')

    def _get_path_hash(self, path_str: str) -> str:
        if path_str in self._path_hash_cache:
            return self._path_hash_cache[path_str]
        try:
            content = Path(path_str).read_text(encoding='utf-8', errors='ignore').replace('\r\n', '\n')
            h = hashlib.sha256(content.encode('utf-8')).hexdigest()[:6]
        except Exception:
            h = "000000"
        self._path_hash_cache[path_str] = h
        return h

    def _find_project_binary(self, py_path: str):
        if not py_path:
            return None
        abs_path = Path(py_path).resolve()
        path_hash = self._get_path_hash(str(abs_path))
        stem = abs_path.stem
        
        # ═══════════════════════════════════════════════════════════════
        # TIER 0: HBC6 (Motor C-Native) - PRIORIDADE MÁXIMA
        # ═══════════════════════════════════════════════════════════════
        hbc6_name = f"{stem}_{path_hash}.hbc6"
        if hasattr(self, '_hbc6_files') and hbc6_name in self._hbc6_files:
            return self.hbc6_dir / hbc6_name
        if hasattr(self, '_hbc6_files') and f"{stem}.hbc6" in self._hbc6_files:
            return self.hbc6_dir / f"{stem}.hbc6"

        # ═══════════════════════════════════════════════════════════════
        # TIER 1: Cython .pyd (Vulcan Bin)
        # ═══════════════════════════════════════════════════════════════
        candidate_name = f"v_{stem}_{path_hash}{self._ext}"
        if candidate_name in self._bin_files:
            return self.bin_dir / candidate_name
            
        for name in self._lib_bin_files:
            if name.endswith(f"_{path_hash}{self._ext}"):
                return self.lib_bin_dir / name
                
        return None

    def _resolve_py_path(self, fullname, path):
        try:
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if spec and spec.origin and spec.origin.endswith('.py'):
                return spec.origin
        except Exception:
            pass
        return None

    def _build_ram_index(self):
        """Lê os diretórios binários e cria cache em RAM O(1)."""
        self._bin_files = []
        if self.bin_dir.exists():
            try:
                for f in os.scandir(self.bin_dir):
                    if f.name.endswith(self._ext):
                        self._bin_files.append(f.name)
            except Exception:
                pass
        
        self._lib_bin_files = []
        if self.lib_bin_dir.exists():
            try:
                for f in os.scandir(self.lib_bin_dir):
                    if f.name.endswith(self._ext):
                        self._lib_bin_files.append(f.name)
            except Exception:
                pass

        # 🚀 NOVO: Indexa Hermes HBC6 Build Dir (Tier 0)
        self.hbc6_dir = self.project_root / '.doxoade' / 'hermes' / 'build'
        self._hbc6_files = []
        if self.hbc6_dir.exists():
            try:
                for f in os.scandir(self.hbc6_dir):
                    if f.name.endswith('.hbc6'):
                        self._hbc6_files.append(f.name)
            except Exception:
                pass

        # LOG CRÍTICO PARA O SEU CASO:
        if os.environ.get("VULCAN_META_DEBUG") == "1":
            print(f"[VULCAN INDEX] Binários detectados: {len(self._bin_files)} em {self.bin_dir}")
            for b in self._bin_files:
                print(f"   -> {b}")

    def find_spec(self, fullname, path, target=None):
        """Intercepta imports e redireciona para binários Vulcan."""
        if any(fullname.startswith(p) for p in self.BYPASS if p):
            return None

        py_path = self._resolve_py_path(fullname, path)
        if not py_path:
            return None

        # Tenta binário .pyd/.so
        bin_path = self._find_project_binary(str(py_path))
        if bin_path and self._is_binary_valid(bin_path, py_path):
            from .safe_loader import SafeExtensionLoader
            loader = SafeExtensionLoader(fullname, str(bin_path), str(py_path))
            return importlib.util.spec_from_file_location(
                fullname, str(bin_path), loader=loader)

        # Tenta HBC6
#        hbc6_path = self._find_hbc6(py_path)
#        if hbc6_path:
#            from .safe_loader import HBC6BridgeLoader
#            gd = str(self.project_root / '.doxoade' / 'hermes' / 'master.bin')
#            loader = HBC6BridgeLoader(fullname, str(hbc6_path), gd)
#            spec = importlib.util.spec_from_file_location(
#                fullname, str(py_path), loader=loader)
#            spec.origin = str(hbc6_path)
#            return spec

        return None

    def _find_hbc6(self, py_path):
        """
        Localiza o arquivo .hbc6 correspondente a um .py.
        Usa hash do conteúdo para encontrar o artefato no build dir.
        Retorna Path se existir, None caso contrário.
        """
        if not py_path or not Path(py_path).exists():
            return None

        try:
            content_hash = hashlib.sha256(
                Path(py_path).read_bytes()
            ).hexdigest()[:6]
        except Exception:
            return None

        stem = Path(py_path).stem
        hbc6_file = self.build_dir / f"{stem}_{content_hash}.hbc6"

        if hbc6_file.exists():
            return hbc6_file

        # Fallback: busca por stem sem hash (compatibilidade)
        candidates = list(self.build_dir.glob(f"{stem}_*.hbc6"))
        if len(candidates) == 1:
            return candidates[0]

        return None

    @staticmethod
    def _debug_enabled() -> bool:
        return (os.environ.get('VULCAN_META_DEBUG', '').strip() == '1' or
                os.environ.get('VULCAN_VERBOSE', '').strip() == '1')

    @classmethod
    def _dlog(cls, msg: str) -> None:
        if cls._debug_enabled():
            print(str(msg), file=sys.stderr)

def find_spec(self, fullname: str, path, target=None):
    try:
        if any((fullname.startswith(p) for p in self.BYPASS)):
            return None
        cached = self._spec_cache.get(fullname)
        if cached is not None:
            return cached if cached is not False else None

        module_part = fullname.split('.')[-1]
        lib_bin_enabled = os.environ.get('VULCAN_DISABLE_LIB_BIN', '0').strip() != '1'

        # ═══════════════════════════════════════════════════════════════════
        # TIER 1: Binário Nativo (.pyd/.so)
        # ═══════════════════════════════════════════════════════════════════
        if lib_bin_enabled and self._lib_bin_files:
            prefix = f'v_{module_part}_'
            exact = f'v_{module_part}{self._ext}'
            candidate_names = [f for f in self._lib_bin_files if f.startswith(prefix) or f == exact]
            if candidate_names:
                candidates = [self.lib_bin_dir / f for f in candidate_names]
                for bin_path in sorted(candidates, key=lambda p: self._get_mtime(str(p)), reverse=True):
                    if not is_binary_candidate(fullname, bin_path):
                        self._dlog(f'\x1b[90m[VULCAN SKIP] {bin_path.name} ≠ {fullname}\x1b[0m')
                        continue
                    if not self.is_binary_valid_for_host(bin_path):
                        continue

                    original_spec = self._resolve_py_path_as_spec(fullname, path)
                    self._dlog(f'[DEBUG] {fullname} → original_spec={original_spec}')

                    if not (original_spec and original_spec.loader):
                        continue

                    expected_hash = self._get_path_hash(original_spec.origin)
                    actual_hash = bin_path.stem.split('.')[0].rsplit('_', 1)[-1]
                    if actual_hash != expected_hash:
                        self._dlog(f'[VULCAN SKIP] hash mismatch {fullname}: esperado={expected_hash}, pyd={actual_hash} ({bin_path.name})')
                        continue

                    try:
                        origin_name = Path(str(original_spec.origin)).name
                    except Exception:
                        origin_name = ''

                    if origin_name == '__init__.py':
                        self._dlog(f'[DEBUG] skip package root for {fullname}')
                        continue

                    native_name = bin_path.stem.split('.')[0]
                    from .runtime import VulcanLoader
                    new_spec = importlib.machinery.ModuleSpec(
                        fullname,
                        VulcanLoader(original_spec.loader, bin_path, native_name),
                        origin=original_spec.origin
                    )
                    if getattr(original_spec, 'submodule_search_locations', None) is not None:
                        new_spec.submodule_search_locations = original_spec.submodule_search_locations
                    new_spec.has_location = True
                    self._spec_cache[fullname] = new_spec
                    return new_spec

        # Resolve .py original para Tier 2 e Tier 3
        py_path = self._resolve_py_path(fullname, path)
        if py_path:
            self._dlog(f"[RESOLVE] {fullname} -> {py_path}")
            bin_path = self._find_project_binary(py_path)
            self._dlog(f"[BINARY] {bin_path}")
            
            # ═══════════════════════════════════════════════════════════
            # 🚀 TIER 0: HBC6 (Motor C) - Roteamento Direto
            # ═══════════════════════════════════════════════════════════
            if bin_path and str(bin_path).endswith('.hbc6'):
                from .vulcan_safe_loader import HBC6BridgeLoader
                gd_path = self.project_root / '.doxoade' / 'hermes' / 'master.bin'
                loader = HBC6BridgeLoader(fullname, str(bin_path), str(gd_path))
                spec = importlib.machinery.ModuleSpec(
                    name=fullname, loader=loader, origin=str(bin_path), is_package=False
                )
                spec.has_location = True
                self._spec_cache[fullname] = spec
                return spec

            # ═══════════════════════════════════════════════════════════════════
            # TIER 1 (Projeto): Binário Nativo com hash matching
            # ═══════════════════════════════════════════════════════════════════
            if (bin_path and
                self.is_binary_valid_for_host(bin_path) and
                not self._is_stale(py_path, str(bin_path))):

                original_spec = self._resolve_py_path_as_spec(fullname, path)
                if original_spec and original_spec.loader:
                    self.logger.info(
                        f"VULCAN HIT: Mapping project file "
                        f"'{fullname}' -> '{bin_path}'"
                    )
                    spec = self._make_spec(fullname, original_spec, Path(bin_path))

                    if spec:
                        self._spec_cache[fullname] = spec
                        return spec

        # ═══════════════════════════════════════════════════════════════════
        # TIER 2: Python Otimizado (.py do opt_cache)
        # ═══════════════════════════════════════════════════════════════════
        if py_path:
            try:
                from .opt_cache import find_opt_py, find_project_root_for
                origin_path = Path(py_path)
                opt_root = find_project_root_for(origin_path) or self.project_root
                opt_path = find_opt_py(opt_root, origin_path)
                if opt_path and opt_path.exists():
                    original_spec = self._resolve_py_path_as_spec(fullname, path)
                    if original_spec and original_spec.loader:
                        from .runtime import VulcanLoader
                        loader = VulcanLoader(original_spec.loader, None, '', opt_path)
                        t2_spec = importlib.machinery.ModuleSpec(
                            fullname, loader, origin=original_spec.origin
                        )
                        t2_spec.has_location = True
                        self._spec_cache[fullname] = t2_spec
                        return t2_spec
            except Exception:
                pass

        # ═══════════════════════════════════════════════════════════════════
        # [NOVO] TIER 3: Hermes (.hermes HBC3)
        # ═══════════════════════════════════════════════════════════════════
        try:
            from .hermes_systems.hermes_hook import try_load_from_hermes
            hermes_spec = try_load_from_hermes(fullname, str(self.project_root))
            if hermes_spec:
                self._dlog(f'[HERMES HIT] {fullname} → {hermes_spec.origin}')
                self._spec_cache[fullname] = hermes_spec
                return hermes_spec
        except Exception:
            pass

        # ═══════════════════════════════════════════════════════════════════
        # FALLBACK: Não encontrou nada → deixa Python padrão carregar
        # ═══════════════════════════════════════════════════════════════════
        # [CORREÇÃO] Não cacheia False para módulos não-doxoade
        # Isso permite que o HermesFinder (em sys.meta_path[-1]) tente carregar
        if fullname.startswith('doxoade.'):
            self._spec_cache[fullname] = False
        
        return None
    except Exception:
        self.logger.error(f"VulcanMetaFinder.find_spec failure on '{fullname}'", exc_info=True)
        return None

    def _resolve_py_path_as_spec(self, fullname: str, path):
        """Retorna o spec do .py original sem acionar este finder."""
        for finder in sys.meta_path:
            if finder is self:
                continue
            if not hasattr(finder, 'find_spec'):
                continue
            try:
                spec = finder.find_spec(fullname, path, None)
                if spec and spec.origin and (spec.origin not in ('built-in', 'frozen')):
                    return spec
            except Exception:
                continue
        return None

    @classmethod
    def _get_mtime(cls, path: str) -> float:
        now = time.monotonic()
        if path in cls._mtime_cache:
            ts, mtime = cls._mtime_cache[path]
            if now - ts < cls._MTIME_TTL:
                return mtime
        try:
            mtime = Path(path).stat().st_mtime
            cls._mtime_cache[path] = (now, mtime)
            return mtime
        except OSError:
            return 0.0

    def _is_stale(self, py_path: str, bin_path: str) -> bool:
        if not py_path:
            return False
        py_mtime = self._get_mtime(py_path)
        bin_mtime = self._get_mtime(bin_path)
        is_stale = py_mtime > bin_mtime
        if is_stale:
            self.logger.warning(f"STALE: '{Path(bin_path).name}' is older than '{Path(py_path).name}'.")
        return is_stale

    def _make_spec(self, fullname: str, original_spec, bin_path: Path):
        try:
            native_name = bin_path.stem.split('.')[0]
            from .runtime import VulcanLoader

            opt_path = None
            try:
                from .opt_cache import find_opt_py, find_project_root_for
                origin_path = Path(original_spec.origin)
                opt_root = find_project_root_for(origin_path) or self.project_root
                opt_path = find_opt_py(opt_root, origin_path)
            except Exception:
                pass

            loader = VulcanLoader(original_spec.loader, bin_path, native_name, opt_path)
            spec = importlib.machinery.ModuleSpec(fullname, loader, origin=original_spec.origin)
            spec.has_location = True
            return spec
        except Exception:
            self.logger.error(f"Failed to create SAFE spec for '{fullname}' at '{bin_path}'", exc_info=True)
            return None

    def is_binary_valid_for_host(self, bin_path: Path) -> bool:
        bin_str = str(bin_path)
        if bin_str in self._host_validity_cache:
            return self._host_validity_cache[bin_str]
        try:
            if not bin_path.exists() or bin_path.stat().st_size < 1024:
                self._host_validity_cache[bin_str] = False
                return False
            if os.name == 'nt':
                with bin_path.open('rb') as f:
                    if f.read(2) != b'MZ':
                        self._host_validity_cache[bin_str] = False
                        return False
                    f.seek(60)
                    pe_offset = struct.unpack('<I', f.read(4))[0]
                    f.seek(pe_offset + 4)
                    machine = struct.unpack('<H', f.read(2))[0]
                host_bits = struct.calcsize('P') * 8
                if host_bits == 64 and machine != 34404:
                    self._host_validity_cache[bin_str] = False
                    return False
                if host_bits == 32 and machine != 332:
                    self._host_validity_cache[bin_str] = False
                    return False
            self._host_validity_cache[bin_str] = True
            return True
        except Exception:
            self._host_validity_cache[bin_str] = False
            return False


def validate_pyd_for_export(bin_path: str, expected_init_name: str | None = None) -> bool:
    try:
        p = Path(bin_path)
        if not p.exists() or p.stat().st_size < 1024:
            return False
        lib = ctypes.CDLL(str(p))
        if expected_init_name:
            return getattr(lib, f'PyInit_{expected_init_name}', None) is not None
        return True
    except (OSError, Exception):
        return False


def install(project_root: str):
    """Instala a INSTÂNCIA do VulcanMetaFinder com segurança."""
    global _VULCAN_FINDER_INSTANCE
    # Remove Apenas duplicatas antigas do Vulcan
    sys.meta_path = [f for f in sys.meta_path if "VulcanMetaFinder" not in str(f)]

    _ensure_vulcan_dirs(project_root)
    logfile = str(Path(project_root) / '.doxoade' / 'vulcan' / 'logs' / 'meta_finder.log')
    logger = _setup_logger(logfile)

    _VULCAN_FINDER_INSTANCE = VulcanMetaFinder(project_root, logger)
    sys.meta_path.insert(0, _VULCAN_FINDER_INSTANCE)


def uninstall():
    """Remove todas as instâncias do VulcanMetaFinder do sys.meta_path."""
    global _VULCAN_FINDER_INSTANCE
    original_len = len(sys.meta_path)
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, VulcanMetaFinder)]
    if len(sys.meta_path) < original_len and _VULCAN_FINDER_INSTANCE:
        _VULCAN_FINDER_INSTANCE.logger.info('VulcanMetaFinder desinstalado.')
    _VULCAN_FINDER_INSTANCE = None
