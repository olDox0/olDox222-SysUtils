from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from doxoade.tools.import_fixer import fix_project_imports, verify_project_imports


def test_fix_imports_rewrites_from_import_for_moved_module(tmp_path):
    root = tmp_path
    (root / "x" / "m").mkdir(parents=True)
    (root / "x" / "__init__.py").write_text("")
    (root / "x" / "m" / "__init__.py").write_text("")
    (root / "x" / "m" / "z.py").write_text("def a():\n    return 1\n")

    app = root / "app.py"
    app.write_text("from x.y.z import a, b\nprint(a)\n", encoding="utf-8")

    result = fix_project_imports(root)

    assert result.imports_changed == 1
    assert "from x.m.z import a, b" in app.read_text(encoding="utf-8")


def test_fix_imports_keeps_existing_valid_import(tmp_path):
    root = tmp_path
    (root / "x" / "m").mkdir(parents=True)
    (root / "x" / "__init__.py").write_text("")
    (root / "x" / "m" / "__init__.py").write_text("")
    (root / "x" / "m" / "z.py").write_text("def a():\n    return 1\n")

    app = root / "app.py"
    original = "from x.m.z import a\n"
    app.write_text(original, encoding="utf-8")

    result = fix_project_imports(root)

    assert result.imports_changed == 0
    assert app.read_text(encoding="utf-8") == original


def test_verify_project_imports_detects_without_rewrite(tmp_path):
    root = tmp_path
    (root / "x" / "m").mkdir(parents=True)
    (root / "x" / "__init__.py").write_text("")
    (root / "x" / "m" / "__init__.py").write_text("")
    (root / "x" / "m" / "z.py").write_text("def a():\n    return 1\n")

    app = root / "app.py"
    original = "from x.y.z import a, b\n"
    app.write_text(original, encoding="utf-8")

    result = verify_project_imports(root)

    assert result.files_changed == 1
    assert result.imports_changed == 1
    assert app.read_text(encoding="utf-8") == original


def test_fix_imports_rewrites_invalid_relative_to_absolute_module(tmp_path):
    root = tmp_path
    (root / "doxoade" / "commands").mkdir(parents=True)
    (root / "doxoade" / "tools").mkdir(parents=True)
    (root / "doxoade" / "__init__.py").write_text("")
    (root / "doxoade" / "commands" / "__init__.py").write_text("")
    (root / "doxoade" / "tools" / "__init__.py").write_text("")
    (root / "doxoade" / "tools" / "memory_pool.py").write_text("def finding_arena():\n    return 1\n")

    f = root / "doxoade" / "commands" / "sample.py"
    f.write_text("from ...tools.memory_pool import finding_arena\n", encoding="utf-8")

    result = fix_project_imports(root)

    assert result.imports_changed == 1
    assert f.read_text(encoding="utf-8") == "from doxoade.tools.memory_pool import finding_arena\n"


def test_verify_flags_deep_relative_import_for_canonical_absolute(tmp_path):
    root = tmp_path
    (root / "doxoade" / "commands" / "check_systems").mkdir(parents=True)
    (root / "doxoade" / "tools").mkdir(parents=True)
    (root / "doxoade" / "__init__.py").write_text("")
    (root / "doxoade" / "commands" / "__init__.py").write_text("")
    (root / "doxoade" / "commands" / "check_systems" / "__init__.py").write_text("")
    (root / "doxoade" / "tools" / "__init__.py").write_text("")
    (root / "doxoade" / "tools" / "memory_pool.py").write_text("def finding_arena():\n    return 1\n")

    f = root / "doxoade" / "commands" / "check_systems" / "check_engine.py"
    original = "from ...tools.memory_pool import finding_arena\n"
    f.write_text(original, encoding="utf-8")

    verify = verify_project_imports(root)
    assert verify.imports_changed == 1
    assert f.read_text(encoding="utf-8") == original

    fixed = fix_project_imports(root)
    assert fixed.imports_changed == 1
    assert f.read_text(encoding="utf-8") == "from doxoade.tools.memory_pool import finding_arena\n"
