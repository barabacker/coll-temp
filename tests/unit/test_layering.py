"""The runner entrypoint must not depend on any concrete engine (sources)."""

from __future__ import annotations

import inspect

import collector.runner


def test_runner_does_not_import_sources():
    src = inspect.getsource(collector.runner)
    assert 'collector.sources' not in src
    assert 'fogsoft' not in src
    assert '_FOGSOFT_DIR' not in src
