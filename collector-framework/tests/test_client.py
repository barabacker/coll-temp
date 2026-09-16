"""HttpClient: hooks wrap every request, and network errors are retried."""

from __future__ import annotations

from typing import Any

import pytest
from curl_cffi.requests.exceptions import RequestException
from tests.conftest import FakeResponse

from collector import HttpClient, Middleware


class _FakeSession:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.closed = False

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        self.calls.append((method, url, kwargs))
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def close(self) -> None:
        self.closed = True


async def test_request_hook_can_mutate_kwargs():
    session = _FakeSession([FakeResponse(text='ok')])
    mw = Middleware()

    async def add_header(method: str, url: str, kwargs: dict[str, Any]) -> None:
        kwargs.setdefault('headers', {})['X-Test'] = '1'

    mw.request(add_header)
    client = HttpClient(session, mw)

    await client.request('GET', 'https://example.test/')

    assert session.calls[0][2]['headers'] == {'X-Test': '1'}


async def test_response_hook_may_replace_the_response():
    session = _FakeSession([FakeResponse(text='original')])
    mw = Middleware()

    async def swap(response: Any, *, session: Any, retry: Any) -> Any:
        return FakeResponse(text='replaced')

    mw.response(swap)
    client = HttpClient(session, mw)

    assert (await client.request('GET', 'https://example.test/')).text == 'replaced'


async def test_response_hook_can_retry_the_request():
    """A hook that solves a challenge re-runs the request and returns the new one."""
    session = _FakeSession([FakeResponse(text='challenge'), FakeResponse(text='content')])
    mw = Middleware()

    async def solve(response: Any, *, session: Any, retry: Any) -> Any:
        if response.text == 'challenge':
            return await retry()
        return response

    mw.response(solve)
    client = HttpClient(session, mw)

    assert (await client.request('GET', 'https://example.test/')).text == 'content'
    assert len(session.calls) == 2


async def test_network_errors_are_retried_then_the_response_returned(monkeypatch):
    monkeypatch.setattr('collector.http.client.HttpClient.request.retry.wait', lambda *a, **k: 0)
    session = _FakeSession([RequestException('boom'), FakeResponse(text='ok')])
    client = HttpClient(session, Middleware())

    assert (await client.request('GET', 'https://example.test/')).text == 'ok'
    assert len(session.calls) == 2


async def test_retries_give_up_and_reraise(monkeypatch):
    monkeypatch.setattr('collector.http.client.HttpClient.request.retry.wait', lambda *a, **k: 0)
    session = _FakeSession([RequestException('boom')] * 4)
    client = HttpClient(session, Middleware())

    with pytest.raises(RequestException):
        await client.request('GET', 'https://example.test/')
    assert len(session.calls) == 4


async def test_context_manager_closes_the_session():
    session = _FakeSession([])
    async with HttpClient(session, Middleware()):
        pass
    assert session.closed
