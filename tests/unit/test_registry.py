"""The parser registry: register / get / list, keyed by parser name."""

from __future__ import annotations

from typing import Any

import pytest
from collector import BaseParser

from tenders import ParserNotFound, get_parser, register_parser, registry
from tenders.registry import _REGISTRY


class _Parser(BaseParser):
    name = 'demo'

    async def parse(self, response: Any):  # pragma: no cover - never run
        yield {}


@pytest.fixture
def demo(monkeypatch):
    """Register a throwaway parser without leaking it into other tests.

    Reaches into the private dict on purpose: the public API has no way to undo
    a registration, and adding one just for tests is what we removed.
    """
    monkeypatch.setitem(_REGISTRY, 'demo', _Parser)
    return _Parser


def test_get_parser_returns_the_registered_class(demo):
    assert get_parser('demo') is demo


def test_registry_is_a_copy(demo):
    snapshot = registry()
    snapshot['demo'] = object  # type: ignore[assignment]
    assert get_parser('demo') is demo


def test_unknown_key_raises_parser_not_found():
    with pytest.raises(ParserNotFound):
        get_parser('nope')


def test_duplicate_registration_is_rejected(demo):
    with pytest.raises(ValueError, match='already registered'):
        register_parser('demo')(_Parser)
