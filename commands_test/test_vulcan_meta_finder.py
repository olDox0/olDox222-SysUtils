import importlib.machinery
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.meta_finder import VulcanMetaFinder


class DummyLoader:
    def exec_module(self, module):
        return None


def test_find_spec_skips_package_init_mapping(tmp_path, monkeypatch):
    root = tmp_path
    lib_bin = root / ".doxoade" / "vulcan" / "lib_bin"
    lib_bin.mkdir(parents=True, exist_ok=True)
    (lib_bin / "v_pathspec_abc123.pyd").write_bytes(b"MZ" + b"0" * 8192)

    finder = VulcanMetaFinder(str(root))

    monkeypatch.setattr(finder, "is_binary_valid_for_host", lambda _p: True)
    spec = importlib.machinery.ModuleSpec("pathspec", DummyLoader(), origin=str(root / "site-packages" / "pathspec" / "__init__.py"))
    spec.submodule_search_locations = [str(root / "site-packages" / "pathspec")]
    monkeypatch.setattr(finder, "_resolve_py_path_as_spec", lambda fullname, path: spec)

    out = finder.find_spec("pathspec", None)
    assert out is None
