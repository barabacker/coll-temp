"""TenderRuson — base parser for rus-on bankruptcy-auction sites.

A subclass sets ``name``, ``DOMAIN`` and (when it differs) ``LISTING_PATH``
(``bankrot/trade_list.php`` vs ``tradelist.php``). ``parse`` reduces the listing
to distinct trades and dives into each ``trade_view.php`` detail;
``parse_lots_page`` expands the (uniform) detail into one item per lot. The
listing carries no reliable price, so the dive is mandatory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar
from urllib.parse import urljoin

from collector.core.spider import BaseParser, Request, Response
from collector.sources.ruson.parsing.detail import parse_lots
from collector.sources.ruson.parsing.listing import (
    find_next_page,
    parse_listing,
    read_max_pages,
)


class TenderRuson(BaseParser):
    """Base parser for rus-on sites (heterogeneous listing, uniform detail)."""

    DOMAIN: ClassVar[str]
    LISTING_PATH: ClassVar[str] = 'bankrot/trade_list.php'
    BASE_URL: ClassVar[str]

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        # De-duplicate trades across the whole crawl: a trade can reappear on a
        # later page (per-lot listings span pages; live re-sorting on trade
        # listings), and must be dived — and emitted — only once.
        self._seen_trades: set[object] = set()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if 'DOMAIN' in cls.__dict__ or 'LISTING_PATH' in cls.__dict__:
            domain = cls.DOMAIN.rstrip('/')
            cls.BASE_URL = f'{domain}/{cls.LISTING_PATH}'
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
            detail_url = trade.get('detail_url')
            nid = trade.get('trade_nid')
            if not detail_url or nid in seen:
                continue
            seen.add(nid)
            yield self.request(
                urljoin(response.request.url, str(detail_url)),
                callback=self.parse_lots_page,
                metadata={'trade': trade},
            )

        next_page = find_next_page(sel, page)
        max_pages = read_max_pages(self.ctx.params)
        if next_page and (max_pages is None or page < max_pages):
            yield self.request(f'{self.BASE_URL}?pagenum={next_page}', metadata={'page': next_page})

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
