# Lot Pydantic Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize the ad-hoc dict each parser emits into a typed Pydantic `Lot` model that flows through the `LotSink` boundary, normalizing dates to `datetime` and deriving `is_active`.

**Architecture:** A new `collector.core.lot.Lot` (pydantic v2) is validated at each engine's emit point (`DiveParser.parse_lots_page` and the fogsoft base). A `@model_validator(mode='before')` renames `_source`→`source` / `detail`→`extra`, parses the two date strings into `datetime` (keeping the raw strings), and derives `is_active`. `LotSink.save` now takes a `Lot`; the JSON-writing sinks dump `model_dump(mode='json')`.

**Tech Stack:** Python 3.14, pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-lot-pydantic-model-design.md`

**Key facts (verified):**
- The 17 emitted keys (union across all 31 sites): `_source, lot_id, trade_id, lot_num, trade_title, trade_type, organizer, description, lot_url, price, price_raw, status, bidding_date, event_date, detail, attachments, price_schedule`. btorg/ruson omit `attachments`+`price_schedule`; kendo omits `price_schedule`.
- `BaseParser._handle` routes any non-`Request` yield to `process_item`, which only passes the item to `sink.save` (never indexes it) — so yielding a `Lot` works unchanged.
- fogsoft emits items at two `yield item` lines (`base.py:99` in `parse`, `base.py:135` in `parse_detail`); the dive engines emit in `DiveParser.parse_lots_page`.

---

## File Structure

```
collector/core/parsing.py      + parse_datetime()
collector/core/lot.py          NEW — the Lot model
collector/core/storage/sink.py LotSink.save(item: Lot)
collector/core/spider/parser.py  type hints -> Lot (TYPE_CHECKING)
collector/core/spider/dive.py    yield Lot.model_validate(item)
collector/sources/fogsoft/base.py  wrap both yields
main.py, worker.py             dump lot.model_dump(mode='json')
tests/unit/test_lot.py         NEW
tests/integration/test_{kendo,btorg,ruson}_crawl.py  _Sink takes Lot; attribute asserts
pyproject.toml                 + pydantic>=2
```

---

## Task 1: parse_datetime helper

**Files:**
- Modify: `collector/core/parsing.py`
- Test: `tests/unit/test_parse_datetime.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_parse_datetime.py`:

```python
"""parse_datetime turns the listing/detail date strings into datetimes."""

from __future__ import annotations

from datetime import datetime

from collector.core.parsing import parse_datetime


def test_all_observed_formats():
    assert parse_datetime('18.08.2026 13:00:00') == datetime(2026, 8, 18, 13, 0, 0)
    assert parse_datetime('29.07.2026 12:00') == datetime(2026, 7, 29, 12, 0)
    assert parse_datetime('28.08.2026 00:00:00') == datetime(2026, 8, 28, 0, 0)
    # centerr appends a "days left" suffix that must be ignored
    assert parse_datetime('26.08.2026 12:30 (33 дн.)') == datetime(2026, 8, 26, 12, 30)
    # date only
    assert parse_datetime('23.07.2026') == datetime(2026, 7, 23, 0, 0)


def test_unparseable_and_empty():
    assert parse_datetime(None) is None
    assert parse_datetime('') is None
    assert parse_datetime('нет даты') is None
    assert parse_datetime('31.02.2026 10:00') is None  # invalid calendar date
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/unit/test_parse_datetime.py -q`
Expected: FAIL — `ImportError: cannot import name 'parse_datetime'`.

- [ ] **Step 3: Add `parse_datetime` to `collector/core/parsing.py`**

Add the import at the top of the file (with the existing imports):

```python
from datetime import datetime
```

Add this regex next to the other module-level regexes:

```python
# DD.MM.YYYY with an optional HH:MM[:SS]; trailing text (e.g. "(33 дн.)") ignored.
_DATETIME_RE = re.compile(r'(\d{2})\.(\d{2})\.(\d{4})(?:\D+(\d{2}):(\d{2})(?::(\d{2}))?)?')
```

Add the function:

```python
def parse_datetime(value: str | None) -> datetime | None:
    """Parse a "DD.MM.YYYY[ HH:MM[:SS]]" string to a datetime, else None."""
    if not value:
        return None
    m = _DATETIME_RE.search(value)
    if not m:
        return None
    day, month, year, hour, minute, second = m.groups()
    try:
        return datetime(
            int(year), int(month), int(day),
            int(hour or 0), int(minute or 0), int(second or 0),
        )
    except ValueError:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_parse_datetime.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add collector/core/parsing.py tests/unit/test_parse_datetime.py
