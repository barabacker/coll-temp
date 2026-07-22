# Kendo-ETP Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `Kendo-ETP` engine (`collector/sources/kendo/`) — a parser family for 5 bankruptcy-auction sites on the Kendo-UI platform, emitting per-lot items compatible with the existing `LotSink`/`lot_fingerprint`.

**Architecture:** Mirrors `sources/fogsoft/` (base + platforms + parsing/). Server-rendered HTML, `GET /lots?page=N` pagination, detail `GET /{type}/{id}`. The listing lists *trades*; the parser always dives into each trade's detail and expands it into one item per lot. No ViewState, no anti-bot, no JS. Selectors and expected values are validated against committed fixtures.

**Tech Stack:** Python 3, `parsel` (lxml), `curl_cffi`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-07-22-kendo-etp-engine-design.md`

**Fixtures (already committed, from trade-alliance.ru):**
- `tests/fixtures/kendo/listing_page1.html` — 15 trade cards, pager pages 2..N.
- `tests/fixtures/kendo/detail_oaof.html` — trade 10775, 2 lots, 2 documents.

All selectors below were verified against these fixtures with parsel.

---

## File Structure

```
collector/sources/kendo/
  __init__.py            package marker
  base.py                TenderKendo(BaseParser): parse listing, dive, expand to per-lot items
  platforms.py           5 concrete @register_parser classes
  parsing/
    __init__.py          package marker
    listing.py           parse_listing, find_next_page, read_max_pages, clean
    detail.py            parse_price, parse_lots, parse_main_info, parse_documents
tests/
  unit/kendo/__init__.py
  unit/kendo/test_listing.py
  unit/kendo/test_detail.py
  unit/kendo/test_registration.py
  integration/test_kendo_crawl.py
```

Item keys mirror fogsoft (`parse_table`): `lot_id, trade_id, lot_num, trade_title, lot_url, description, price, price_raw, status, bidding_date, event_date, trade_type, organizer, _source` plus `detail`, `attachments`.

---

## Task 1: parsing/listing.py

**Files:**
- Create: `collector/sources/kendo/__init__.py`, `collector/sources/kendo/parsing/__init__.py`, `collector/sources/kendo/parsing/listing.py`
- Create: `tests/unit/kendo/__init__.py`, `tests/unit/kendo/test_listing.py`

- [ ] **Step 1: Create package markers**

```bash
mkdir -p collector/sources/kendo/parsing tests/unit/kendo
printf '"""collector.sources.kendo — Kendo-ETP engine family."""\n' > collector/sources/kendo/__init__.py
printf '"""Page extractors for Kendo-ETP."""\n' > collector/sources/kendo/parsing/__init__.py
printf '"""Test package marker."""\n' > tests/unit/kendo/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/kendo/test_listing.py`:

```python
"""parse_listing / find_next_page against the committed listing fixture."""

from __future__ import annotations

from pathlib import Path

from parsel import Selector

from collector.sources.kendo.parsing.listing import (
    find_next_page,
    parse_listing,
    read_max_pages,
)

FIXTURE = Path(__file__).parents[2] / 'fixtures' / 'kendo' / 'listing_page1.html'


def _sel() -> Selector:
    return Selector(text=FIXTURE.read_text(encoding='utf-8'))


def test_parse_listing_card_count():
    trades = parse_listing(_sel(), 'trade_alliance')
    assert len(trades) == 15


def test_parse_listing_first_card_fields():
    first = parse_listing(_sel(), 'trade_alliance')[0]
    assert first['trade_id'] == '10775'
    assert first['trade_number'] == '10775–ОАОФ'
    assert first['detail_url'] == '/oaof/10775'
    assert first['status'] == 'Идет прием заявок'
    assert first['bidding_date'] == '21.08.2026 17:00:00'
    assert first['event_date'] == '22.08.2026 12:00:00'
    assert first['trade_title'].startswith('Открытый аукцион')
    assert first['_source'] == 'trade_alliance'


def test_find_next_page():
    assert find_next_page(_sel(), 1) == 2
    assert find_next_page(_sel(), 999) is None


