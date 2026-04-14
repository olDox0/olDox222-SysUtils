import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.forge import VulcanForge


def test_generate_source_removes_future_import(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text(
        '"""doc"""\nfrom __future__ import annotations\n\n'
        'def f(x: int) -> int:\n    return x\n',
        encoding="utf-8",
    )

    out = VulcanForge(str(src)).generate_source(str(src))
    assert "from __future__ import annotations" not in out


def test_generate_source_sanitizes_include_identifier(tmp_path):
    src = tmp_path / "pattern_like.py"
    src.write_text(
        "class Rule:\n"
        "    __slots__ = ('include',)\n\n"
        "    def __init__(self, include):\n"
        "        self.include = include\n",
        encoding="utf-8",
    )

    out = VulcanForge(str(src)).generate_source(str(src))
    assert "def __init___vulcan_optimized(self, _include):" in out
    assert "self.include = _include" in out
