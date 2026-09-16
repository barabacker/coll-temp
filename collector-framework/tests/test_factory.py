"""build_http_client wires hooks and TLS from what the parser class declares."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from collector import BaseParser, build_http_client


class _Bare(BaseParser):
    name = '_bare'

    async def parse(self, response: Any):  # pragma: no cover - never run
        yield {}


async def _hook(response: Any, *, session: Any, retry: Any) -> Any:  # pragma: no cover
    return response


class _Hooked(_Bare):
    name = '_hooked'
    RESPONSE_HOOKS = (_hook,)


class _NoVerify(_Bare):
    name = '_no_verify'
    SKIP_TLS_VERIFY = True


class _ExtraCert(_Bare):
    name = '_extra_cert'
    EXTRA_CA_CERT = 'certs/site.pem'


@pytest.fixture
def captured(monkeypatch):
    """Capture AsyncSession kwargs and the resolved extra-cert path."""
    seen: dict[str, Any] = {}

    class _FakeSession:
        def __init__(self, **kwargs: Any) -> None:
            seen['session_kwargs'] = kwargs

        async def close(self) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr('collector.http.factory.AsyncSession', _FakeSession)

    def _fake_bundle(path: str) -> str:
        seen['cert_path'] = path
        return '/tmp/fake-bundle.pem'

    monkeypatch.setattr('collector.http.factory.ca_bundle_with_extra_cert', _fake_bundle)
    return seen


def test_defaults_impersonate_a_browser(captured):
    build_http_client(_Bare)
    assert captured['session_kwargs'] == {'impersonate': 'chrome'}


def test_logging_hooks_are_always_registered(captured):
    client = build_http_client(_Bare)
    assert len(client.middleware.request_middleware) == 1
    assert len(client.middleware.response_middleware) == 1


def test_declared_response_hooks_run_before_the_logging_hook(captured):
    client = build_http_client(_Hooked)
    assert list(client.middleware.response_middleware)[0] is _hook


def test_skip_tls_verify_disables_verification(captured):
    build_http_client(_NoVerify)
    assert captured['session_kwargs']['verify'] is False


def test_extra_ca_cert_is_resolved_against_the_parser_module(captured):
    build_http_client(_ExtraCert)
    expected = Path(__file__).parent / 'certs' / 'site.pem'
    assert Path(captured['cert_path']) == expected
    assert captured['session_kwargs']['verify'] == '/tmp/fake-bundle.pem'
