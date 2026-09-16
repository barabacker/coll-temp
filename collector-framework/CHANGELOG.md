# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — unreleased

### Added

- `Settings` — one frozen dataclass per parser for proxy, timeout,
  impersonation, headers, TLS, pacing, retry policy and hooks; a subclass
  narrows its parent's with `dataclasses.replace`.
- `RetryPolicy` — retryable statuses (429, 5xx) alongside transport errors under
  one attempt budget, with `Retry-After` honoured up to `max_retry_after`.
- `Throttle` request hook, installed by `delay` / `delay_jitter`; it holds the
  gap behind a lock, so it survives `concurrency > 1`.
- `BaseParser.start_requests()` for starts a URL cannot express.
- `Response.json()`, `Response.urljoin()`, `Response.follow()`.
- `collect(parser_cls)` — run a crawl and get the items back as a list.

### Fixed

- Cancelling a crawl left its workers running (and the HTTP session with them);
  they are now cancelled from a `finally`.
- Errors were collected silently and only the first one ever surfaced, without
  saying which page failed. Each is now logged as it happens, annotated with its
  request, and kept in `parser.errors` as `(request, exception)`.

### Changed

- **Breaking**: `concurrency`, `EXTRA_CA_CERT`, `SKIP_TLS_VERIFY` and
  `RESPONSE_HOOKS` move into `settings = Settings(...)`.
- `item_count` is incremented by the crawl rather than by `process_item`, so an
  override that forgets `super()` no longer corrupts it.
- Retries are an explicit loop in `HttpClient.request` rather than a `tenacity`
  decorator, which is what lets one budget cover both failure modes.

### Removed

- The parser registry (`register_parser`, `get_parser`, `registry`,
  `unregister_parser`, `ParserNotFound`). Nothing in the framework used it, and
  it was the package's only global mutable state — how an application maps a
  name to a parser class belongs to that application.
- The `tenacity` dependency.

## [0.1.0] — unreleased

First extraction from the scraper it grew in.

### Added

- `BaseParser` with a concurrent producer/consumer `crawl()`, `Request`,
  `Response` and `ParserContext`.
- HTTP layer: `HttpClient` (curl_cffi + tenacity retries), `Middleware` with
  request/response hooks, `build_http_client`, `ca_bundle_with_extra_cert`.
- Runner: `run_parser` (sync) and `crawl` (async), both returning the finished
  parser instance.
- Param readers `read_max_pages`, `read_concurrency`, `read_flag` and the text
  helper `clean`.
