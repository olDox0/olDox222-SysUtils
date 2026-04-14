import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.runtime import probe_embedded


def test_probe_embedded_returns_basic_state(tmp_path):
    state = probe_embedded(project_root=tmp_path)
    assert isinstance(state, dict)
    assert "finder_installed" in state
    assert "finder_count" in state
    assert "meta_path" in state
    assert "bin_count" in state
    assert "lib_bin_count" in state
    assert state["project_root"] == str(tmp_path.resolve())
