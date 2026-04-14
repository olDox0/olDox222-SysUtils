import ast
import importlib.util
from pathlib import Path


_module_path = Path('doxoade/commands/check_systems/check_structural.py')
_spec = importlib.util.spec_from_file_location('check_structural', _module_path)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)


def test_structural_risk_classifies_critical_for_import_hooks_and_exec():
    code = """
import sys
sys.meta_path.insert(0, object())
mod = {}
sys.modules['x'] = mod
exec('print(1)')
"""
    findings = {
        "dynamic_exec": 0,
        "sys_modules_mutation": 0,
        "meta_path_mutation": 0,
        "dynamic_import": 0,
        "runtime_attr_access": 0,
        "runtime_namespace": 0,
    }
    bucket = {k: 0 for k in findings}
    _mod._scan_tree(ast.parse(code), findings, bucket)
    assert _mod._classify_level(findings) == 3


def test_structural_risk_classifies_moderate_for_runtime_dynamics():
    findings = {
        "dynamic_exec": 0,
        "sys_modules_mutation": 0,
        "meta_path_mutation": 0,
        "dynamic_import": 3,
        "runtime_attr_access": 0,
        "runtime_namespace": 0,
    }
    assert _mod._classify_level(findings) == 1
