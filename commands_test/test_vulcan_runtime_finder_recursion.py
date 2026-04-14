import importlib.machinery
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.runtime import VulcanBinaryFinder, install_meta_finder


class DummyLoader:
    def exec_module(self, module):
        return None


class ForeignVulcanFinder:
    _VULCAN_FINDER_MARKER = True

    def __init__(self, project_root):
        self.project_root = project_root
        self.calls = 0

    def find_spec(self, fullname, path=None, target=None):
        self.calls += 1
        return None


class PyFinder:
    def find_spec(self, fullname, path=None, target=None):
        return importlib.machinery.ModuleSpec(fullname, DummyLoader(), origin="/tmp/mod.py")


def test_resolve_original_spec_skips_foreign_vulcan_finder(monkeypatch, tmp_path):
    finder = VulcanBinaryFinder(tmp_path)
    foreign = ForeignVulcanFinder(str(tmp_path / "other"))
    pyfinder = PyFinder()

    monkeypatch.setattr(sys, "meta_path", [finder, foreign, pyfinder])

    spec = finder._resolve_original_spec("pkg.mod", None)
    assert spec is not None
    assert spec.origin == "/tmp/mod.py"
    assert foreign.calls == 0


def test_install_meta_finder_reuses_existing_marker_instance(monkeypatch, tmp_path):
    root = str(tmp_path.resolve())
    foreign = ForeignVulcanFinder(root)
    monkeypatch.setattr(sys, "meta_path", [foreign])

    installed = install_meta_finder(root)
    assert installed is foreign
    assert sys.meta_path[0] is foreign
