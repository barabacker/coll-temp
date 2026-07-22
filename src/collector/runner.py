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
