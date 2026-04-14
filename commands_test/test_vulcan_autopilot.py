import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.autopilot import VulcanAutopilot


class _AdvisorStub:
    def __init__(self, compiled: set[str]):
        self.compiled = compiled

    def _is_already_compiled(self, file_path: str) -> bool:
        return file_path in self.compiled


def test_filter_candidates_skips_already_compiled_when_not_forced(monkeypatch):
    ap = object.__new__(VulcanAutopilot)
    ap.advisor = _AdvisorStub({"b.py"})

    monkeypatch.setattr(
        "doxoade.tools.vulcan.forge.assess_file_for_vulcan",
        lambda file_path: (True, None),
    )

    result = ap._filter_candidates(
        [{"file": "a.py"}, {"file": "b.py"}],
        force_recompile=False,
    )

    assert [c["file"] for c in result] == ["a.py"]


def test_filter_candidates_keeps_compiled_when_forced(monkeypatch):
    ap = object.__new__(VulcanAutopilot)
    ap.advisor = _AdvisorStub({"b.py"})

    monkeypatch.setattr(
        "doxoade.tools.vulcan.forge.assess_file_for_vulcan",
        lambda file_path: (True, None),
    )

    result = ap._filter_candidates(
        [{"file": "a.py"}, {"file": "b.py"}],
        force_recompile=True,
    )

    assert [c["file"] for c in result] == ["a.py", "b.py"]


def test_resolve_max_workers_prefers_explicit_value(monkeypatch):
    monkeypatch.setenv("DOXOADE_VULCAN_JOBS", "7")
    assert VulcanAutopilot._resolve_max_workers(3) == 3


def test_resolve_max_workers_uses_env(monkeypatch):
    monkeypatch.setenv("DOXOADE_VULCAN_JOBS", "5")
    assert VulcanAutopilot._resolve_max_workers(None) == 5


def test_resolve_max_workers_auto_tunes_with_cpu_plus_one(monkeypatch):
    monkeypatch.delenv("DOXOADE_VULCAN_JOBS", raising=False)
    monkeypatch.setattr("doxoade.tools.vulcan.autopilot.os.cpu_count", lambda: 2)
    monkeypatch.setattr(VulcanAutopilot, "_available_mem_mb", staticmethod(lambda: None))
    assert VulcanAutopilot._resolve_max_workers(None) == 3


def test_resolve_max_workers_limits_when_memory_low(monkeypatch):
    monkeypatch.delenv("DOXOADE_VULCAN_JOBS", raising=False)
    monkeypatch.setattr("doxoade.tools.vulcan.autopilot.os.cpu_count", lambda: 8)
    monkeypatch.setattr(VulcanAutopilot, "_available_mem_mb", staticmethod(lambda: 2048))
    assert VulcanAutopilot._resolve_max_workers(None) == 2


def test_resolve_max_workers_limits_when_memory_medium(monkeypatch):
    monkeypatch.delenv("DOXOADE_VULCAN_JOBS", raising=False)
    monkeypatch.setattr("doxoade.tools.vulcan.autopilot.os.cpu_count", lambda: 8)
    monkeypatch.setattr(VulcanAutopilot, "_available_mem_mb", staticmethod(lambda: 4096))
    assert VulcanAutopilot._resolve_max_workers(None) == 3


def test_process_target_passes_prevalidated_flag(monkeypatch):
    ap = object.__new__(VulcanAutopilot)
    ap.env = type("E", (), {"foundry": "/tmp/foundry", "bin_dir": "/tmp/bin"})()
    ap._pid_registry = {}

    captured = {}

    def fake_worker(task):
        captured.update(task)
        return {"ok": True, "err": None}

    monkeypatch.setattr("doxoade.tools.vulcan.autopilot._forge_worker", fake_worker)

    out = ap._process_target({"file": "a.py", "__vulcan_validated": True})
    assert out["ok"] is True
    assert captured.get("prevalidated") is True


def test_limit_auto_candidates_caps_by_default():
    candidates = [{"file": f"f{i}.py"} for i in range(20)]
    limited, trimmed = VulcanAutopilot._limit_auto_candidates(candidates)
    assert len(limited) == 12
    assert trimmed == 8


def test_limit_auto_candidates_can_be_configured(monkeypatch):
    monkeypatch.setenv("DOXOADE_VULCAN_AUTO_TARGET_CAP", "5")
    candidates = [{"file": f"f{i}.py"} for i in range(9)]
    limited, trimmed = VulcanAutopilot._limit_auto_candidates(candidates)
    assert [c["file"] for c in limited] == [f"f{i}.py" for i in range(5)]
    assert trimmed == 4
