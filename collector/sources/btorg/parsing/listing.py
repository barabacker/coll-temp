"""Parse the trade listing (/etp/trade/list.html?page=N) on btorg/edoc-ETP sites.

The listing is an HTML ``table.data``; each ``<tr onclick=…>`` is one trade. The
trade's internal purchase id (used to fetch its lots) lives in the row's
``onclick`` (``…general.html?id=NNN…``); the visible columns are number, debtor,
organizer + object description, status, date.
"""

from __future__ import annotations

import logging
import re

from parsel import Selector

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r'\s+')
_PAGE_RE = re.compile(r'page=(\d+)')
_DIGITS_RE = re.compile(r'\d+')
_ID_RE = re.compile(r'id=(\d+)')
_PRICE_HEAD_RE = re.compile(r'[\d\s\xa0.,]+')

# The AJAX endpoint that returns a trade's lots (with prices).
LOTS_PATH = '/etp/trade/inner-view-lots.html'


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
        logger.warning('btorg.bad_max_pages value=%s', raw)
        return None
    return value if value > 0 else None


def parse_price(value: str | None) -> float | None:
    """Parse "280 000,00 руб, НДС не облагается" → 280000.0.

    Takes the leading numeric run (space/nbsp thousands, comma decimal) and
    ignores the trailing currency/VAT text.
    """
    if value is None:
        return None
    m = _PRICE_HEAD_RE.match(value)
    if not m:
        return None
    raw = m.group(0).replace('\xa0', '').replace(' ', '').replace(',', '.').strip().rstrip('.')
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning('btorg.bad_price value=%s', value)
        return None


def parse_listing(selector: Selector, source: str) -> list[dict[str, object]]:
    """Parse ``table.data`` trade rows into trade dicts."""
    trades: list[dict[str, object]] = []
    for row in selector.xpath('//table[@class="data"]//tr[@onclick]'):
        m = _ID_RE.search(row.xpath('./@onclick').get() or '')
        purchase_id = m.group(1) if m else None
        tds = row.xpath('./td')
        if not purchase_id or len(tds) < 5:
            continue
        number = clean(tds[0].xpath('string(.)').get())
        if not number:
            continue
        dm = _DIGITS_RE.search(number)
        trade_id = dm.group(0) if dm else None
        if not trade_id:
            continue
        parts = number.split('-')
        trade_type = clean(parts[1]) if len(parts) == 2 else None
        trades.append(
            {
                'trade_id': trade_id,
                'trade_number': number,
                'trade_type': trade_type,
                'purchase_id': purchase_id,
                'debtor': clean(tds[1].xpath('string(.)').get()),
                'organizer': clean(tds[2].xpath('.//div[contains(@style, "bold")]//text()').get()),
                'status': clean(tds[3].xpath('string(.)').get()),
                'list_date': clean(tds[4].xpath('string(.)').get()),
                'lots_url': f'{LOTS_PATH}?perspective=inline&id={purchase_id}',
                '_source': source,
            }
        )
    return trades


def find_next_page(selector: Selector, current_page: int) -> int | None:
    """Smallest pager page number greater than ``current_page``, or None."""
    pages: list[int] = []
    for href in selector.xpath('//a[contains(@href, "list.html?page=")]/@href').getall():
        m = _PAGE_RE.search(href)
        if m:
            pages.append(int(m.group(1)))
    nxt = [p for p in pages if p > current_page]
    return min(nxt) if nxt else None
