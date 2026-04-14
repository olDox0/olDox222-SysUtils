from pathlib import Path


def _load_bootstrap_source() -> str:
    src = Path('doxoade/commands/vulcan_cmd.py').read_text(encoding='utf-8')
    return src


def test_bootstrap_registers_runtime_alias_module():
    src = _load_bootstrap_source()
    assert '_doxo_sys.modules["_doxoade_vulcan_runtime"] = _doxo_mod' in src


def test_bootstrap_registers_embedded_alias_module():
    src = _load_bootstrap_source()
    assert '_doxo_sys.modules["_doxoade_vulcan_embedded"] = _doxo_mod2' in src


def test_bootstrap_exposes_probe_and_optional_diag():
    src = _load_bootstrap_source()
    assert '_doxo_probe_embedded = getattr(_doxo_mod, "probe_embedded", None)' in src
    assert '__doxoade_vulcan_probe__ = _doxo_probe_embedded(_doxo_project_root)' in src
    assert '__doxoade_vulcan_probe__["boot_ms"] = int((_doxo_time.monotonic() - _doxo_boot_t0) * 1000)' in src
    assert '+ "boot_ms=" + str(__doxoade_vulcan_probe__.get("boot_ms", 0)) + " "' in src