git commit -m "feat(core): parse_datetime for the RU date strings"
```

---

## Task 2: the Lot model

**Files:**
- Modify: `pyproject.toml`
- Create: `collector/core/lot.py`
- Test: `tests/unit/test_lot.py`

- [ ] **Step 1: Add pydantic to `pyproject.toml`**

In the `[project]` `dependencies` list, add `"pydantic>=2"`:

```toml
dependencies = [
    "certifi>=2026.7.22",
    "curl-cffi>=0.15.0",
    "parsel>=1.11.0",
    "tenacity>=9.1.4",
    "pydantic>=2",
]
```

Then sync: `uv sync` (installs pydantic).

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_lot.py`:

```python
"""The Lot model standardizes and normalizes an emitted parser item."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from collector.core.lot import Lot

# A maximal (fogsoft-shaped) emitted item — every one of the 17 keys.
FULL_ITEM = {
    'lot_id': '0099382_1',
    'trade_id': '0099382',
    'lot_num': '1',
    'trade_title': 'Багаутдинова Рузиля Вазировна',
    'trade_type': 'Открытый аукцион',
    'organizer': 'Климова Светлана Евгеньевна',
    'description': 'Право собственности на объект недвижимости',
    'lot_url': '/public/auctions/lots/view/1167819/',
    'price': 5500800.0,
    'price_raw': '5 500 800,00',
    'status': 'Прием заявок',
    'bidding_date': '26.08.2026 12:30 (33 дн.)',
    'event_date': '27.08.2026 11:30',
    'detail': {'Информация о лоте №1': {'Наименование': 'X'}},
    'attachments': [{'name': 'doc.pdf', 'url': 'http://x/doc.pdf'}],
    'price_schedule': [{'период': '1', 'цена': '100'}],
    '_source': 'centerr',
}

# A minimal (btorg/ruson-shaped) item — no attachments / price_schedule.
MINIMAL_ITEM = {
    'lot_id': '68289_1',
    'trade_id': '68289',
    'lot_num': '1',
    'trade_title': '68289-ОАОФ',
    'trade_type': 'ОАОФ',
    'organizer': None,
    'description': 'Легковой автомобиль',
    'lot_url': 'https://nistp.ru/bankrot/trade_view.php?trade_nid=1',
    'price': 140000.0,
    'price_raw': '140 000.00',
    'status': 'Торги завершены',
    'bidding_date': '28.08.2026 00:00:00',
    'event_date': '24.07.2026 00:00:00',
    'detail': {'Номер лота': '1'},
    '_source': 'nistp',
}


def test_full_item_normalized():
    lot = Lot.model_validate(FULL_ITEM)
    assert lot.source == 'centerr'
    assert lot.lot_id == '0099382_1'
    assert lot.price == 5500800.0
    # dates normalized, raw kept
    assert lot.bidding_deadline == datetime(2026, 8, 26, 12, 30)
    assert lot.bidding_date_raw == '26.08.2026 12:30 (33 дн.)'
    assert lot.result_date == datetime(2026, 8, 27, 11, 30)
    # status -> is_active
    assert lot.is_active is True
    # raw blob folded into extra
    assert lot.extra == {'Информация о лоте №1': {'Наименование': 'X'}}
    assert lot.attachments and lot.price_schedule


def test_minimal_item_defaults_and_finished_status():
    lot = Lot.model_validate(MINIMAL_ITEM)
    assert lot.attachments == []
    assert lot.price_schedule == []
    assert lot.is_active is False  # "Торги завершены"
    assert lot.bidding_deadline == datetime(2026, 8, 28, 0, 0)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        Lot.model_validate({**MINIMAL_ITEM, 'surprise': 'boom'})


def test_model_dump_is_json_ready():
    dumped = Lot.model_validate(FULL_ITEM).model_dump(mode='json')
    assert dumped['source'] == 'centerr'
    assert dumped['bidding_deadline'] == '2026-08-26T12:30:00'
    assert 'extra' in dumped and '_source' not in dumped
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/unit/test_lot.py -q`
Expected: FAIL — `ModuleNotFoundError: collector.core.lot`.

