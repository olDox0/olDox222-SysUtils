from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.diagnostic.inspector import SystemInspector
from doxoade.tools.git import _get_detailed_diff_stats


def test_check_git_health_uses_target_file_parent_as_cwd(tmp_path):
    file_path = tmp_path / "proj" / "src" / "main.py"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("print('ok')")

    expected_cwd = str(file_path.parent)

    with patch("doxoade.diagnostic.inspector._run_git_command") as mock_git, \
         patch("doxoade.diagnostic.inspector._get_last_commit_info", return_value=None), \
         patch("doxoade.diagnostic.inspector._get_detailed_diff_stats", return_value=[]):
        mock_git.side_effect = ["true", "work", ""]

        data = SystemInspector().check_git_health(detailed=False, target_path=str(file_path))

    assert data["is_git_repo"] is True
    calls = mock_git.call_args_list
    assert calls[0].kwargs.get("cwd") == expected_cwd
    assert calls[1].kwargs.get("cwd") == expected_cwd
    assert calls[2].kwargs.get("cwd") == expected_cwd


def test_get_detailed_diff_stats_handles_binary_numstat():
    with patch("doxoade.tools.git._run_git_command") as mock_git:
        mock_git.side_effect = [
            "-\t-\tassets/logo.png\n3\t1\tsrc/a.py",
            ""  # sem diff textual necessário para este teste
        ]

        changes = _get_detailed_diff_stats(show_code=False)

    # sem diff textual não há entradas em changes, mas também não deve explodir
    assert changes == []
