from pathlib import Path


def test_bootstrap_diag_probe_not_host_interpolated():
    src = Path('doxoade/commands/vulcan_cmd.py').read_text(encoding='utf-8')
    assert 'f"finder_count={__doxoade_vulcan_probe__' not in src
    assert 'f"bin={__doxoade_vulcan_probe__' not in src
    assert 'f"lib_bin={__doxoade_vulcan_probe__' not in src
    assert '+ "finder_count=" + str(__doxoade_vulcan_probe__.get("finder_count", 0)) + " "' in src