- [ ] **Step 4: Implement `collector/core/lot.py`**

```python
"""Lot — the standardized, typed item every parser emits.

Parsers build ad-hoc dicts; this model validates and normalizes one at the
engine boundary (see DiveParser / fogsoft base). It renames ``_source``/
``detail`` to ``source``/``extra``, parses the two date strings into
``datetime`` (keeping the raw strings), and derives ``is_active`` from status.
Unknown fields are rejected so engine drift surfaces immediately.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from collector.core.parsing import is_active_status, parse_datetime


class Lot(BaseModel):
    """A single lot within a trade, normalized across all engines."""

    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    source: str = Field(alias='_source')
    lot_id: str
    trade_id: str
    lot_num: str | None = None

    trade_title: str | None = None
    trade_type: str | None = None
    organizer: str | None = None

    description: str | None = None
    lot_url: str | None = None
    price: float | None = None
    price_raw: str | None = None

    status: str | None = None
    is_active: bool = True
    bidding_deadline: datetime | None = None
    result_date: datetime | None = None
    bidding_date_raw: str | None = None
    event_date_raw: str | None = None

    attachments: list[dict[str, Any]] = Field(default_factory=list)
    price_schedule: list[dict[str, Any]] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict, alias='detail')

    @model_validator(mode='before')
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if 'bidding_date' in d:
            d['bidding_date_raw'] = d.get('bidding_date')
            d['bidding_deadline'] = parse_datetime(d.pop('bidding_date'))
        if 'event_date' in d:
            d['event_date_raw'] = d.get('event_date')
            d['result_date'] = parse_datetime(d.pop('event_date'))
        d.setdefault('is_active', is_active_status(d.get('status')))
        return d
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_lot.py -q`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock collector/core/lot.py tests/unit/test_lot.py
git commit -m "feat(core): Lot pydantic model with date/status normalization"
```

---

## Task 3: flow the model through the sink boundary

**Files:**
- Modify: `collector/core/storage/sink.py`, `collector/core/spider/parser.py`, `collector/core/spider/dive.py`, `collector/sources/fogsoft/base.py`
- Modify: `tests/integration/test_kendo_crawl.py`, `tests/integration/test_btorg_crawl.py`, `tests/integration/test_ruson_crawl.py`

- [ ] **Step 1: Change the `LotSink` contract**

In `collector/core/storage/sink.py`, replace `save`'s signature (and drop the now-unused `Any` if present):

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from collector.core.lot import Lot
from collector.core.storage.contracts import ChangeStatus


class LotSink(Protocol):
    """What a parser needs to persist lots and detect changes."""

    async def save(self, item: Lot) -> ChangeStatus:
        """Upsert a lot, returning NEW / CHANGED / UNCHANGED."""
        ...

    async def get_fingerprints(self, source: str, lot_ids: Sequence[str]) -> dict[str, str]:
        """Batch-read current fingerprints for the given lot ids."""
        ...
```

- [ ] **Step 2: Update `process_item` / `parse` type hints in `collector/core/spider/parser.py`**

Under the existing `if TYPE_CHECKING:` block add the import:

```python
if TYPE_CHECKING:
    from collector.core.lot import Lot
    from collector.http.middleware import ResponseHook
```

Change `process_item`'s signature:

```python
    async def process_item(self, item: Lot) -> None:
```

(The `parse`/`request` `dict[str, Any]` hints may stay — they describe the raw items parsers build internally; only the emitted, post-validation object is a `Lot`.)

- [ ] **Step 3: Wrap the dive-engine emit in `collector/core/spider/dive.py`**