def test_read_max_pages():
    assert read_max_pages({}) is None
    assert read_max_pages({'max_pages': '3'}) == 3
    assert read_max_pages({'max_pages': 'x'}) is None
    assert read_max_pages({'max_pages': '0'}) is None
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/unit/kendo/test_listing.py -q`
Expected: FAIL — `ModuleNotFoundError: collector.sources.kendo.parsing.listing`.

- [ ] **Step 4: Implement `collector/sources/kendo/parsing/listing.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/kendo/test_listing.py -q`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add collector/sources/kendo tests/unit/kendo
git commit -m "feat(kendo): listing parser (parse_listing/find_next_page)"
```

---

## Task 2: parsing/detail.py

**Files:**
- Create: `collector/sources/kendo/parsing/detail.py`
- Create: `tests/unit/kendo/test_detail.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/kendo/test_detail.py`:

```python
"""parse_lots / parse_main_info / parse_documents against the detail fixture."""

from __future__ import annotations

from pathlib import Path

from parsel import Selector

from collector.sources.kendo.parsing.detail import (
    parse_documents,
    parse_lots,
    parse_main_info,
    parse_price,
)

FIXTURE = Path(__file__).parents[2] / 'fixtures' / 'kendo' / 'detail_oaof.html'

TRADE = {
    'trade_id': '10775',
    'trade_title': 'Открытый аукцион …, должник Баранов Виталий Витальевич',
    'trade_type': 'ОАОФ',
    'bidding_date': '21.08.2026 17:00:00',
    'event_date': '22.08.2026 12:00:00',
    '_source': 'trade_alliance',
}


def _sel() -> Selector:
    return Selector(text=FIXTURE.read_text(encoding='utf-8'))


def test_parse_price():
    assert parse_price('6 721 200.00') == 6721200.0
    assert parse_price('9 000.00') == 9000.0
    assert parse_price(None) is None
    assert parse_price('—') is None


def test_parse_lots_count_and_first_lot():
    lots = parse_lots(_sel(), TRADE)
    assert len(lots) == 2
    first = lots[0]
    assert first['lot_id'] == '10775_5'
    assert first['lot_num'] == '5'
    assert first['price'] == 6721200.0
    assert first['status'] == 'Идет прием заявок'
    assert first['lot_url'].endswith('/oaof/10775/lots/3090')
    assert 'М7-КРЕДИТ' in first['description']
    # trade-level fields carried onto the lot for fingerprinting:
    assert first['trade_title'] == TRADE['trade_title']
    assert first['bidding_date'] == '21.08.2026 17:00:00'
    assert first['_source'] == 'trade_alliance'


def test_parse_lots_second_lot():
    lots = parse_lots(_sel(), TRADE)
    assert lots[1]['lot_id'] == '10775_6'
    assert lots[1]['price'] == 9000.0


def test_parse_main_info():
    info = parse_main_info(_sel())
    assert info.get('Статус торгов') == 'идет прием заявок'
    assert len(info) >= 10


def test_parse_documents():
    docs = parse_documents(_sel())
    assert len(docs) == 2
    assert docs[0]['url'].startswith('http')
    assert docs[0]['name']
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/unit/kendo/test_detail.py -q`
Expected: FAIL — `ModuleNotFoundError: collector.sources.kendo.parsing.detail`.

- [ ] **Step 3: Implement `collector/sources/kendo/parsing/detail.py`**

