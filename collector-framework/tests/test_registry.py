"""register_parser / get_parser / registry."""

from __future__ import annotations

from typing import Any

import pytest

from collector import (
    BaseParser,
    ParserNotFound,
    get_parser,
    register_parser,
    registry,
    unregister_parser,
)


class _Parser(BaseParser):
    name = 'demo'

    async def parse(self, response: Any):  # pragma: no cover - never run
        yield {}


@pytest.fixture
def demo():
    register_parser('demo')(_Parser)
    yield _Parser
    unregister_parser('demo')


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
