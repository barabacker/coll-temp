# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — unreleased

First extraction from the scraper it grew in.

### Added

- `BaseParser` with a concurrent producer/consumer `crawl()`, `Request`,
  `Response` and `ParserContext`.
- HTTP layer: `HttpClient` (curl_cffi + tenacity retries), `Middleware` with
  request/response hooks, `build_http_client`, `ca_bundle_with_extra_cert`.
- Parser registry: `register_parser`, `get_parser`, `registry`,
  `unregister_parser`, `ParserNotFound`.
- Runner: `run_parser` (sync) and `crawl` (async), both returning the finished
  parser instance.
- Param readers `read_max_pages`, `read_concurrency`, `read_flag` and the text
  helper `clean`.