```python
"""Parse a Kendo-ETP trade detail page (/{type}/{id}).

One server-rendered page holds all tabs. Lots live in ``div#lots`` as repeated
``a.block-lot`` blocks (each: lot link, "Номер лота", "Статус лота", price in
``span.fs36``). Trade-level key/value fields live in ``div#main-info`` as
``div.table_row`` label/value pairs; documents in ``div#documents``.
"""

from __future__ import annotations

import logging
import re

from parsel import Selector

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r'\s+')


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _WS_RE.sub(' ', value).strip()
    return cleaned or None


def parse_price(value: str | None) -> float | None:
    """Parse "6 721 200.00" → 6721200.0. Space = thousands, dot/comma = decimal."""
    if value is None:
        return None
    raw = value.replace('\xa0', '').replace(' ', '').replace(',', '.')
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning('kendo.detail.bad_price value=%s', value)
        return None


def parse_lots(selector: Selector, trade: dict[str, object]) -> list[dict[str, object]]:
    """Expand ``div#lots > a.block-lot`` into per-lot item dicts.

    Trade-level fields from ``trade`` (title, dates, source) are copied onto each
    lot so ``lot_fingerprint`` (status/price/dates/trade_title) works per lot.
    """
    trade_id = trade.get('trade_id')
    items: list[dict[str, object]] = []
    for block in selector.xpath('//div[@id="lots"]//a[contains(@class, "block-lot")]'):
        link = block.xpath('.//a[contains(@class, "blue-text")][@href][1]')
        lot_num = _clean(block.xpath('.//span[contains(@class, "black-text")]/text()').get())
        price_raw = _clean(block.xpath('string(.//span[contains(@class, "fs36")])').get())
        items.append(
            {
                'lot_id': f'{trade_id}_{lot_num}' if trade_id and lot_num else None,
                'trade_id': trade_id,
                'lot_num': lot_num,
                'lot_url': link.xpath('./@href').get(),
                'description': _clean(link.xpath('string(.)').get()),
                'price': parse_price(price_raw),
                'price_raw': price_raw,
                'status': _clean(
                    block.xpath('.//span[contains(@class, "lot-status")]/following-sibling::text()').get()
                ),
                'trade_title': trade.get('trade_title'),
                'trade_type': trade.get('trade_type'),
                'bidding_date': trade.get('bidding_date'),
                'event_date': trade.get('event_date'),
                'organizer': None,
                '_source': trade.get('_source'),
            }
        )
    return items


def parse_main_info(selector: Selector) -> dict[str, str]:
    """Flat {label: value} of the ``#main-info`` table_row pairs.

    Labels repeated across sections collapse (last wins) — acceptable for this
    reference blob, which is not fingerprinted.
    """
    info: dict[str, str] = {}
    for row in selector.xpath('//div[@id="main-info"]//div[contains(@class, "table_row")]'):
        label = _clean(row.xpath('string(./div[contains(@class, "grey-text")][1])').get())
        value = _clean(row.xpath('string(./div[contains(@class, "l9")][1])').get())
        if label and value:
            info[label.rstrip(':').strip()] = value
    return info


def parse_documents(selector: Selector) -> list[dict[str, object]]:
    """Extract downloadable documents (name + http url) from ``#documents``."""
    docs: list[dict[str, object]] = []
    for row in selector.xpath('//div[@id="documents"]//div[contains(@class, "file-row")]'):
        link = row.xpath('.//a[starts-with(@href, "http")][1]')
        url = link.xpath('./@href').get()
        if url:
            docs.append({'name': _clean(link.xpath('string(.)').get()), 'url': url})
    return docs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/kendo/test_detail.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add collector/sources/kendo/parsing/detail.py tests/unit/kendo/test_detail.py
git commit -m "feat(kendo): detail parser (lots/main-info/documents)"
```

---

## Task 3: base.py + platforms.py + registration

**Files:**
- Create: `collector/sources/kendo/base.py`, `collector/sources/kendo/platforms.py`
- Modify: `collector/__init__.py` (side-effect import), `tests/unit/test_public_api.py` (EXPECTED_KEYS)
- Create: `tests/unit/kendo/test_registration.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/kendo/test_registration.py`:

```python
"""TenderKendo derives URLs; the 5 platforms register."""

from __future__ import annotations

from collector.core.registry import get_parser, registry
from collector.sources.kendo.base import TenderKendo

KENDO_KEYS = {'trade_alliance', 'seltim', 'electro_torgi', 'torgi82', 'vetp'}


def test_all_kendo_platforms_registered():
    assert KENDO_KEYS <= set(registry())


def test_base_url_derived():
    cls = get_parser('trade_alliance')
    assert issubclass(cls, TenderKendo)
    assert cls.BASE_URL == 'https://trade-alliance.ru/lots'
    assert cls.start_urls == ['https://trade-alliance.ru/lots']


def test_no_response_hooks():
    cls = get_parser('trade_alliance')
    assert cls.RESPONSE_HOOKS == ()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/unit/kendo/test_registration.py -q`
Expected: FAIL — `ModuleNotFoundError: collector.sources.kendo.base`.

- [ ] **Step 3: Implement `collector/sources/kendo/base.py`**

```python
"""TenderKendo — base parser for Kendo-ETP bankruptcy-auction sites.

A subclass sets ``name`` (registry key) and ``DOMAIN``. The listing lists
*trades*; ``parse`` enqueues a detail dive per trade, and ``parse_detail``
expands each trade into one item per lot (matching the lot-centric LotSink).
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
        lots = parse_lots(sel, trade)
        await self.log(
            f'{response.request.method} | {response.status} '
            f'| detail trade={trade.get("trade_id")} | lots={len(lots)}'
        )
        for item in lots:
            item['organizer'] = organizer
            item['detail'] = main
            item['attachments'] = docs
            yield item
```

