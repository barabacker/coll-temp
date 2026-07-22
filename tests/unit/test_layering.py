"""Layer dependency invariant: core <- http <- sources, entrypoint on top.

Guards the architectural claim of the restructure so a future edit cannot
silently reintroduce an upward runtime import (see design doc section 3).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import collector.runner


def test_runner_does_not_import_sources():
    src = inspect.getsource(collector.runner)
    assert 'collector.sources' not in src
    assert 'fogsoft' not in src
    assert '_FOGSOFT_DIR' not in src


def _runtime_imports(module_path: Path) -> list[str]:
    """Module-level imported names, excluding those under ``if TYPE_CHECKING:``."""
    tree = ast.parse(module_path.read_text(encoding='utf-8'))

    type_checking_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            is_tc = (isinstance(test, ast.Name) and test.id == 'TYPE_CHECKING') or (
                isinstance(test, ast.Attribute) and test.attr == 'TYPE_CHECKING'
            )
            if is_tc:
                for child in ast.walk(node):
                    type_checking_nodes.add(id(child))

    names: list[str] = []
    for node in ast.walk(tree):
        if id(node) in type_checking_nodes:
            continue
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


_SRC = Path(collector.__file__).parent


def test_core_has_no_runtime_dependency_on_http_or_sources():
    for py in sorted((_SRC / 'core').rglob('*.py')):
        for imported in _runtime_imports(py):
            assert not imported.startswith('collector.http'), f'{py.name} runtime-imports {imported}'
            assert not imported.startswith(
                'collector.sources'
            ), f'{py.name} runtime-imports {imported}'


def test_http_has_no_runtime_dependency_on_sources():
    for py in sorted((_SRC / 'http').rglob('*.py')):
        for imported in _runtime_imports(py):
            assert not imported.startswith(
                'collector.sources'
            ), f'{py.name} runtime-imports {imported}'
