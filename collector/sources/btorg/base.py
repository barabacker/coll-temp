"""TenderBtorg — base parser for btorg/edoc-ETP bankruptcy-auction sites.

A subclass sets ``name`` (registry key) and ``DOMAIN``. ``parse`` reads the
``table.data`` listing (one row per trade), then dives per trade into the AJAX
lots endpoint; ``parse_lots_page`` expands the fragment into one item per lot
(lot-centric LotSink). The listing carries no price, so the dive is mandatory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar
from urllib.parse import urljoin

from collector.core.spider import BaseParser, Request, Response
from collector.sources.btorg.parsing.listing import (
    find_next_page,
    parse_listing,
    read_max_pages,
)
from collector.sources.btorg.parsing.lots import parse_lots


class TenderBtorg(BaseParser):
    """Base parser for btorg/edoc-ETP sites (HTML table listing + AJAX lots)."""

    DOMAIN: ClassVar[str]
    LISTING_PATH: ClassVar[str] = 'etp/trade/list.html'
    BASE_URL: ClassVar[str]

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        # De-duplicate trades across the whole crawl (a trade can reappear on a
        # later listing page); dive and emit each only once.
        self._seen_trades: set[object] = set()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if 'DOMAIN' in cls.__dict__:
            cls.BASE_URL = f'{cls.DOMAIN.rstrip("/")}/{cls.LISTING_PATH}'
            cls.start_urls = [cls.BASE_URL]

    async def parse(self, response: Response) -> AsyncIterator[Request | dict[str, Any]]:
        sel = response.selector()
        trades = parse_listing(sel, self.name)
        page = response.metadata.get('page', 1)
        await self.log(
            f'{response.request.method} | {response.status} | page={page} '
            f'| trades={len(trades)}'
        )
        seen = self._seen_trades
        for trade in trades:
            lots_url = trade.get('lots_url')
            pid = trade.get('purchase_id')
            if not lots_url or pid in seen:
                continue
            seen.add(pid)
            yield self.request(
                urljoin(response.request.url, str(lots_url)),
                callback=self.parse_lots_page,
                metadata={'trade': trade},
                headers={'X-Requested-With': 'XMLHttpRequest'},
            )

        next_page = find_next_page(sel, page)
        max_pages = read_max_pages(self.ctx.params)
        if next_page and (max_pages is None or page < max_pages):
            yield self.request(f'{self.BASE_URL}?page={next_page}', metadata={'page': next_page})

    async def parse_lots_page(self, response: Response) -> AsyncIterator[Request | dict[str, Any]]:
        sel = response.selector()
        trade = response.metadata['trade']
        lots = parse_lots(sel, trade)
        await self.log(
            f'{response.request.method} | {response.status} '
            f'| lots trade={trade.get("trade_id")} | lots={len(lots)}'
        )
        for item in lots:
            if item.get('lot_id'):
                yield item
