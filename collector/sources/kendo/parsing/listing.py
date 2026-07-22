"""Parse the trade listing (/lots?page=N) on Kendo-ETP sites.

Each listing card is ``a.block-lot`` whose ``href`` is the trade detail URL.
The card holds the trade title, the trade number ("10775–ОАОФ"), the status,
and three dates keyed by the icon ``title`` attribute.
"""

from __future__ import annotations

import logging
import re

from parsel import Selector

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r'\s+')
_PAGE_RE = re.compile(r'page=(\d+)')
_DIGITS_RE = re.compile(r'\d+')


def clean(value: str | None) -> str | None:
    """Collapse whitespace to single spaces. None for empty."""
    if value is None:
        return None
    cleaned = _WS_RE.sub(' ', value).strip()
    return cleaned or None


def read_max_pages(params: dict[str, str]) -> int | None:
    """Read ``max_pages`` from job params. None means no limit."""
    raw = params.get('max_pages')
    if raw is None or raw == '':
        return None
    try:
        value = int(raw)
    except (ValueError, TypeError):
        logger.warning('kendo.bad_max_pages value=%s', raw)
        return None
    return value if value > 0 else None


def _date_by_title(card: Selector, title: str) -> str | None:
    return clean(card.xpath(f'.//nobr[i[@title="{title}"]]/text()').get())


def parse_listing(selector: Selector, source: str) -> list[dict[str, object]]:
    """Parse trade cards on a /lots page into trade dicts."""
    trades: list[dict[str, object]] = []
    for card in selector.xpath('//a[contains(@class, "block-lot")][@href]'):
        number = clean(
            card.xpath('.//span[contains(@class, "bold")]/a[contains(@class, "blue-text")]/text()').get()
        )
        trade_id = None
        trade_type = None
        if number:
            m = _DIGITS_RE.search(number)
            trade_id = m.group(0) if m else None
            parts = number.split('–')
            trade_type = clean(parts[1]) if len(parts) == 2 else None
        trades.append(
            {
                'trade_id': trade_id,
                'trade_number': number,
                'trade_type': trade_type,
                'trade_title': clean(
                    card.xpath('.//a[contains(@class, "blue-text") and contains(@class, "bold")]/text()').get()
                ),
                'detail_url': card.xpath('./@href').get(),
                'status': clean(
                    card.xpath('.//span[contains(@class, "competition-status-text")]/text()').get()
                ),
                'start_date': _date_by_title(card, 'Начало приема заявок'),
                'bidding_date': _date_by_title(card, 'Окончание приема заявок'),
                'event_date': _date_by_title(card, 'Подведение итогов'),
                '_source': source,
            }
        )
    return trades


def find_next_page(selector: Selector, current_page: int) -> int | None:
    """Smallest pager page number greater than ``current_page``, or None."""
    pages: list[int] = []
    for href in selector.xpath(
        '//ul[contains(@class, "pagination")]//a[contains(@href, "page=")]/@href'
    ).getall():
        m = _PAGE_RE.search(href)
        if m:
            pages.append(int(m.group(1)))
    nxt = [p for p in pages if p > current_page]
    return min(nxt) if nxt else None
