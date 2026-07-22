"""Parse the trade listing on rus-on sites (…/trade_list.php or …/tradelist.php).

The rus-on group is heterogeneous: the listing table is ``table.data`` or
``table.node_view``; each row links to a trade either via an ``<a href>`` or a
row ``onclick``; some sites list trades, others list lots (several rows per
trade). What is uniform is the trade detail URL ``trade_view.php?trade_nid=N``,
so the listing is reduced to a de-duplicated set of those trade references — all
trade/lot fields are then read from the (uniform) detail page.
"""

from __future__ import annotations

import logging
import re

from parsel import Selector

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r'\s+')
_NID_RE = re.compile(r'trade_view\.php\?trade_nid=(\d+)')
_REF_RE = re.compile(r"(/?[^'\"\s]*trade_view\.php\?trade_nid=\d+)")
_CODE_RE = re.compile(r'(\d+)-[А-Я]{2,}')
_PAGENUM_RE = re.compile(r'pagenum_send\((\d+)\)')
_PRICE_HEAD_RE = re.compile(r'[\d\s\xa0.,]+')


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
        logger.warning('ruson.bad_max_pages value=%s', raw)
        return None
    return value if value > 0 else None


def parse_price(value: str | None) -> float | None:
    """Parse "1 315 000.00" → 1315000.0 (space thousands, dot/comma decimal)."""
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
        logger.warning('ruson.bad_price value=%s', value)
        return None


def parse_listing(selector: Selector, source: str) -> list[dict[str, object]]:
    """Reduce a listing page to DISTINCT trades (by trade_nid).

    Trade reference comes from a row ``<a href=…trade_view.php…>`` or the row's
    ``onclick``. ``trade_id`` is the visible code's digits when present, else the
    internal nid; ``detail_url`` may be absolute or root-relative (the caller
    resolves it against the page URL).
    """
    trades: list[dict[str, object]] = []
    seen: set[str] = set()
    rows = selector.xpath(
        '//tr[.//a[contains(@href, "trade_view.php")]] | //tr[contains(@onclick, "trade_view.php")]'
    )
    for row in rows:
        href = row.xpath('.//a[contains(@href, "trade_view.php")]/@href').get()
        ref = href
        if not ref:
            m = _REF_RE.search(row.xpath('./@onclick').get() or '')
            ref = m.group(1) if m else None
        if not ref:
            continue
        nid = _NID_RE.search(ref)
        if not nid:
            continue
        trade_nid = nid.group(1)
        if trade_nid in seen:
            continue
        seen.add(trade_nid)
        code = _CODE_RE.search(clean(row.xpath('string(.)').get()) or '')
        trades.append(
            {
                'trade_nid': trade_nid,
                'trade_id': code.group(1) if code else trade_nid,
                'trade_number': code.group(0) if code else None,
                'trade_type': clean(code.group(0).split('-')[1]) if code else None,
                'detail_url': ref,
                '_source': source,
            }
        )
    return trades


def find_next_page(selector: Selector, current_page: int) -> int | None:
    """Next page number from the ``pagenum_send(N)`` pager, or None."""
    pages: list[int] = []
    for onclick in selector.xpath('//ul[contains(@class, "pagination")]//a/@onclick').getall():
        pages.extend(int(n) for n in _PAGENUM_RE.findall(onclick))
    nxt = [p for p in pages if p > current_page]
    return min(nxt) if nxt else None
