# Collector Module Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `src/collector` into three dependency layers (`core/`, `http/`, `sources/`) plus a `runner` entrypoint, and fold in the engine-independent `build_http_client` decoupling — without changing parser behavior.

**Architecture:** `core` (spider + storage + registry) is the foundation and imports nothing upward at runtime; `http` depends on `core`; `sources` (platform engines, `fogsoft` nested) depends on both; `runner`/`__init__` sit on top. The relocation is one atomic step guarded by a regression test written first; the decoupling (`RESPONSE_HOOKS`, `http/tls.py`, `http/factory.py`) follows as small TDD tasks.

**Tech Stack:** Python 3, `uv`, `curl_cffi`, `parsel`, `pytest` + `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-07-22-collector-module-restructure-design.md`

---

## File Structure (end state)

```
src/collector/
  __init__.py            facade (unchanged public symbols, updated import paths)
  runner.py              run_parser / _crawl / CrawlResult only
  core/
    __init__.py
    spider/  __init__.py parser.py request.py response.py context.py
    storage/ __init__.py sink.py contracts.py
    registry.py
  http/
    __init__.py client.py middleware.py tls.py factory.py hooks.py
  sources/
    __init__.py
    fogsoft/
      __init__.py base.py platforms.py inprotect.py
      parsing/ __init__.py tables.py detail.py viewstate.py
      certs/*.pem
tests/
  unit/ test_public_api.py test_layering.py test_base_hooks.py http/test_tls.py
  integration/ test_factory.py
```

---

## Task 0: Test tooling + regression safety net

