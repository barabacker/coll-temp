"""BaseParser — Spider-style base class for parsers."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from typing import Any, ClassVar

from collector.params import read_concurrency
from collector.settings import Settings
from collector.spider.context import ParserContext
from collector.spider.request import Request
from collector.spider.response import Response

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Spider-style parser with a concurrent ``crawl()``.

    A subclass sets ``name`` / ``start_urls`` and implements ``parse()`` as an
    async generator: yield a ``Request`` to enqueue it, yield anything else to
    emit it as an item.

    ``settings`` is how a parser declares its own HTTP quirks (proxy, timeout,
    TLS, pacing, hooks) instead of the caller knowing about them; a subclass
    narrows its parent's with ``dataclasses.replace``.
    """

    name: ClassVar[str]
    start_urls: ClassVar[list[str]] = []
    settings: ClassVar[Settings] = Settings()

    def __init__(self, ctx: ParserContext) -> None:
        self.ctx = ctx
        self.http = ctx.http
        self.item_count = 0
        #: Every request that failed, paired with its exception. ``crawl()``
        #: re-raises the first one, but a crawl that survived twenty failures
        #: should be able to show all twenty.
        self.errors: list[tuple[Request, Exception]] = []

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

    async def start_requests(self) -> AsyncIterator[Request]:
        """The requests a crawl begins with. Defaults to ``start_urls``.

        Override it when a crawl starts with something a URL cannot express — a
        POST, a per-start ``metadata``, or a list read at runtime.
        """
        for url in self.start_urls:
            yield self.request(url)

    @abstractmethod
    def parse(self, response: Response) -> AsyncIterator[Request | Any]:
        """yield ``Request`` to enqueue; yield anything else to emit an item."""

    async def log(self, message: str) -> None:
        """Write a message to the job log. No-op if ``ctx.log`` is unset."""
        if self.ctx.log is not None:
            await self.ctx.log(message)

    async def process_item(self, item: Any) -> None:  # noqa: B027 — optional hook
        """Handle one emitted item. A no-op here; override to persist it.

        The framework stores nothing: an application overrides this to write the
        item to ``self.ctx.sink`` and to keep whatever counters it needs.
        ``item_count`` is the crawl's own and stays accurate either way.
        """

    async def crawl(self) -> int:
        """Run producer/consumer crawling with ``concurrency`` workers.

        Returns the number of items emitted. The first error collected while
        handling requests is re-raised once all workers have finished, so one bad
        page neither kills a worker nor passes silently; see ``errors`` for the
        rest.
        """
        queue: asyncio.Queue[Request] = asyncio.Queue()
        async for req in self.start_requests():
            queue.put_nowait(req)

        async def worker() -> None:
            while True:
                req = await queue.get()
                try:
                    await self._handle(req, queue)
                except Exception as exc:  # noqa: BLE001 — collect, don't kill the worker
                    # Note the request on the exception itself, so the traceback
                    # raised at the end of the crawl still says which page it was.
                    exc.add_note(f'while handling {req.method} {req.url}')
                    logger.warning('crawl.error %s %s %r', req.method, req.url, exc)
                    self.errors.append((req, exc))
                finally:
                    queue.task_done()

        n_workers = read_concurrency(self.ctx.params, self.settings.concurrency)
        workers = [asyncio.create_task(worker()) for _ in range(n_workers)]
        try:
            await queue.join()
        finally:
            # In a finally because a crawl can also end by being cancelled from
            # the outside, and workers left running would outlive the session
            # they hold.
            for w in workers:
                w.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*workers, return_exceptions=True)

        if self.errors:
            raise self.errors[0][1]
        return self.item_count

    async def _handle(self, req: Request, queue: asyncio.Queue[Request]) -> None:
        raw = await self.http.request(req.method, req.url, headers=req.headers, data=req.data)
        response = Response(raw, req)
        callback = req.callback or self.parse
        async for result in callback(response):
            if isinstance(result, Request):
                queue.put_nowait(result)
            else:
                # Counted here rather than in process_item: an override that
                # forgets super() must not silently corrupt the crawl's count.
                self.item_count += 1
                await self.process_item(result)
