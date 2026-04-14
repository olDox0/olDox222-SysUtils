import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.environment import VulcanEnvironment


def test_safe_rmtree_removes_directory(tmp_path):
    d = tmp_path / "x"
    d.mkdir()
    (d / "a.txt").write_text("ok", encoding="utf-8")

    VulcanEnvironment._safe_rmtree(d)
    assert not d.exists()


def test_safe_rmtree_rename_fallback_on_failure(monkeypatch, tmp_path):
    d = tmp_path / "y"
    d.mkdir()
    (d / "b.txt").write_text("ok", encoding="utf-8")

    def fail_rmtree(*args, **kwargs):
        raise PermissionError("locked")

    monkeypatch.setattr("shutil.rmtree", fail_rmtree)

    VulcanEnvironment._safe_rmtree(d)

    # diretório original não deve permanecer com mesmo nome
    assert not d.exists()
    pending = list(tmp_path.glob("y.purge_pending_*"))
    assert pending