- [ ] **Step 4: Implement `collector/sources/kendo/platforms.py`**

```python
"""Concrete Kendo-ETP platforms."""

from __future__ import annotations

from collector.core.registry import register_parser
from collector.sources.kendo.base import TenderKendo


@register_parser('trade_alliance')
class TradeAllianceParser(TenderKendo):
    """Альянс Трэйд — trade-alliance.ru."""

    name = 'trade_alliance'
    DOMAIN = 'https://trade-alliance.ru'


@register_parser('seltim')
class SeltimParser(TenderKendo):
    """Селтим — bankrupt.seltim.ru."""

    name = 'seltim'
    DOMAIN = 'https://bankrupt.seltim.ru'


@register_parser('electro_torgi')
class ElectroTorgiParser(TenderKendo):
    """Электро-Торги — bankrotstvo.electro-torgi.ru."""

    name = 'electro_torgi'
    DOMAIN = 'https://bankrotstvo.electro-torgi.ru'


@register_parser('torgi82')
class Torgi82Parser(TenderKendo):
    """Торги82 — lot.torgi82.ru."""

    name = 'torgi82'
    DOMAIN = 'https://lot.torgi82.ru'


@register_parser('vetp')
class VetpParser(TenderKendo):
    """ВЭТП — банкрот.вэтп.рф (IDN)."""

    name = 'vetp'
    DOMAIN = 'https://банкрот.вэтп.рф'
```

- [ ] **Step 5: Register the platforms in the facade**

In `collector/__init__.py`, directly below the existing fogsoft side-effect import line

```python
from collector.sources.fogsoft import platforms as _fogsoft_platforms  # noqa: E402,F401
```

add:

```python
from collector.sources.kendo import platforms as _kendo_platforms  # noqa: E402,F401
```

- [ ] **Step 6: Update the registry safety-net**

In `tests/unit/test_public_api.py`, replace the `EXPECTED_KEYS` set so it also contains the 5 kendo keys (15 fogsoft keys + 5 = 20). New value:

```python
EXPECTED_KEYS = {
    'centerr', 'alfalot', 'etpu_bankrupt', 'bep', 'arbbitlot', 'arbitat',
    'utp_lot', 'tender_one', 'etpugra', 'tendergarant', 'yuzhnyy_etp',
    'meta_invest', 'gloria_service', 'zakazrf', 'etb',
    'trade_alliance', 'seltim', 'electro_torgi', 'torgi82', 'vetp',
}
```

