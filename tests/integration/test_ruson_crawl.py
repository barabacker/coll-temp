"""End-to-end rus-on crawl over fixtures via a fake HTTP client (no network)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from collector.core.spider import ParserContext
from collector.core.storage.contracts import ChangeStatus
from collector.sources.ruson.platforms import NistpParser

FIX = Path(__file__).parents[1] / 'fixtures' / 'ruson'
LISTING = (FIX / 'nistp_listing.html').read_text(encoding='utf-8')
DETAIL = (FIX / 'nistp_detail.html').read_text(encoding='utf-8')

FINGERPRINT_KEYS = {'status', 'price', 'bidding_date', 'event_date', 'trade_title'}


class _Raw:
    def __init__(self, text: str) -> None:
        self.status_code = 200
        self.text = text
        self.content = text.encode('utf-8')


class _FakeHttp:
    """Listing fixture for trade_list URLs, detail fixture for trade_view."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> _Raw:
        self.calls.append(url)
        if 'trade_view.php' in url:
            return _Raw(DETAIL)
        return _Raw(LISTING)


class _Sink:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    async def get_fingerprints(self, source: str, lot_ids: Any) -> dict[str, str]:
        return {}

    async def save(self, item: dict[str, Any]) -> ChangeStatus:
        self.items.append(item)
        return ChangeStatus.NEW


def test_ruson_crawl_expands_trades_into_lots():
    sink = _Sink()
    http = _FakeHttp()
    ctx = ParserContext(http=http, params={'max_pages': '1'}, lot_sink=sink)
    parser = NistpParser(ctx)

    total = asyncio.run(parser.crawl())

    # 20 distinct trades on page 1, the detail fixture has 1 lot each -> 20 items.
    assert total == 20
    assert len(sink.items) == 20
    assert any('trade_view.php' in c for c in http.calls)  # dived to detail
    assert not any('pagenum=2' in c for c in http.calls)  # max_pages=1 stopped paging
    first = sink.items[0]
    assert FINGERPRINT_KEYS <= first.keys()
    assert first['lot_id'] == '68240_1'
    assert first['price'] == 1315000.0
    assert first['status'] == 'Торги объявлены'
    assert first['detail']


def test_ruson_crawl_dedupes_trades_across_pages():
    """The same listing served on pages 1 and 2 must dive each trade once.

    Regression for the cross-page duplicate-lot_id bug (crawl-level _seen_trades).
    """
    sink = _Sink()
    http = _FakeHttp()  # serves the same LISTING for every trade_list URL
    ctx = ParserContext(http=http, params={'max_pages': '2'}, lot_sink=sink)
    parser = NistpParser(ctx)

    asyncio.run(parser.crawl())

    detail_calls = [c for c in http.calls if 'trade_view.php' in c]
    # 20 distinct trades: dived exactly once even though the pager advanced to
    # page 2 with identical content (without dedup this would be 40).
    assert len(detail_calls) == 20
    assert len(detail_calls) == len(set(detail_calls))
    assert len(sink.items) == 20
    assert any('pagenum=2' in c for c in http.calls)  # page 2 was fetched