Add the import:

```python
from collector.core.lot import Lot
```

In `parse_lots_page`, change the emit loop:

```python
        for item in lots:
            # An item without a lot_id cannot be upserted downstream — drop it.
            if item.get('lot_id'):
                yield Lot.model_validate(item)
```

- [ ] **Step 4: Wrap the fogsoft emits in `collector/sources/fogsoft/base.py`**

Add the import (with the other core imports):

```python
from collector.core.lot import Lot
```

Change the emit in `parse` (the `else: yield item` branch) to:

```python
            else:
                yield Lot.model_validate(item)
```

Change the emit in `parse_detail` (`yield item`) to:

```python
        yield Lot.model_validate(item)
```

- [ ] **Step 5: Update the three integration test sinks + assertions**

In **each** of `tests/integration/test_kendo_crawl.py`, `test_btorg_crawl.py`, `test_ruson_crawl.py`:

Add the import near the top:

```python
from collector.core.lot import Lot
```

Change `_Sink.save`'s signature and the `items` type:

```python
class _Sink:
    def __init__(self) -> None:
        self.items: list[Lot] = []

    async def get_fingerprints(self, source: str, lot_ids: Any) -> dict[str, str]:
        return {}

    async def save(self, item: Lot) -> ChangeStatus:
        self.items.append(item)
        return ChangeStatus.NEW
```

Then change the item assertions from dict access to attribute access. In **test_kendo_crawl.py** replace:

```python
    first = sink.items[0]
    assert FINGERPRINT_KEYS <= first.keys()
    assert first['lot_id'] == '10775_5'
    assert first['price'] == 6721200.0
    assert first['status'] == 'Идет прием заявок'
    assert first['detail'] and first['attachments']
```

with:

```python
    first = sink.items[0]
    assert first.lot_id == '10775_5'
    assert first.price == 6721200.0
    assert first.status == 'Идет прием заявок'
    assert first.extra and first.attachments
```

In **test_btorg_crawl.py** replace:

```python
    first = sink.items[0]
    assert FINGERPRINT_KEYS <= first.keys()
    assert first['lot_id'] == '12850_1'
    assert first['price'] == 280000.0
    assert first['status'] == 'объявлены'
    assert first['detail']
```

with:

```python
    first = sink.items[0]
    assert first.lot_id == '12850_1'
    assert first.price == 280000.0
    assert first.status == 'объявлены'
    assert first.extra
```

In **test_ruson_crawl.py** replace (in `test_ruson_crawl_expands_trades_into_lots`):

```python
    first = sink.items[0]
    assert FINGERPRINT_KEYS <= first.keys()
    assert first['lot_id'] == '68240_1'
    assert first['price'] == 1315000.0
    assert first['status'] == 'Торги объявлены'
    assert first['detail']
```

with:

```python
    first = sink.items[0]
    assert first.lot_id == '68240_1'
    assert first.price == 1315000.0
    assert first.status == 'Торги объявлены'
    assert first.extra
```

The `FINGERPRINT_KEYS = {...}` module constant is now unused in all three files — delete that line from each. The other assertions (`len(sink.items)`, `total`, `http.calls`) are unchanged.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q`
Expected: all passed. (parse_lots unit tests are unaffected — they assert on the raw dict `parse_lots` returns, before the `Lot` wrap.)

- [ ] **Step 7: Commit**

```bash
git add collector/core/storage/sink.py collector/core/spider/parser.py collector/core/spider/dive.py collector/sources/fogsoft/base.py tests/integration/test_kendo_crawl.py tests/integration/test_btorg_crawl.py tests/integration/test_ruson_crawl.py
git commit -m "feat: emit validated Lot models through the LotSink boundary"
```

---

## Task 4: dump Lot models in the consumer sinks

**Files:**
- Modify: `main.py`, `worker.py`

- [ ] **Step 1: Update `worker.py`'s `CollectingSink`**

In `worker.py`, change the `CollectingSink` type + `save` signature, and the JSON write.

Add the import (with the other collector imports):

```python
from collector.core.lot import Lot  # noqa: E402
```

Change the sink:

```python
    def __init__(self) -> None:
        self.items: list[Lot] = []

    async def get_fingerprints(self, source: str, lot_ids: object) -> dict[str, str]:
        return {}

    async def save(self, item: Lot) -> ChangeStatus:
        self.items.append(item)
        return ChangeStatus.NEW
