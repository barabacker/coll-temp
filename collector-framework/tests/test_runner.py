"""run_parser / crawl: build the client, run the crawl, hand back the parser."""

from __future__ import annotations

from typing import Any

from tests.conftest import FakeHttp

from collector import BaseParser, crawl, run_parser

URL = 'https://example.test/'


class _Counting(BaseParser):
    name = 'counting'
    start_urls = [URL]

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        self.saved: list[Any] = []

    async def parse(self, response: Any):
        yield {'url': response.request.url}

    async def process_item(self, item: Any) -> None:
        await super().process_item(item)
        self.ctx.sink.append(item)
        self.saved.append(item)


def _patch_client(monkeypatch) -> FakeHttp:
    """Replace the real client factory with a FakeHttp that closes cleanly."""
    http = FakeHttp()

    async def _aenter(self):
        return self

    async def _aexit(self, *exc_info):
        return None

    type(http).__aenter__ = _aenter
    type(http).__aexit__ = _aexit
    monkeypatch.setattr('collector.runner.build_http_client', lambda parser_cls: http)
    return http


def test_run_parser_returns_the_finished_parser(monkeypatch):
    _patch_client(monkeypatch)
    sink: list[Any] = []

    parser = run_parser(_Counting, sink=sink)

    assert parser.item_count == 1
    assert parser.saved == [{'url': URL}]
    assert sink == [{'url': URL}]


def test_run_parser_passes_params_through(monkeypatch):
    _patch_client(monkeypatch)
    parser = run_parser(_Counting, params={'max_pages': '2'}, sink=[])
    assert parser.ctx.params == {'max_pages': '2'}


def test_run_parser_logs_through_the_default_logger(monkeypatch, caplog):
    _patch_client(monkeypatch)

    class _Logging(_Counting):
        name = 'logging'

        async def parse(self, response: Any):
            await self.log('hello')
            yield {'url': response.request.url}

    with caplog.at_level('INFO', logger='collector.runner'):
        run_parser(_Logging, sink=[])

    assert '[logging] hello' in caplog.text


async def test_crawl_is_the_async_entry_point(monkeypatch):
    _patch_client(monkeypatch)
    parser = await crawl(_Counting, sink=[])
    assert parser.item_count == 1