Establishes pytest and a behavior test that passes on the CURRENT tree and must stay green through the whole restructure.

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/unit/http/__init__.py`, `tests/integration/__init__.py`
- Create: `tests/unit/test_public_api.py`

- [ ] **Step 1: Add pytest tooling to `pyproject.toml`**

Append (or merge) these sections at the end of `pyproject.toml`:

```toml
[dependency-groups]
dev = ["pytest", "pytest-asyncio"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty test package markers**

Create these four files, each containing a single line:

```python
"""Test package marker."""
```

Paths: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/unit/http/__init__.py`, `tests/integration/__init__.py`

- [ ] **Step 3: Write the regression safety-net test**

Create `tests/unit/test_public_api.py`:

```python
"""Behavior held invariant across the restructure: the public facade and the
populated parser registry. Must stay green at every step."""

from __future__ import annotations

import collector

EXPECTED_KEYS = {
    'centerr', 'alfalot', 'etpu_bankrupt', 'bep', 'arbbitlot', 'arbitat',
    'utp_lot', 'tender_one', 'etpugra', 'tendergarant', 'yuzhnyy_etp',
    'meta_invest', 'gloria_service', 'zakazrf', 'etb',
}


def test_facade_exports_are_importable():
    for name in (
        'BaseParser', 'ParserContext', 'Request', 'Response', 'LotSink',
        'ParserNotFound', 'get_parser', 'register_parser', 'registry',
        'CrawlResult', 'run_parser',
    ):
        assert hasattr(collector, name), f'missing facade export: {name}'


def test_registry_is_fully_populated():
    assert set(collector.registry()) == EXPECTED_KEYS


def test_get_parser_resolves_a_known_key():
    cls = collector.get_parser('centerr')
    assert cls.name == 'centerr'
```

- [ ] **Step 4: Run the test — it must PASS on the current tree**

Run: `uv run pytest tests/unit/test_public_api.py -v`
Expected: 3 passed. (If `registry()` count differs, fix `EXPECTED_KEYS` to match the actual active `@register_parser` decorators before proceeding — do not change parser code.)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/
git commit -m "test: pytest tooling + public-API regression safety net"
```

---

## Task 1: Relocate modules into core/ http/ sources/ (atomic move)

Pure relocation + import rewrite + inprotect consolidation. No behavior change. `build_http_client` stays in `runner.py` (still coupled to fogsoft — decoupled in Task 3). Verified by the Task 0 safety net staying green.

**Files:** many moves (see steps). Uses `git mv` to preserve history.

- [ ] **Step 1: Create new package directories with markers**

```bash
mkdir -p src/collector/core/spider src/collector/core/storage src/collector/sources/fogsoft/parsing
printf '"""collector.core — engine framework (foundation layer)."""\n' > src/collector/core/__init__.py
printf '"""collector.core.storage — persistence contract + change detection."""\n' > src/collector/core/storage/__init__.py
printf '"""collector.sources — platform engine families."""\n' > src/collector/sources/__init__.py
printf '"""collector.sources.fogsoft.parsing — page extractors."""\n' > src/collector/sources/fogsoft/parsing/__init__.py
```

- [ ] **Step 2: Move core files with `git mv`**

```bash
cd src/collector
git mv base/parser.py    core/spider/parser.py
git mv base/request.py   core/spider/request.py
git mv base/response.py  core/spider/response.py
git mv base/context.py   core/spider/context.py
git mv base/__init__.py  core/spider/__init__.py
git mv sink.py           core/storage/sink.py
git mv contracts.py      core/storage/contracts.py
git mv registry.py       core/registry.py
rmdir base
cd ../..
```

- [ ] **Step 3: Move http hooks (logging → single module)**

```bash
cd src/collector
git mv http/hooks/logging.py http/hooks.py
cd ../..
```
(`http/hooks/inprotect.py` is merged in Step 5, then the empty `http/hooks/` dir removed.)

- [ ] **Step 4: Move fogsoft engine under sources/**

```bash
cd src/collector
git mv fogsoft/base.py       sources/fogsoft/base.py
git mv fogsoft/platforms.py  sources/fogsoft/platforms.py
git mv fogsoft/__init__.py   sources/fogsoft/__init__.py
git mv fogsoft/tables.py     sources/fogsoft/parsing/tables.py
git mv fogsoft/detail.py     sources/fogsoft/parsing/detail.py
git mv fogsoft/viewstate.py  sources/fogsoft/parsing/viewstate.py
git mv fogsoft/certs         sources/fogsoft/certs
cd ../..
```

- [ ] **Step 5: Create merged `sources/fogsoft/inprotect.py` (solver + hook)**

Create `src/collector/sources/fogsoft/inprotect.py` with the full content below, then delete the two old files:

```python
"""inprotect anti-bot bypass for iTender (Fogsoft) sites: pure solver + hook.

The site is behind a JS "inprotect" challenge: the first request returns HTTP
429 with a small HTML page whose script collects a browser fingerprint and sets
two cookies, then reloads. The challenge is purely client-side — the server
only checks that the cookies ``inprotect_ok_<id>`` and ``inprotect_fp_<id>`` are
present; the nonce comes from the challenge page itself. So it is solvable over
plain HTTP, no browser.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_NONCE_RE = re.compile(r'nonce\s*=\s*"([0-9a-f]+)"')
_SITE_ID_RE = re.compile(r'inprotect_ok_(\d+)')

_DEFAULT_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
)


def looks_like_challenge(text: str, status_code: int | None = None) -> bool:
    """Is this an inprotect challenge page rather than a real listing?

    Markers: HTTP 429, or an inprotect script page with no ViewState (a real
    listing page always has __CVIEWSTATE).
    """
    if status_code == 429:
        return True
    return 'inprotect_fp_' in text and 'inprotect_ok_' in text and '__CVIEWSTATE' not in text


def build_cookies(html: str, user_agent: str | None = None) -> dict[str, str] | None:
    """Build the inprotect pass cookies from the challenge HTML.

    Returns ``{"inprotect_ok_<id>": "1", "inprotect_fp_<id>": "<base64>"}`` or
    None if the expected markers (site id / nonce) are absent.
    """
    site_id_m = _SITE_ID_RE.search(html)
    nonce_m = _NONCE_RE.search(html)
    if not (site_id_m and nonce_m):
        return None

    site_id = site_id_m.group(1)
    nonce = nonce_m.group(1)

    fp = {
        'ua': user_agent or _DEFAULT_UA,
        'plat': 'Win32',
        'lang': 'ru',
        'languages': ['ru', 'en-US', 'en'],
        'timeZone': 'Europe/Moscow',
        'devToolsOpen': False,
        'pluginsCount': 5,
        'isHeadless': False,
        'screenOrientation': 'landscape-primary',
        'timeOrigin': 1780554480011.6,
        'res': '1920x1080',
        'threads': 8,
        'chrome': 1,
        'touch': 0,
        'canvas': 180447607,
        'webgl': (
            'ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 (0x00001BE0) '
            'Direct3D11 vs_5_0 ps_5_0, D3D11)|Google Inc. (NVIDIA)'
        ),
        'fonts': 0,
        'nonce': nonce,
    }
    payload = json.dumps(fp, separators=(',', ':'), ensure_ascii=False)
    b64 = base64.b64encode(payload.encode('utf-8')).decode('ascii')
    return {f'inprotect_ok_{site_id}': '1', f'inprotect_fp_{site_id}': b64}


async def solve_inprotect(response: Any, *, session: Any, retry: Any) -> Any:
    """Response hook: if the response is an inprotect challenge, set the pass
    cookies and retry."""
    if not looks_like_challenge(response.text, response.status_code):
        return response

    cookies = build_cookies(response.text)
    if not cookies:
        logger.warning(
            'inprotect.unsolvable url=%s status=%s',
            getattr(response, 'url', '?'),
            response.status_code,
        )
        return response

    for name, value in cookies.items():
        session.cookies.set(name, value)
    logger.info(
        'inprotect.solved url=%s cookies=%s', getattr(response, 'url', '?'), sorted(cookies)
    )

    return await retry()
```

Then remove the superseded files:

```bash
cd src/collector
git rm fogsoft/inprotect.py http/hooks/inprotect.py
rmdir http/hooks fogsoft
git add sources/fogsoft/inprotect.py
cd ../..
```

- [ ] **Step 6: Rewrite imports in `core/spider/parser.py`**

Change these four import lines:
- `from collector.base.context import ParserContext` → `from collector.core.spider.context import ParserContext`
- `from collector.base.request import Request` → `from collector.core.spider.request import Request`
- `from collector.base.response import Response` → `from collector.core.spider.response import Response`
- `from collector.contracts import ChangeStatus` → `from collector.core.storage.contracts import ChangeStatus`

- [ ] **Step 7: Rewrite imports in remaining core files**

`core/spider/__init__.py` — replace body with:

```python
"""Spider-style parser base classes: Request/Response/ParserContext/BaseParser."""

from __future__ import annotations

from collector.core.spider.context import ParserContext
from collector.core.spider.parser import BaseParser
from collector.core.spider.request import Request
from collector.core.spider.response import Response

__all__ = ['BaseParser', 'ParserContext', 'Request', 'Response']
```

`core/spider/context.py` — under `if TYPE_CHECKING:` change `from collector.sink import LotSink` → `from collector.core.storage.sink import LotSink` (leave `from collector.http.client import HttpClient` as-is).

`core/spider/response.py` — change `from collector.base.request import Request` → `from collector.core.spider.request import Request`.

`core/storage/sink.py` — change `from collector.contracts import ChangeStatus` → `from collector.core.storage.contracts import ChangeStatus`.

`core/registry.py` — change `from collector.base import BaseParser` → `from collector.core.spider import BaseParser`.

(`core/spider/request.py` and `core/storage/contracts.py` have no `collector` imports — leave them.)

- [ ] **Step 8: Rewrite imports in `sources/fogsoft/base.py`**

Change:
- `from collector.base import BaseParser, Request, Response` → `from collector.core.spider import BaseParser, Request, Response`
- `from collector.contracts import lot_fingerprint` → `from collector.core.storage.contracts import lot_fingerprint`
- `from collector.fogsoft.detail import (` → `from collector.sources.fogsoft.parsing.detail import (`
- `from collector.fogsoft.tables import (` → `from collector.sources.fogsoft.parsing.tables import (`
- `from collector.fogsoft.viewstate import (` → `from collector.sources.fogsoft.parsing.viewstate import (`

- [ ] **Step 9: Rewrite imports in `sources/fogsoft/platforms.py`**

Change:
- `from collector.fogsoft.base import TenderFogsoft` → `from collector.sources.fogsoft.base import TenderFogsoft`
- `from collector.registry import register_parser` → `from collector.core.registry import register_parser`

- [ ] **Step 10: Rewrite imports in `runner.py` (still coupled — decoupled in Task 3)**

Change the import block and `_FOGSOFT_DIR`:
- `from collector.base import BaseParser, ParserContext` → `from collector.core.spider import BaseParser, ParserContext`
- `from collector.fogsoft.base import TenderFogsoft` → `from collector.sources.fogsoft.base import TenderFogsoft`
- `from collector.http.hooks.inprotect import solve_inprotect` → `from collector.sources.fogsoft.inprotect import solve_inprotect`
- `from collector.http.hooks.logging import log_request, log_response` → `from collector.http.hooks import log_request, log_response`
- `from collector.sink import LotSink` → `from collector.core.storage.sink import LotSink`
- `_FOGSOFT_DIR = Path(__file__).parent / 'fogsoft'` → `_FOGSOFT_DIR = Path(__file__).parent / 'sources' / 'fogsoft'`

- [ ] **Step 11: Rewrite the facade `collector/__init__.py`**

Replace the import block (keep the module docstring and `__all__` unchanged):

```python
from collector.core.spider import BaseParser, ParserContext, Request, Response

# Side-effect import: registers every Fogsoft platform parser.
from collector.sources.fogsoft import platforms as _fogsoft_platforms  # noqa: E402,F401
from collector.core.registry import ParserNotFound, get_parser, register_parser, registry
from collector.runner import CrawlResult, run_parser
from collector.core.storage.sink import LotSink
```

- [ ] **Step 12: Rewrite import in `main.py`**

Change `from collector.contracts import ChangeStatus  # noqa: E402` → `from collector.core.storage.contracts import ChangeStatus  # noqa: E402`.

- [ ] **Step 13: Verify the package imports cleanly**

Run: `uv run python -c "import collector; print(sorted(collector.registry()))"`
Expected: prints the sorted list of 15 keys, no ImportError.

- [ ] **Step 14: Run the safety net — must still PASS**

Run: `uv run pytest tests/unit/test_public_api.py -v`
Expected: 3 passed.

- [ ] **Step 15: Commit**

```bash
git add -A
git commit -m "refactor: relocate collector into core/http/sources layers"
```

---

## Task 2: Declare RESPONSE_HOOKS / TLS extension points on parsers

Adds the declarative ClassVars. No wiring change yet (`runner` still uses `issubclass`), so behavior is unchanged; both mechanisms coexist until Task 3.

**Files:**
- Modify: `src/collector/core/spider/parser.py`
- Modify: `src/collector/sources/fogsoft/base.py`
- Test: `tests/unit/test_base_hooks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_base_hooks.py`:

```python
"""Parsers declare their own HTTP specifics via class attributes."""

from __future__ import annotations

from collector.core.spider import BaseParser
from collector.sources.fogsoft.base import TenderFogsoft
from collector.sources.fogsoft.inprotect import solve_inprotect


def test_base_parser_defaults():
    assert BaseParser.RESPONSE_HOOKS == ()
    assert BaseParser.EXTRA_CA_CERT is None
    assert BaseParser.SKIP_TLS_VERIFY is False


def test_fogsoft_declares_inprotect_hook():
    assert TenderFogsoft.RESPONSE_HOOKS == (solve_inprotect,)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_base_hooks.py -v`
Expected: FAIL with `AttributeError: ... RESPONSE_HOOKS`.

- [ ] **Step 3: Add ClassVars to `BaseParser`**

In `src/collector/core/spider/parser.py`:

Add a `TYPE_CHECKING` import block after the existing imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collector.http.middleware import ResponseHook
```

Add these three class attributes to `BaseParser`, right after `concurrency: ClassVar[int] = 1`:

```python
    EXTRA_CA_CERT: ClassVar[str | None] = None
    SKIP_TLS_VERIFY: ClassVar[bool] = False
    RESPONSE_HOOKS: ClassVar[tuple[ResponseHook, ...]] = ()
```

(The module already has `from __future__ import annotations`, so the `ResponseHook` reference in the annotation stays a string and creates no runtime import of `http`.)

- [ ] **Step 4: Add RESPONSE_HOOKS to `TenderFogsoft`**

In `src/collector/sources/fogsoft/base.py`:

Add the import (with the other imports):

```python
from collector.sources.fogsoft.inprotect import solve_inprotect
```

Add the class attribute right after `SKIP_TLS_VERIFY: ClassVar[bool] = False`:

```python
    RESPONSE_HOOKS: ClassVar[tuple[ResponseHook, ...]] = (solve_inprotect,)
```

Add the `ResponseHook` TYPE_CHECKING import (base.py already imports `TYPE_CHECKING`? if not, add it):

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collector.http.middleware import ResponseHook
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_base_hooks.py tests/unit/test_public_api.py -v`
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: declarative RESPONSE_HOOKS/TLS attrs on parsers"
```

---

## Task 3: Extract http/tls.py + http/factory.py; make build_http_client engine-independent

Moves the TLS bundle util and the HTTP-client factory out of `runner`, drops the `issubclass(TenderFogsoft)` coupling. `runner` becomes just the sync bridge.

**Files:**
- Create: `src/collector/http/tls.py`, `src/collector/http/factory.py`
- Modify: `src/collector/runner.py`
- Test: `tests/unit/http/test_tls.py`, `tests/integration/test_factory.py`, `tests/unit/test_layering.py`

- [ ] **Step 1: Write the failing TLS test**

Create `tests/unit/http/test_tls.py`:

```python
"""ca_bundle_with_extra_cert builds a certifi bundle plus a site's extra cert."""

from __future__ import annotations

from pathlib import Path

import certifi

from collector.http.tls import ca_bundle_with_extra_cert


def test_bundle_contains_certifi_and_extra(tmp_path: Path):
    extra = tmp_path / 'extra.pem'
    extra.write_text('-----BEGIN CERTIFICATE-----\nEXTRA_MARKER\n-----END CERTIFICATE-----\n')

    bundle_path = ca_bundle_with_extra_cert(str(extra))
    text = Path(bundle_path).read_text(encoding='utf-8')

    assert 'EXTRA_MARKER' in text
    assert Path(certifi.where()).read_text(encoding='utf-8')[:200] in text


def test_bundle_is_cached_per_path(tmp_path: Path):
    extra = tmp_path / 'extra.pem'
    extra.write_text('-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n')

    assert ca_bundle_with_extra_cert(str(extra)) == ca_bundle_with_extra_cert(str(extra))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/unit/http/test_tls.py -v`
Expected: FAIL with `ModuleNotFoundError: collector.http.tls`.

- [ ] **Step 3: Create `src/collector/http/tls.py`**

```python
"""TLS helper: build a certifi CA bundle augmented with a site's extra cert."""

from __future__ import annotations

import functools
import tempfile
from pathlib import Path

import certifi


@functools.cache
def ca_bundle_with_extra_cert(cert_path: str) -> str:
    """Build (and disk-cache) a certifi bundle plus a site's extra certificate.

    Some sites omit an intermediate certificate from their TLS chain;
    curl/BoringSSL, unlike browsers, will not fetch it, so we append it here.
    ``cert_path`` is an absolute path to the extra PEM file (the caller resolves
    it — see http.factory).
    """
    combined = Path(certifi.where()).read_text(encoding='utf-8')
    combined += '\n' + Path(cert_path).read_text(encoding='utf-8')
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.pem', prefix='ca-bundle-', delete=False, encoding='utf-8'
    )
    tmp.write(combined)
    tmp.close()
    return tmp.name
```

- [ ] **Step 4: Run the TLS test to verify it passes**

Run: `uv run pytest tests/unit/http/test_tls.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write the failing factory + layering tests**

Create `tests/integration/test_factory.py`:

```python
"""build_http_client wires hooks and TLS from the parser class, engine-agnostic."""

from __future__ import annotations

from typing import Any

import pytest

from collector.core.spider import BaseParser
from collector.sources.fogsoft.inprotect import solve_inprotect
from collector.sources.fogsoft.platforms import (
    ArbBitLotParser,
    CenterrParser,
    MetaInvestParser,
)


class _Bare(BaseParser):
    name = '_bare_test'

    async def parse(self, response: Any):  # pragma: no cover - never run
        yield {}


@pytest.fixture
def captured(monkeypatch):
    """Capture AsyncSession kwargs and the resolved extra-cert path."""
    seen: dict[str, Any] = {}

    class _FakeSession:
        def __init__(self, **kwargs: Any):
            seen['session_kwargs'] = kwargs

        async def close(self) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr('collector.http.factory.AsyncSession', _FakeSession)
    monkeypatch.setattr(
        'collector.http.factory.ca_bundle_with_extra_cert',
        lambda path: seen.setdefault('cert_path', path) or '/tmp/fake-bundle.pem',
    )
    return seen


def test_fogsoft_parser_gets_inprotect_hook(captured):
    from collector.http.factory import build_http_client

    client = build_http_client(CenterrParser)
    assert solve_inprotect in client.middleware.response_middleware


def test_bare_parser_has_no_inprotect_hook(captured):
    from collector.http.factory import build_http_client

    client = build_http_client(_Bare)
    assert solve_inprotect not in client.middleware.response_middleware


def test_skip_tls_verify_disables_verification(captured):
    from collector.http.factory import build_http_client

    build_http_client(ArbBitLotParser)
    assert captured['session_kwargs'].get('verify') is False


def test_extra_ca_cert_resolved_against_parser_module(captured):
    from collector.http.factory import build_http_client

    build_http_client(MetaInvestParser)
    cert_path = captured['cert_path'].replace('\\', '/')
    assert cert_path.endswith(
        'sources/fogsoft/certs/meta_invest_globalsign_gcc_r3_dv_tls_ca_2020.pem'
    )
```

Create `tests/unit/test_layering.py`:

```python
"""The runner entrypoint must not depend on any concrete engine (sources)."""

from __future__ import annotations

import inspect

import collector.runner


def test_runner_does_not_import_sources():
    src = inspect.getsource(collector.runner)
    assert 'collector.sources' not in src
    assert 'fogsoft' not in src
    assert '_FOGSOFT_DIR' not in src
```

- [ ] **Step 6: Run them to verify they fail**

Run: `uv run pytest tests/integration/test_factory.py tests/unit/test_layering.py -v`
Expected: FAIL — `collector.http.factory` missing, and `runner` still references `fogsoft`.

- [ ] **Step 7: Create `src/collector/http/factory.py`**

```python
"""build_http_client — assemble an HttpClient from a parser class, engine-agnostic."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from curl_cffi.requests import AsyncSession

from collector.core.spider import BaseParser
from collector.http.client import HttpClient
from collector.http.hooks import log_request, log_response
from collector.http.middleware import Middleware
from collector.http.tls import ca_bundle_with_extra_cert


def build_http_client(parser_cls: type[BaseParser]) -> HttpClient:
    """Assemble an ``HttpClient`` with the hooks and TLS config a parser declares."""
    middleware = Middleware()
    middleware.request(log_request)
    middleware.response(log_response)
    for hook in parser_cls.RESPONSE_HOOKS:
        middleware.response(hook)

    session_kwargs: dict[str, Any] = {'impersonate': 'chrome'}
    if parser_cls.EXTRA_CA_CERT:
        cert_path = Path(inspect.getfile(parser_cls)).parent / parser_cls.EXTRA_CA_CERT
        session_kwargs['verify'] = ca_bundle_with_extra_cert(str(cert_path))
    elif parser_cls.SKIP_TLS_VERIFY:
        session_kwargs['verify'] = False

    session: AsyncSession[Any] = AsyncSession(**session_kwargs)
    return HttpClient(session, middleware)
```

- [ ] **Step 8: Slim down `src/collector/runner.py`**

Replace the whole file with:

```python
"""Bridge between the async parser core and the synchronous RQ task.

Runs ``crawl()`` under ``asyncio.run`` and returns the counts. HTTP-client
assembly lives in ``collector.http.factory``; TLS bundling in
``collector.http.tls``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from collector.core.spider import BaseParser, ParserContext
from collector.core.storage.sink import LotSink
from collector.http.factory import build_http_client

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CrawlResult:
    total: int
    new: int
    changed: int


async def _crawl(
    parser_cls: type[BaseParser],
    params: dict[str, str],
    sink: LotSink | None,
    log: Any,
) -> CrawlResult:
    http = build_http_client(parser_cls)
    async with http:
        ctx = ParserContext(http=http, params=params, lot_sink=sink, log=log)
        parser = parser_cls(ctx)
        total = await parser.crawl()
    return CrawlResult(total=total, new=parser.new_item_count, changed=parser.changed_item_count)


def run_parser(
    parser_cls: type[BaseParser],
    *,
    params: dict[str, str] | None = None,
    sink: LotSink | None = None,
) -> CrawlResult:
    """Run a parser to completion synchronously. Called from the RQ task.

    ``sink`` is injected by the caller (the Django side passes an ORM sink).
    Passing ``None`` runs the crawl without persisting — useful for a smoke
    check that hits the site but writes nothing.
    """

    async def _log(message: str) -> None:
        logger.info('[%s] %s', parser_cls.name, message)

    return asyncio.run(_crawl(parser_cls, params or {}, sink, _log))
```

- [ ] **Step 9: Run the new tests to verify they pass**

Run: `uv run pytest tests/integration/test_factory.py tests/unit/test_layering.py -v`
Expected: all passed.

- [ ] **Step 10: Run the full suite**

Run: `uv run pytest -v`
Expected: all passed (public_api, base_hooks, tls, factory, layering).

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "refactor: engine-independent build_http_client in http/factory + http/tls"
```

---

## Task 4: Final verification + cleanup

**Files:**
- Modify: `src/collector/sources/fogsoft/certs/meta_invest_globalsign_gcc_r3_dv_tls_ca_2020.pem` (stale comment)

- [ ] **Step 1: Remove the stale `cli.py` comment in the cert file**

Open `src/collector/sources/fogsoft/certs/meta_invest_globalsign_gcc_r3_dv_tls_ca_2020.pem`. If it contains a comment line mentioning `build_http_client() в cli.py`, update it to reference `http/factory.py` or delete that comment line. Leave the PEM certificate block untouched.

- [ ] **Step 2: Confirm the final tree**

Run: `uv run python -c "import collector, pathlib; print('\n'.join(sorted(str(p.relative_to('src')) for p in pathlib.Path('src/collector').rglob('*.py'))))"`
Expected: paths match the File Structure section (no `base/`, no `http/hooks/`, no top-level `contracts.py`/`sink.py`/`registry.py`/`fogsoft/`).

- [ ] **Step 3: Full test suite, green, no network**

Run: `uv run pytest -v`
Expected: all passed.

- [ ] **Step 4: Registry sanity via the CLI entrypoint**

Run: `uv run python main.py --list`
Expected: prints all 15 platform keys (no crawl, no network).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: cert comment cleanup + final restructure verification"
```

---

## Self-Review Notes

- **Spec coverage:** §2 tree → Tasks 1/3/4; §3 layering → Task 3 (test_layering); §4 move-map → Task 1; §5 decoupling → Tasks 2+3; §6 inprotect merge → Task 1 Step 5; §7 imports → Task 1 Steps 6–12; §8 tooling/guards → Tasks 0/2/3; §9 order → task order; §10 DoD → Task 4.
- **Behavior invariance:** the Task 0 safety net (`test_public_api`) is written before any move and re-run after Tasks 1 & 2; response-hook order (LIFO) is preserved because `factory` registers `log_response` before iterating `RESPONSE_HOOKS`, matching the old `runner`.
- **Type consistency:** `RESPONSE_HOOKS: tuple[ResponseHook, ...]`, `ca_bundle_with_extra_cert(cert_path: str) -> str`, and `build_http_client(parser_cls: type[BaseParser]) -> HttpClient` are used identically across tasks.
