import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.lib_forge import LibForge


def test_is_safe_requirement_accepts_simple_and_pinned_names():
    assert LibForge._is_safe_requirement("numpy")
    assert LibForge._is_safe_requirement("orjson==3.10.7")
    assert LibForge._is_safe_requirement("pydantic>=2.8.0")


def test_is_safe_requirement_rejects_shell_like_inputs():
    assert not LibForge._is_safe_requirement("")
    assert not LibForge._is_safe_requirement("numpy; rm -rf /")
    assert not LibForge._is_safe_requirement("../evil")
    assert not LibForge._is_safe_requirement("package with spaces")


def test_extract_package_name():
    assert LibForge._extract_package_name("click") == "click"
    assert LibForge._extract_package_name("Click==8.1.7") == "click"
    assert LibForge._extract_package_name("pydantic>=2.0") == "pydantic"


def test_integrity_report_detects_missing_files(tmp_path):
    forge = LibForge(tmp_path)
    manifest = forge.lib_bin_dir / "manifest.json"
    manifest.write_text(
        json.dumps({"libraries": {"click": {"compiled_at": 1, "binaries": ["v_click_xxx.pyd"]}}}),
        encoding="utf-8",
    )

    report = forge.integrity_report("click")
    assert report["ok"] is False
    assert report["missing_files"] == 1
    assert report["libraries_checked"] == 1


def test_select_forge_target_prefers_package_dir(tmp_path):
    forge = LibForge(tmp_path)
    src = tmp_path / "srcpkg"
    src.mkdir()
    (src / "pathspec").mkdir()
    (src / "pathspec" / "__init__.py").write_text("", encoding="utf-8")
    (src / "benchmarks").mkdir()

    target = forge._select_forge_target(src, "pathspec")
    assert target == (src / "pathspec")


def test_write_manifest_persists_errors(tmp_path):
    forge = LibForge(tmp_path)
    forge._write_manifest("pathspec", ["v_x.pyd"], errors=["e1"])
    data = forge._load_manifest()
    assert data["libraries"]["pathspec"]["errors"] == ["e1"]


def test_benchmark_library_success(monkeypatch, tmp_path):
    forge = LibForge(tmp_path)

    calls = []

    def fake_samples(package, runs, disable_lib_bin):
        calls.append((package, runs, disable_lib_bin))
        if disable_lib_bin:
            return [{"elapsed": 2.0, "redirected": 0}] * runs
        return [{"elapsed": 1.0, "redirected": 3}] * runs

    monkeypatch.setattr(forge, "_run_bench_samples", fake_samples)

    result = forge.benchmark_library("Click==8.1.7", runs=4)
    assert result["ok"] is True
    assert result["library"] == "click"
    assert result["speedup"] == 2.0
    assert result["redirected_modules"] == 3
    assert calls == [("click", 4, True), ("click", 4, False)]


def test_benchmark_library_failure_includes_details(monkeypatch, tmp_path):
    forge = LibForge(tmp_path)
    monkeypatch.setattr("importlib.util.find_spec", lambda _name: object())

    def fake_samples(package, runs, disable_lib_bin):
        forge._last_bench_error_base = "base err"
        forge._last_bench_error_vulcan = "vulcan err"
        return []

    monkeypatch.setattr(forge, "_run_bench_samples", fake_samples)
    result = forge.benchmark_library("rich", runs=2)

    assert result["ok"] is False
    assert result["library"] == "rich"
    assert "details" in result


def test_benchmark_library_requires_importable_package(monkeypatch, tmp_path):
    forge = LibForge(tmp_path)

    monkeypatch.setattr("importlib.util.find_spec", lambda _name: None)
    result = forge.benchmark_library("pathspec", runs=3)

    assert result["ok"] is False
    assert "não está importável" in result["error"]
