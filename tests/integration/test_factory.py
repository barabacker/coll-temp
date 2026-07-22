"""build_http_client wires hooks and TLS from the parser class, engine-agnostic."""

from __future__ import annotations

from typing import Any

import pytest

from collector.core.spider import BaseParser
from collector.sources.fogsoft.inprotect import solve_inprotect
from collector.sources.fogsoft.platforms import (
    ArbBitLotParser,
    CenterrParser,
    MetaInvestParser,
)


class _Bare(BaseParser):
    name = '_bare_test'

    async def parse(self, response: Any):  # pragma: no cover - never run
        yield {}


@pytest.fixture
def captured(monkeypatch):
    """Capture AsyncSession kwargs and the resolved extra-cert path."""
    seen: dict[str, Any] = {}

    class _FakeSession:
        def __init__(self, **kwargs: Any):
            seen['session_kwargs'] = kwargs

        async def close(self) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr('collector.http.factory.AsyncSession', _FakeSession)
    monkeypatch.setattr(
        'collector.http.factory.ca_bundle_with_extra_cert',
        lambda path: seen.setdefault('cert_path', path) or '/tmp/fake-bundle.pem',
    )
    return seen


def test_fogsoft_parser_gets_inprotect_hook(captured):
    from collector.http.factory import build_http_client

    client = build_http_client(CenterrParser)
    assert solve_inprotect in client.middleware.response_middleware


def test_bare_parser_has_no_inprotect_hook(captured):
    from collector.http.factory import build_http_client

    client = build_http_client(_Bare)
    assert solve_inprotect not in client.middleware.response_middleware


def test_skip_tls_verify_disables_verification(captured):
    from collector.http.factory import build_http_client

    build_http_client(ArbBitLotParser)
    assert captured['session_kwargs'].get('verify') is False


def test_extra_ca_cert_resolved_against_parser_module(captured):
    from collector.http.factory import build_http_client

    build_http_client(MetaInvestParser)
    cert_path = captured['cert_path'].replace('\\', '/')
    assert cert_path.endswith(
        'sources/fogsoft/certs/meta_invest_globalsign_gcc_r3_dv_tls_ca_2020.pem'
    )
