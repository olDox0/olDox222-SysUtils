from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from energy_sys.core import process_tuner


class FakeProcess:
    def __init__(
        self,
        pid: int = 4321,
        name: str = "cpu_affinity_stress.py",
        create_time: float = 1234.5,
    ) -> None:
        self.pid = pid
        self._name = name
        self._create_time = create_time
        self.affinity = [0, 1, 2, 3]

    def name(self) -> str:
        return self._name

    def create_time(self) -> float:
        return self._create_time

    def cpu_affinity(self, cpus: list[int] | None = None) -> list[int] | None:
        if cpus is None:
            return list(self.affinity)
        self.affinity = list(cpus)
        return None


class ProcessTunerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(process_tuner, "REPORT_DIR", root),
            patch.object(process_tuner, "STATE_FILE", root / "process_affinity_state.json"),
            patch.object(process_tuner, "HISTORY_FILE", root / "process_affinity_history.jsonl"),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

        self.process = FakeProcess()
        process_patch = patch.object(
            process_tuner.psutil, "Process", return_value=self.process
        )
        process_patch.start()
        self.addCleanup(process_patch.stop)

    def test_original_affinity_survives_mode_changes_and_restores(self) -> None:
        with patch.object(process_tuner, "get_core_indices", return_value=[2, 3]):
            ok, message, _ = process_tuner.apply_process_affinity(4321, "perf")
        self.assertTrue(ok, message)
        self.assertEqual(self.process.affinity, [2, 3])

        with patch.object(process_tuner, "get_core_indices", return_value=[0, 1]):
            ok, message, _ = process_tuner.apply_process_affinity(4321, "eco")
        self.assertTrue(ok, message)
        self.assertEqual(self.process.affinity, [0, 1])

        ok, message, _ = process_tuner.restore_process_affinity(4321)
        self.assertTrue(ok, message)
        self.assertEqual(self.process.affinity, [0, 1, 2, 3])
        self.assertNotIn("4321", process_tuner._load_state())

        events = process_tuner.get_affinity_history()
        self.assertEqual(
            [event["action"] for event in events],
            ["apply", "apply", "restore"],
        )
        self.assertEqual(events[1]["original_affinity"], [0, 1, 2, 3])

    def test_pid_reuse_blocks_restore(self) -> None:
        with patch.object(process_tuner, "get_core_indices", return_value=[2, 3]):
            ok, message, _ = process_tuner.apply_process_affinity(4321, "perf")
        self.assertTrue(ok, message)

        self.process._create_time = 9999.0
        current = list(self.process.affinity)
        ok, message, _ = process_tuner.restore_process_affinity(4321)

        self.assertFalse(ok)
        self.assertIn("outro processo", message)
        self.assertEqual(self.process.affinity, current)
        self.assertIn("4321", process_tuner._load_state())

    def test_normal_without_saved_state_does_not_change_affinity(self) -> None:
        original = list(self.process.affinity)
        ok, message, _ = process_tuner.restore_process_affinity(4321)

        self.assertFalse(ok)
        self.assertIn("nada foi alterado", message)
        self.assertEqual(self.process.affinity, original)

    def test_windows_reserved_pid_is_rejected(self) -> None:
        with patch.object(process_tuner, "get_core_indices", return_value=[2, 3]):
            ok, message, _ = process_tuner.apply_process_affinity(4, "perf")
        self.assertFalse(ok)
        self.assertIn("reservado pelo Windows", message)

    def test_exited_process_state_is_removed(self) -> None:
        with patch.object(process_tuner, "get_core_indices", return_value=[2, 3]):
            ok, message, _ = process_tuner.apply_process_affinity(4321, "perf")
        self.assertTrue(ok, message)

        with patch.object(
            process_tuner.psutil,
            "Process",
            side_effect=process_tuner.psutil.NoSuchProcess(4321),
        ):
            ok, message, _ = process_tuner.restore_process_affinity(4321)

        self.assertTrue(ok, message)
        self.assertIn("registro obsoleto removido", message)
        self.assertNotIn("4321", process_tuner._load_state())

    def test_unknown_topology_fails_closed_without_guessing(self) -> None:
        with (
            patch.object(process_tuner.psutil, "cpu_count", return_value=4),
            patch.object(
                process_tuner.power_strategies,
                "get_hybrid_cpu_topology",
                return_value={i: "Núcleo Padrão" for i in range(4)},
            ),
        ):
            self.assertEqual(process_tuner.get_core_indices("p-cores"), [])
            self.assertEqual(process_tuner.get_core_indices("e-cores"), [])


if __name__ == "__main__":
    unittest.main()