(If `EXPECTED_KEYS` already contains `utender` from a prior change, keep it and just add the 5 kendo keys — the assertion compares to the live registry either way.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/kendo/test_registration.py tests/unit/test_public_api.py -q`
Expected: all passed. If `test_registry_is_fully_populated` fails on count, reconcile `EXPECTED_KEYS` with the live `registry()` (only the intended kendo keys should be new).

- [ ] **Step 8: Commit**

```bash
git add collector/sources/kendo/base.py collector/sources/kendo/platforms.py collector/__init__.py tests/unit/kendo/test_registration.py tests/unit/test_public_api.py
git commit -m "feat(kendo): TenderKendo base + 5 platforms + registration"
```

---

## Task 4: integration crawl test

**Files:**
- Create: `tests/integration/test_kendo_crawl.py`

- [ ] **Step 1: Write the test**

Create `tests/integration/test_kendo_crawl.py`:

```python
"""End-to-end kendo crawl over fixtures via a fake HTTP client (no network)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from collector.core.spider import ParserContext
from collector.core.storage.contracts import ChangeStatus
from collector.sources.kendo.platforms import TradeAllianceParser

FIX = Path(__file__).parents[1] / 'fixtures' / 'kendo'
LISTING = (FIX / 'listing_page1.html').read_text(encoding='utf-8')
DETAIL = (FIX / 'detail_oaof.html').read_text(encoding='utf-8')

FINGERPRINT_KEYS = {'status', 'price', 'bidding_date', 'event_date', 'trade_title'}


class _Raw:
    def __init__(self, text: str) -> None:
        self.status_code = 200
        self.text = text
        self.content = text.encode('utf-8')


class _FakeHttp:
    """Serves the listing fixture for /lots URLs, the detail fixture otherwise."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> _Raw:
        self.calls.append(url)
        if url.endswith('/lots') or 'page=' in url:
            return _Raw(LISTING)
        return _Raw(DETAIL)


class _Sink:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    async def get_fingerprints(self, source: str, lot_ids: Any) -> dict[str, str]:
        return {}

    async def save(self, item: dict[str, Any]) -> ChangeStatus:
        self.items.append(item)
        return ChangeStatus.NEW


def test_kendo_crawl_expands_trades_into_lots():
    sink = _Sink()
    http = _FakeHttp()
    ctx = ParserContext(http=http, params={'max_pages': '1'}, lot_sink=sink)
    parser = TradeAllianceParser(ctx)

    total = asyncio.run(parser.crawl())

    # 15 trades on page 1, each detail fixture has 2 lots -> 30 lot items.
    assert total == 30
    assert len(sink.items) == 30
    # dived into details, and max_pages=1 stopped pagination (no page=2 fetched).
    assert any('/oaof/' in c for c in http.calls)
    assert not any('page=2' in c for c in http.calls)
    # items are fogsoft-shaped: fingerprint keys present and populated.
    first = sink.items[0]
    assert FINGERPRINT_KEYS <= first.keys()
    assert first['lot_id'] == '10775_5'
    assert first['price'] == 6721200.0
    assert first['status'] == 'Идет прием заявок'
    assert first['detail'] and first['attachments']
```

- [ ] **Step 2: Run it to verify it passes**

Run: `uv run pytest tests/integration/test_kendo_crawl.py -q`
Expected: 1 passed. (If it hangs, the pagination guard is wrong — verify `max_pages=1` blocks the `page < max_pages` branch so no `page=2` request is enqueued.)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_kendo_crawl.py
git commit -m "test(kendo): end-to-end crawl over fixtures via fake http"
```

---

## Task 5: full verification

**Files:** none (verification only)

- [ ] **Step 1: Full suite, green, no network**

Run: `uv run pytest -q`
Expected: all passed (public_api, base_hooks, tls, factory, layering, kendo listing/detail/registration, kendo crawl). No network calls.

- [ ] **Step 2: Registry lists 20 platforms including the 5 kendo keys**

Run: `uv run python main.py --list`
Expected: prints 20 keys; `trade_alliance`, `seltim`, `electro_torgi`, `torgi82`, `vetp` present. No crawl, no network.

- [ ] **Step 3: Layering guard still holds**

Run: `uv run pytest tests/unit/test_layering.py -q`
Expected: passed — `sources/kendo` imports only `core` at runtime (no upward import).

- [ ] **Step 4 (optional, network): live smoke of one site**

Run: `uv run python main.py trade_alliance 1`
Expected: collects lots into `lots.json`; sampled items show non-empty `price`/`status`. This hits the live site (VPN required) — skip if offline. Keep page count at 1.

- [ ] **Step 5: Confirm clean tree**

No code changes in this task. If Step 4 created `lots.json`, do not commit it (throwaway output). Confirm `git status` shows no unintended tracked changes.

---

## Self-Review Notes

- **Spec coverage:** §3.1 layout → Tasks 1–3; §3.2 base flow → Task 3; §3.3 listing → Task 1; §3.4 detail + item mapping → Task 2; §3.6 registration → Task 3; §4 invariants (EXPECTED_KEYS 20, layering) → Tasks 3/5; §5 tests → Tasks 1–4. §7 fixtures — captured and committed (`b05c8fa`) before this plan.
- **Selectors/values validated:** every selector and expected value in Tasks 1–2 was run against the committed fixtures with parsel (15 cards; lot ids 10775_5/10775_6; prices 6721200.0/9000.0; statuses; main_info["Статус торгов"]="идет прием заявок"; 2 docs).
- **Type consistency:** `parse_listing(sel, source)`, `find_next_page(sel, page)`, `read_max_pages(params)`, `parse_lots(sel, trade)`, `parse_price(str)`, `parse_main_info(sel)`, `parse_documents(sel)` used identically across tasks. Item keys match fogsoft's `parse_table` output.
- **Deferred (per spec §7):** verify the other 4 sites' template + capture their fixtures before relying on them in production; date-field semantics; trade-level skip optimization.
