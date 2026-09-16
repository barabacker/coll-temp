"""The HTTP client a platform parser gets is assembled from what it declares.

The generic wiring is the framework's own test; this covers the three sites
whose declarations carry real quirks: the inprotect challenge, an expired
certificate, and a missing intermediate certificate.
"""

from __future__ import annotations

from typing import Any

import pytest
from collector import BaseParser, build_http_client, get_parser

from tenders.sources.fogsoft.inprotect import solve_inprotect

# Parser classes are built from platforms.toml and reached via the registry.
ArbBitLotParser = get_parser('arbbitlot')
CenterrParser = get_parser('centerr')
MetaInvestParser = get_parser('meta_invest')


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

    def _fake_bundle(path: str) -> str:
        seen['cert_path'] = path
        return '/tmp/fake-bundle.pem'

    monkeypatch.setattr('collector.http.factory.AsyncSession', _FakeSession)
    monkeypatch.setattr('collector.http.factory.ca_bundle_with_extra_cert', _fake_bundle)
    return seen


def test_fogsoft_parser_gets_inprotect_hook(captured):
    client = build_http_client(CenterrParser)
    assert solve_inprotect in client.middleware.response_middleware


def test_bare_parser_has_no_inprotect_hook(captured):
    client = build_http_client(_Bare)
    assert solve_inprotect not in client.middleware.response_middleware


def test_skip_tls_verify_disables_verification(captured):
    build_http_client(ArbBitLotParser)
    assert captured['session_kwargs'].get('verify') is False


def test_extra_ca_cert_resolved_against_parser_module(captured):
    build_http_client(MetaInvestParser)
    cert_path = captured['cert_path'].replace('\\', '/')
    assert cert_path.endswith(
        'sources/fogsoft/certs/meta_invest_globalsign_gcc_r3_dv_tls_ca_2020.pem'
    )