```

Change the write (currently `json.dumps(sink.items, …)`):

```python
        out_path.write_text(
            json.dumps(
                [lot.model_dump(mode='json') for lot in sink.items],
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )
```

- [ ] **Step 2: Update `main.py`'s `CollectingSink` and print loop**

In `main.py`, add the import (with the other collector imports):

```python
from collector.core.lot import Lot  # noqa: E402
```

Change `save` to accept a `Lot` (the body already just appends). Change the JSON write:

```python
    out.write_text(
        json.dumps(
            [lot.model_dump(mode='json') for lot in sink.items],
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
```

Change the sample print loop (`for item in sink.items[:5]:`) to attribute access:

```python
    for item in sink.items[:5]:
        print(f'- {item.lot_id:20} | {(item.trade_title or "")[:46]:46} | {item.price}')
```

- [ ] **Step 3: Verify main.py imports cleanly**

Run: `uv run python -c "import ast; ast.parse(open('main.py', encoding='utf-8').read()); ast.parse(open('worker.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add main.py worker.py
git commit -m "feat: dump Lot models to JSON in worker/main sinks"
```

---

## Task 5: full verification

**Files:** none (verification only)

- [ ] **Step 1: Full suite, green**

Run: `uv run pytest -q`
Expected: all passed.

- [ ] **Step 2: Live smoke — one site per dive engine produces valid Lot JSON**

Run: `uv run python worker.py torgi82 atctrade nistp --max-pages 1 --out data/_lotcheck`
Expected: `3/3 sites OK`.

Then check the output validates and carries the new normalized fields:

```bash
uv run python -c "
import json, glob
from collector.core.lot import Lot
for f in glob.glob('data/_lotcheck/*.json'):
    rows = json.load(open(f, encoding='utf-8'))
    assert rows, f
    r = rows[0]
    assert 'source' in r and 'extra' in r and '_source' not in r and 'detail' not in r, r.keys()
    assert 'bidding_deadline' in r and 'is_active' in r
    print(f.split('/')[-1], len(rows), 'first bidding_deadline=', r['bidding_deadline'])
print('all outputs are Lot-shaped')
"
```

Expected: prints one line per site, keys include `source`/`extra`/`bidding_deadline`/`is_active` (and NOT `_source`/`detail`).

- [ ] **Step 3: Clean up the smoke output**

```bash
rm -rf data/_lotcheck
```

(fogsoft sites are not smoke-tested here — their domains time out without the VPN allow-list; the maximal fogsoft-shaped item is covered by `tests/unit/test_lot.py::test_full_item_normalized`.)

- [ ] **Step 4: Confirm clean tree**

Run: `git status --short`
Expected: no unintended tracked changes (only the pre-existing `README_1.md`/`.idea/`).

---

## Self-Review Notes

- **Spec coverage:** §2 model → Task 2; §2.1 normalization (`parse_datetime`, `is_active`) → Tasks 1-2; §3 integration (sink contract, dive+fogsoft emits, consumer dumps, `lot_fingerprint` untouched) → Tasks 3-4; §4 files → all tasks; §5 tests → Tasks 1,2,3 + live smoke (Task 5); §6 DoD → Task 5.
- **`lot_fingerprint` deliberately untouched:** it runs in `fogsoft.parse` on raw listing-row dicts before the `Lot` wrap, so it still receives a Mapping.
- **Type consistency:** `Lot.model_validate(dict)` used at every emit; `save(item: Lot)` across the protocol and all sinks; `model_dump(mode='json')` in both consumer sinks; `_source`→`source`, `detail`→`extra` aliases consistent between the model and every assertion.
- **parse_lots unit tests unaffected:** the `Lot` conversion is at the emit boundary, not inside `parse_lots`/`parse_table`.
