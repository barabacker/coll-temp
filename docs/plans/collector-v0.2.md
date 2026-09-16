# Plan: collector v0.2 — settings, retry policy, parser ergonomics

Status: done (framework v0.2.0 + tenders migrated)
Branch: `claude/clever-volta-jlw1br`

## Decisions (agreed with the owner)

- Scope: (1) session config + retry, (2) ready-made middleware, (3) parser ergonomics.
  Crawl discipline (dupe filter, max_requests, stats) is deferred.
- Config shape: one `Settings` dataclass per parser, replacing the loose ClassVars.
  This is a breaking change, taken deliberately while the package is at 0.x.

## 1. `collector/settings.py`

```python
@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 4
    multiplier / min_wait / max_wait        # exponential backoff
    statuses: frozenset[int] = {429, 500, 502, 503, 504}
    respect_retry_after: bool = True
    max_retry_after: float = 60.0

@dataclass(frozen=True, slots=True)
class Settings:
    # transport
    impersonate, timeout, proxy, headers, session_kwargs (escape hatch)
    extra_ca_cert, skip_tls_verify
    # pacing
    concurrency, delay, delay_jitter
    # policy and hooks
    retry: RetryPolicy
    request_hooks, response_hooks
```

A parser sets `settings = Settings(...)`; a subclass narrows it with
`dataclasses.replace(Base.settings, ...)`.

## 2. One retry mechanism instead of two

Today `tenacity` retries network exceptions on `HttpClient.request`, and a bad
status is nobody's business. Replacing the decorator with an explicit loop in
`request()` gives one attempt counter covering both, lets `Retry-After` be
honoured, and drops the `tenacity` dependency.

The hook-driven `await retry()` (used to re-run a request after solving a
challenge) stays as it is — a different mechanism for a different reason.

## 3. Ready-made middleware

`Throttle(delay, jitter)` — a stateful request hook that spaces requests out
behind an `asyncio.Lock`, so it holds with `concurrency > 1`. Lives next to the
logging hooks in `http/hooks.py`; the factory registers it when
`settings.delay` is set. No new package: `middleware.py` stays the mechanism,
`hooks.py` the ready-made hooks.

## 4. Parser ergonomics

- `Response.urljoin(href)`, `Response.follow(href, **kwargs) -> Request`
  (callback defaults to `parse`, as `_handle` already falls back), `Response.json()`.
- `BaseParser.start_requests()` — an async generator, defaulting to `start_urls`,
  so a POST start or per-start metadata no longer needs a `crawl()` override.
- `collector.collect(parser_cls, **kwargs) -> list` — run a crawl and get the
  items back, without writing a sink for a one-off.

## 5. Migration of `tenders`

`concurrency` / `EXTRA_CA_CERT` / `SKIP_TLS_VERIFY` / `RESPONSE_HOOKS` become
`settings = Settings(...)`; `platforms.py` builds each class's settings with
`replace()` from its engine's; the three affected tests follow.

## 6. Verification

Framework suite on 3.11-3.14, domain suite, `worker.py --list`. A live run is
impossible in this container (the proxy blocks outbound hosts).
