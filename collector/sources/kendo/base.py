"""TenderKendo — base parser for Kendo-ETP bankruptcy-auction sites.

A subclass sets ``name`` (registry key) and ``DOMAIN``. ``parse`` reads the
listing as a de-duplicated set of trade detail URLs and enqueues a dive per
trade; ``parse_detail`` reads authoritative trade-level fields from the detail
page and expands the trade into one item per lot (lot-centric LotSink). This
absorbs the two listing card templates (per-trade and per-lot) uniformly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar
from urllib.parse import urljoin

from collector.core.spider import BaseParser, Request, Response
from collector.sources.kendo.parsing.detail import (
    parse_documents,
    parse_lots,
    parse_main_info,
)
from collector.sources.kendo.parsing.listing import (
    find_next_page,
    parse_listing,
    read_max_pages,
)


class TenderKendo(BaseParser):
    """Base parser for Kendo-ETP sites (server-rendered listing + detail)."""

    DOMAIN: ClassVar[str]
    LISTING_PATH: ClassVar[str] = 'lots'
    BASE_URL: ClassVar[str]

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
        for trade in trades:
            detail_url = trade.get('detail_url')
            if detail_url:
                yield self.request(
                    urljoin(response.request.url, str(detail_url)),
                    callback=self.parse_detail,
                    metadata={'trade': trade},
                )

        next_page = find_next_page(sel, page)
        max_pages = read_max_pages(self.ctx.params)
        if next_page and (max_pages is None or page < max_pages):
            yield self.request(f'{self.BASE_URL}?page={next_page}', metadata={'page': next_page})

    async def parse_detail(self, response: Response) -> AsyncIterator[Request | dict[str, Any]]:
        sel = response.selector()
        trade = response.metadata['trade']
        main = parse_main_info(sel)
        docs = parse_documents(sel)
        organizer = main.get('Наименование')
        # Trade-level fingerprint fields come from the authoritative detail page,
        # not the listing card (which is lot-level on the per-lot template).
        trade_ctx = dict(trade)
        trade_ctx['trade_title'] = main.get('Номер торгов') or trade.get('trade_title')
        trade_ctx['bidding_date'] = main.get('Окончание приема заявок') or trade.get('bidding_date')
        trade_ctx['event_date'] = main.get('Подведение результатов торгов') or trade.get('event_date')
        lots = parse_lots(sel, trade_ctx)
        await self.log(
            f'{response.request.method} | {response.status} '
            f'| detail trade={trade.get("trade_id")} | lots={len(lots)}'
        )
        for item in lots:
            item['organizer'] = organizer
            item['detail'] = main
            item['attachments'] = docs
            yield item
