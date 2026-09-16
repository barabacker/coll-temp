"""BaseParser — Spider-style base class for parsers."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any, ClassVar

from collector.params import read_concurrency
from collector.spider.context import ParserContext
from collector.spider.request import Request
from collector.spider.response import Response

if TYPE_CHECKING:
    from collector.http.middleware import ResponseHook


class BaseParser(ABC):
    """Spider-style parser with a concurrent ``crawl()``.

    A subclass sets ``name`` / ``start_urls`` and implements ``parse()`` as an
    async generator: yield a ``Request`` to enqueue it, yield anything else to
    emit it as an item.

    The class attributes below are read by ``collector.http.build_http_client``
    when it assembles the client for this parser, so a parser declares its own
    HTTP quirks instead of the caller knowing about them.
    """

    name: ClassVar[str]
    start_urls: ClassVar[list[str]] = []
    concurrency: ClassVar[int] = 1
    #: PEM file with an extra CA/intermediate certificate, resolved relative to
    #: the file the parser class is defined in.
    EXTRA_CA_CERT: ClassVar[str | None] = None
    #: Disable TLS verification outright. Only for a certificate that is broken
    #: on the site's side and that no CA bundle can fix.
    SKIP_TLS_VERIFY: ClassVar[bool] = False
    #: Response hooks added to this parser's client (e.g. an anti-bot solver).
    RESPONSE_HOOKS: ClassVar[tuple[ResponseHook, ...]] = ()

    def __init__(self, ctx: ParserContext) -> None:
        self.ctx = ctx
        self.http = ctx.http
        self.item_count = 0
        self._errors: list[Exception] = []

    def request(
        self,
        url: str,
        *,
        method: str = 'GET',
        callback: Callable[[Response], AsyncIterator[Request | Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: dict[str, str] | str | None = None,
    ) -> Request:
        """Build a ``Request`` defaulting its callback to ``self.parse``."""
        return Request(
            url=url,
            method=method,
            callback=callback or self.parse,
            metadata=metadata or {},
            headers=headers,
            data=data,
        )

    @abstractmethod
    def parse(self, response: Response) -> AsyncIterator[Request | Any]:
        """yield ``Request`` to enqueue; yield anything else to emit an item."""

    async def log(self, message: str) -> None:
        """Write a message to the job log. No-op if ``ctx.log`` is unset."""
        if self.ctx.log is not None:
            await self.ctx.log(message)

    async def process_item(self, item: Any) -> None:
        """Handle one emitted item. Counts it; override to persist it.

        The framework stores nothing: an application overrides this to write the
        item to ``self.ctx.sink`` (and to keep whatever extra counters it needs),
        calling ``super().process_item(item)`` to keep ``item_count`` accurate.
        """
        self.item_count += 1

    async def crawl(self) -> int:
        """Run producer/consumer crawling with ``concurrency`` workers.

        Returns the number of items emitted. The first error collected while
        handling requests is re-raised once all workers have finished, so one bad
        page neither kills a worker nor passes silently.
        """
        queue: asyncio.Queue[Request] = asyncio.Queue()
        for url in self.start_urls:
            queue.put_nowait(self.request(url))

        async def worker() -> None:
            while True:
                req = await queue.get()
                try:
                    await self._handle(req, queue)
                except Exception as exc:  # noqa: BLE001 — collect, don't kill the worker
                    self._errors.append(exc)
                finally:
                    queue.task_done()

        n_workers = read_concurrency(self.ctx.params, self.concurrency)
        workers = [asyncio.create_task(worker()) for _ in range(n_workers)]
        await queue.join()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        if self._errors:
            raise self._errors[0]
        return self.item_count

    async def _handle(self, req: Request, queue: asyncio.Queue[Request]) -> None:
        raw = await self.http.request(req.method, req.url, headers=req.headers, data=req.data)
        response = Response(raw, req)
        callback = req.callback or self.parse
        async for result in callback(response):
            if isinstance(result, Request):
                queue.put_nowait(result)
            else:
                await self.process_item(result)
