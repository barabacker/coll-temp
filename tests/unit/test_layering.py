"""Layer dependency invariants: framework <- domain core <- sources.

Guards the boundary the framework extraction established, so a future edit
cannot quietly import the domain back into the engine — the thing that would
make the split meaningless.
"""

from __future__ import annotations

import ast
from pathlib import Path

import collector
import tenders


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


_FRAMEWORK = Path(collector.__file__).parent
_DOMAIN = Path(tenders.__file__).parent


def test_framework_knows_nothing_about_the_domain():
    """The whole point of the extraction: collector must stand alone."""
    for py in sorted(_FRAMEWORK.rglob('*.py')):
        for imported in _runtime_imports(py):
            assert not imported.startswith('tenders'), f'{py.name} runtime-imports {imported}'


def test_domain_core_does_not_import_sources():
    """Engines may depend on core; core may not depend on an engine."""
    for py in sorted((_DOMAIN / 'core').rglob('*.py')):
        for imported in _runtime_imports(py):
            assert not imported.startswith(
                'tenders.sources'
            ), f'{py.name} runtime-imports {imported}'


def test_domain_core_does_not_reach_into_the_http_layer():
    """Core speaks to the network only through the parser the framework gives it."""
    for py in sorted((_DOMAIN / 'core').rglob('*.py')):
        for imported in _runtime_imports(py):
            assert not imported.startswith(
                'collector.http'
            ), f'{py.name} runtime-imports {imported}'


def test_runner_does_not_import_sources():
    for imported in _runtime_imports(_DOMAIN / 'runner.py'):
        assert not imported.startswith('tenders.sources')
