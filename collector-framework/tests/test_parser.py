"""BaseParser.crawl(): queueing, item handling, concurrency and error surfacing."""

from __future__ import annotations

from typing import Any

import pytest
from tests.conftest import FakeHttp

from collector import BaseParser, Request

PAGE_1 = 'https://example.test/p1'
PAGE_2 = 'https://example.test/p2'


class _TwoPages(BaseParser):
    """Emits one item per page and follows a single link from page 1."""

    name = 'two_pages'
    start_urls = [PAGE_1]

    async def parse(self, response: Any):
        yield {'url': response.request.url}
        if response.request.url == PAGE_1:
            yield self.request(PAGE_2)


async def test_crawl_follows_requests_and_counts_items(ctx_factory):
    http = FakeHttp()
    ctx, _ = ctx_factory(http)
    parser = _TwoPages(ctx)

    assert await parser.crawl() == 2
    assert {url for _, url in http.calls} == {PAGE_1, PAGE_2}


async def test_process_item_override_receives_every_item(ctx_factory):
    seen: list[Any] = []

    class _Collecting(_TwoPages):
        async def process_item(self, item: Any) -> None:
            await super().process_item(item)
            seen.append(item)

    ctx, _ = ctx_factory(FakeHttp())
    parser = _Collecting(ctx)
    await parser.crawl()

    assert [item['url'] for item in seen] == [PAGE_1, PAGE_2]
    assert parser.item_count == 2


async def test_callback_metadata_reaches_the_response(ctx_factory):
    class _WithMeta(BaseParser):
        name = 'with_meta'
        start_urls = [PAGE_1]

        async def parse(self, response: Any):
            yield self.request(PAGE_2, callback=self.parse_detail, metadata={'page': 7})

        async def parse_detail(self, response: Any):
            yield {'page': response.metadata['page']}

    seen: list[Any] = []

    class _Collecting(_WithMeta):
        async def process_item(self, item: Any) -> None:
            seen.append(item)

    ctx, _ = ctx_factory(FakeHttp())
    await _Collecting(ctx).crawl()

    assert seen == [{'page': 7}]


async def test_request_defaults_to_parse_as_callback(ctx_factory):
    ctx, _ = ctx_factory(FakeHttp())
    req = _TwoPages(ctx).request(PAGE_1)
    assert isinstance(req, Request)
    assert req.callback.__name__ == 'parse'


async def test_concurrency_is_read_from_params(ctx_factory):
    ctx, _ = ctx_factory(FakeHttp(), params={'concurrency': '3'})
    parser = _TwoPages(ctx)
    assert await parser.crawl() == 2


async def test_first_error_is_reraised_after_the_crawl(ctx_factory):
    class _Failing(BaseParser):
        name = 'failing'
        start_urls = [PAGE_1, PAGE_2]

        async def parse(self, response: Any):
            if response.request.url == PAGE_1:
                raise ValueError('bad page')
            yield {'ok': True}

    ctx, _ = ctx_factory(FakeHttp())
    parser = _Failing(ctx)

    with pytest.raises(ValueError, match='bad page'):
        await parser.crawl()
    # The other page was still handled: one bad page does not kill the worker.
    assert parser.item_count == 1


async def test_log_is_a_noop_without_a_log_callable():
    from collector import ParserContext

    parser = _TwoPages(ParserContext(http=FakeHttp()))
    await parser.log('nothing blows up')


async def test_log_writes_through_the_context(ctx_factory):
    class _Logging(_TwoPages):
        async def parse(self, response: Any):
            await self.log(f'visited {response.request.url}')
            yield {'url': response.request.url}

    ctx, lines = ctx_factory(FakeHttp())
    await _Logging(ctx).crawl()

    assert lines == [f'visited {PAGE_1}']


async def test_start_requests_defaults_to_start_urls(ctx_factory):
    ctx, _ = ctx_factory(FakeHttp())
    reqs = [req async for req in _TwoPages(ctx).start_requests()]
    assert [r.url for r in reqs] == [PAGE_1]


async def test_start_requests_can_be_overridden(ctx_factory):
    class _PostStart(BaseParser):
        name = 'post_start'

        async def start_requests(self):
            yield self.request(PAGE_1, method='POST', data={'q': '1'}, metadata={'seed': True})

        async def parse(self, response: Any):
            yield {'seed': response.metadata['seed'], 'method': response.request.method}

    seen: list[Any] = []

    class _Collecting(_PostStart):
        async def process_item(self, item: Any) -> None:
            seen.append(item)

    http = FakeHttp()
    ctx, _ = ctx_factory(http)
    await _Collecting(ctx).crawl()

    assert seen == [{'seed': True, 'method': 'POST'}]
    assert http.calls == [('POST', PAGE_1)]


async def test_settings_concurrency_is_the_default_and_params_win(ctx_factory):
    from dataclasses import replace

    class _Parallel(_TwoPages):
        settings = replace(_TwoPages.settings, concurrency=4)

    ctx, _ = ctx_factory(FakeHttp())
    assert _Parallel(ctx).settings.concurrency == 4

    ctx, _ = ctx_factory(FakeHttp(), params={'concurrency': '2'})
    assert await _Parallel(ctx).crawl() == 2
