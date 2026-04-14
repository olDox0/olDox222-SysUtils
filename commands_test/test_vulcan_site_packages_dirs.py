import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.site_packages import site_packages_dirs_for_listing


def test_site_packages_dirs_prioritize_active_venv(tmp_path, monkeypatch):
    venv = tmp_path / "venv"
    win_site = venv / "Lib" / "site-packages"
    win_site.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("VIRTUAL_ENV", str(venv))
    monkeypatch.setattr("site.getsitepackages", lambda: ["/global/site-packages"])

    dirs = site_packages_dirs_for_listing()

    assert dirs == [str(win_site)]


def test_site_packages_dirs_fallback_without_venv(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.setattr("site.getsitepackages", lambda: ["/a", "/b"])
    monkeypatch.setattr("site.getusersitepackages", lambda: "/u")
    monkeypatch.setattr(sys, "path", ["/x", "/b", "/y/dist-packages"])

    dirs = site_packages_dirs_for_listing()

    assert dirs == ["/a", "/b", "/u", "/y/dist-packages"]
