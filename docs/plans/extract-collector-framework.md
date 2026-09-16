# Plan: extract the scraping micro-framework into `collector`

Status: proposed (awaiting go-ahead)
Branch: `claude/clever-volta-jlw1br`

## Decisions (agreed with the owner)

| Question | Decision |
|---|---|
| Purpose | Open-source package: own repo, README/LICENSE/CHANGELOG, semver, own CI |
| Scope | Minimal: spider + http + registry + runner only |
| Packaging | Separate repository (staged here first, moved out afterwards) |
| Framework name | import `collector`, PyPI distribution `collector-framework` (`collector` is taken) |
| Domain package | current `collector/` is renamed to `tenders/` in this repo |

## 1. Boundary

**Moves to the framework (`collector`)**

- `core/spider/{request,response,context,parser}.py` — Request / Response / ParserContext / BaseParser
- `core/registry.py` — register_parser / get_parser / registry
- `runner.py` — the sync `asyncio.run` bridge
- `http/` — client (curl_cffi + tenacity), middleware, hooks, tls, factory
- generic half of `core/parsing.py`: `read_max_pages`, `read_concurrency`, `read_only_active` → `collector/params.py`; `clean` → `collector/text.py`

**Stays in the domain (`tenders`)**

- `core/lot.py` (`Lot`), RU-specific parsing (`parse_price`, `parse_datetime`, `is_active_status`, `pick_status`)
- `core/storage/` (`LotSink`, `ChangeStatus`, `lot_fingerprint`, `FINGERPRINT_FIELDS`)
- `core/spider/dive.py` (`DiveParser` — the listing→dive→lot pattern, status-aware)
- `sources/*`, `platforms.py`, `platforms.toml`

## 2. Decouplings required before the move

1. `BaseParser.process_item` currently knows `Lot` / `LotSink` / `ChangeStatus`.
   Framework version: `async def process_item(self, item: Any) -> None` that only
   increments `item_count`. The sink call and the NEW/CHANGED counters move into a
   `tenders` subclass (`LotParser`).
2. `ParserContext.lot_sink: LotSink | None` → `sink: Any | None` (framework holds no
   storage contract). Domain code keeps its typed sink via its own context usage.
3. `runner.CrawlResult(total, new, changed)` is domain-shaped. Framework
   `run_parser()` returns the finished **parser instance** (so any counter is
   reachable); `tenders.runner` keeps the current `CrawlResult` facade so
   `worker.py` / `main.py` stay unchanged in behavior.
4. `core/parsing.py` splits (see boundary above). `is_active_status` /
   `read_only_active` stay together in the domain, since `read_only_active` only
   has meaning next to a status notion — framework keeps `read_max_pages` and
   `read_concurrency`.
5. `platforms.py` stays domain-side and calls `collector.register_parser`.

## 3. Target layout of the new repo (staged in `collector-framework/`)

```
collector-framework/
  pyproject.toml          name = "collector-framework", module = collector
  README.md  LICENSE(MIT)  CHANGELOG.md  .gitignore
  .github/workflows/ci.yml   ruff + pytest
  src/collector/
    __init__.py           facade
    py.typed
    registry.py  runner.py  params.py  text.py
    spider/{__init__,request,response,context,parser}.py
    http/{__init__,client,factory,middleware,hooks,tls}.py
  tests/                  framework-only tests (no RU domain fixtures)
```

Public API v0.1.0: `BaseParser`, `Request`, `Response`, `ParserContext`,
`register_parser`, `get_parser`, `registry`, `ParserNotFound`, `run_parser`,
`HttpClient`, `Middleware`, `RequestHook`, `ResponseHook`, `build_http_client`,
`read_max_pages`, `read_concurrency`, `clean`.

## 4. Steps (each one ends green)

1. **Plan** (this file).
2. **Stage the framework**: create `collector-framework/` with the modules above,
   docstrings de-domained (no mentions of lots/trades/Django), plus its own tests
   and CI. Verify: `pytest collector-framework/tests`.
3. **Rename the domain**: `collector/` → `tenders/`, drop the modules that moved,
   add `LotParser` (sink + counters), `tenders/runner.py`, fix every import.
   Depend on the framework via `tool.uv.sources` path `./collector-framework`
   until the real repo exists.
4. **Fix the tests**: split `test_layering.py` (framework has no `tenders` import;
   `tenders` core has no http/sources import), retarget `test_public_api.py`.
5. **Verify**: full `pytest`, `uv run python worker.py --list`, one real smoke run
   with `--max-pages 1` on a single site.
6. **Push** the branch. Moving `collector-framework/` into its own GitHub repo is a
   separate, mechanical step done afterwards (git subtree split or plain copy).

## 5. Risks

- Renaming `collector` → `tenders` touches every source file; it is mechanical but
  wide. Mitigated by keeping step 3 a single commit with no behavior change.
- `run_parser` signature change is the only public-behavior break; `worker.py` and
  `main.py` are the only callers and are updated in the same commit.
- `worker.zip` (97 MB) is already committed on `main` and is untouched here.
- Open-source hygiene (README examples, license headers) is scoped to the new repo
  only; the RU-language docs of this repo stay as they are.
