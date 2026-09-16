# collector

A tiny async scraping framework: Spider-style parsers over a `curl_cffi` HTTP
layer with middleware, retries and throttling. Under 900 lines — small enough to
read in one sitting, and it stays out of your domain model.

```python
from collector import BaseParser, Settings, collect


class Quotes(BaseParser):
    name = 'quotes'
    start_urls = ['https://quotes.toscrape.com/']
    settings = Settings(concurrency=4, delay=0.5)

    async def parse(self, response):
        for quote in response.selector().css('div.quote'):
            yield {
                'text': quote.css('span.text::text').get(),
                'author': quote.css('small.author::text').get(),
            }

        next_page = response.selector().css('li.next a::attr(href)').get()
        if next_page:
            yield response.follow(next_page)


for quote in collect(Quotes):
    print(quote['author'])
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
  and re-raises the first one at the end. `start_requests()` covers a start that
  a URL cannot express — a POST, or per-start metadata.
- **`Settings`** — one frozen dataclass per parser holding proxy, timeout,
  impersonation, headers, TLS quirks, pacing, retry policy and hooks. A subclass
  narrows its parent's with `dataclasses.replace`. The HTTP client is assembled
  from it, so the caller never carries site quirks.
- **One retry policy** — `RetryPolicy` covers both failure modes with a single
  attempt budget: transport errors and retryable statuses (429 and the 5xx
  family), with exponential backoff and `Retry-After` honoured up to a cap you
  set. A response hook can separately `await retry()` to re-run a request, which
  is how an anti-bot challenge gets solved without the parser knowing.
- **Throttling** — `delay` and `delay_jitter` install a `Throttle` hook that
  spaces requests out behind a lock, so the gap holds with `concurrency > 1`.
- **Response helpers** — `selector()` (parsel), `json()`, `urljoin()` and
  `follow()` for a link on the page.
- **Param readers** — `read_max_pages`, `read_concurrency`, `read_flag`: the
  knobs arrive as strings and a bad value falls back instead of raising.

## What you do not get, by design

No item schema, no storage, no scheduler, no request de-duplication, no
robots.txt, and no registry — how an application names and looks up a parser is
its own business, and a library holding global mutable state for it is a cost,
not a feature. The framework never persists anything: override `process_item()` and
write to `ctx.sink`, which it passes through untouched.

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

`0.2.0`, extracted from a production scraper that runs ~30 sites. The API is
young: minor versions may break it until `1.0`.

## License

MIT
