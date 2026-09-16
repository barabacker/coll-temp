# collector

A tiny async scraping framework: Spider-style parsers, a `curl_cffi` HTTP layer
with middleware, and a parser registry. Roughly 450 lines — small enough to read
in one sitting, and it stays out of your domain model.

```python
from collector import BaseParser, run_parser


class Quotes(BaseParser):
    name = 'quotes'
    start_urls = ['https://quotes.toscrape.com/']
    concurrency = 4

    async def parse(self, response):
        for quote in response.selector().css('div.quote'):
            yield {
                'text': quote.css('span.text::text').get(),
                'author': quote.css('small.author::text').get(),
            }

        next_page = response.selector().css('li.next a::attr(href)').get()
        if next_page:
            yield self.request(response.request.url.rstrip('/') + next_page)


parser = run_parser(Quotes)
print(parser.item_count)
```

## Why it exists

`Scrapy` brings a whole runtime (its own event loop, settings, signals, project
layout) and `requests`-in-a-loop brings none. This sits in between: an async
producer/consumer crawl you can embed in a worker, a CLI or a web job, with
browser impersonation via `curl_cffi` for sites that fingerprint TLS.

## What you get

- **`BaseParser`** — `parse()` is an async generator: yield a `Request` to
  follow, yield anything else to emit it as an item. `crawl()` runs a queue with
  `concurrency` workers, collects per-request errors instead of killing a worker,
  and re-raises the first one at the end.
- **HTTP layer** — `curl_cffi` with Chrome impersonation, `tenacity` retries
  (4 attempts, exponential 1–60s) and request/response middleware. A response
  hook can `await retry()` to re-run a request, which is how an anti-bot
  challenge gets solved without the parser knowing.
- **Per-parser HTTP declarations** — `EXTRA_CA_CERT` (a site that omits an
  intermediate certificate), `SKIP_TLS_VERIFY`, `RESPONSE_HOOKS`. The client is
  assembled from the class, so the caller does not carry site quirks.
- **Registry** — `@register_parser('key')` / `get_parser('key')`, so a job can
  name a parser by string.
- **Param readers** — `read_max_pages`, `read_concurrency`, `read_flag`: the
  knobs arrive as strings and a bad value falls back instead of raising.

## What you do not get, by design

No item schema, no storage, no scheduler, no deduplication, no robots.txt or
throttling policy. The framework never persists anything: override
`process_item()` and write to `ctx.sink`, which it passes through untouched.

```python
class Saving(Quotes):
    async def process_item(self, item):
        await super().process_item(item)  # keeps item_count accurate
        await self.ctx.sink.save(item)
```

## Install

```bash
pip install collector-framework     # import name: collector
```

Requires Python 3.11+.

## Status

`0.1.0`, extracted from a production scraper that runs ~30 sites. The API is
young: minor versions may break it until `1.0`.

## License

MIT
