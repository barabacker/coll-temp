"""Response wraps a raw client response and exposes a parsel Selector."""

from __future__ import annotations

from tests.conftest import FakeResponse

from collector import Request, Response

HTML = '<html><body><h1>Лот 42</h1><a href="/next">next</a></body></html>'


def test_status_text_and_metadata_come_from_raw_and_request():
    req = Request(url='https://example.test/', metadata={'page': 2})
    response = Response(FakeResponse(text=HTML, status_code=201), req)

    assert response.status == 201
    assert response.text == HTML
    assert response.metadata == {'page': 2}
    assert response.request is req


def test_selector_queries_the_body():
    response = Response(FakeResponse(text=HTML), Request(url='https://example.test/'))
    assert response.selector().css('h1::text').get() == 'Лот 42'


def test_raw_exposes_the_underlying_response():
    raw = FakeResponse(text=HTML)
    assert Response(raw, Request(url='https://example.test/')).raw is raw
