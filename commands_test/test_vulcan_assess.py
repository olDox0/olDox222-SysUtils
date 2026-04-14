import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.forge import assess_file_for_vulcan


def test_assess_skips_main_and_init(tmp_path):
    m = tmp_path / "__main__.py"
    m.write_text("print('x')\n", encoding="utf-8")
    ok, reason = assess_file_for_vulcan(str(m))
    assert ok is False
    assert "entrada/namespace" in (reason or "")


def test_assess_skips_very_complex_file(tmp_path):
    f = tmp_path / "heavy.py"
    body = "\n".join(f"x{i} = {i}" for i in range(2600))
    f.write_text(body, encoding="utf-8")
    ok, reason = assess_file_for_vulcan(str(f))
    assert ok is False
    assert "complexidade alta" in (reason or "")