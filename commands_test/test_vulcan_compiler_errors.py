import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.vulcan.compiler import VulcanCompiler


def test_format_verbose_build_error_contains_context():
    msg = VulcanCompiler._format_verbose_build_error(
        module_name="v_x",
        cmd=["python", "setup_tmp.py", "build_ext"],
        returncode=1,
        stdout="line1\nline2\n",
        stderr="err1\nerr2\n",
    )

    assert "Build failed for v_x (exit=1)" in msg
    assert "CMD: python setup_tmp.py build_ext" in msg
    assert "--- STDERR (tail) ---" in msg
    assert "err2" in msg
    assert "--- STDOUT (tail) ---" in msg
    assert "line2" in msg


def test_format_verbose_build_error_includes_dynamic_setup_script_name():
    msg = VulcanCompiler._format_verbose_build_error(
        module_name="v_mod",
        cmd=["python", "setup_v_mod.py", "build_ext", "--inplace"],
        returncode=1,
        stdout="",
        stderr="boom",
    )
    assert "setup_v_mod.py" in msg


def test_run_command_streaming_returns_tails(tmp_path):
    cmd = [
        sys.executable,
        "-c",
        "import sys; print('o1'); print('o2'); print('e1', file=sys.stderr)",
    ]
    code, out_tail, err_tail = VulcanCompiler._run_command_streaming(
        cmd,
        cwd=str(tmp_path),
        env={},
        max_tail_lines=10,
    )
    assert code == 0
    assert "o2" in out_tail
    assert "e1" in err_tail
