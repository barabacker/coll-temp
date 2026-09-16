"""Bridge between the async parser core and synchronous callers.

A crawl is asynchronous, but the thing that starts it usually is not — a CLI, a
cron entry, an RQ task. ``run_parser`` builds the HTTP client the parser
declares, runs ``crawl()`` under ``asyncio.run`` and hands back the finished
parser instance, so any counter it kept is available to the caller.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from collector.http.factory import build_http_client
from collector.spider import BaseParser, ParserContext

logger = logging.getLogger(__name__)


async def crawl(
    parser_cls: type[BaseParser],
    *,
    params: dict[str, str] | None = None,
    sink: Any | None = None,
    log: Callable[[str], Awaitable[None]] | None = None,
) -> BaseParser:
    """Run a parser to completion and return the parser instance.

    The async entry point: use it when the caller already runs an event loop.
    """
    http = build_http_client(parser_cls)
    async with http:
        ctx = ParserContext(http=http, params=params or {}, sink=sink, log=log)
        parser = parser_cls(ctx)
        await parser.crawl()
    return parser


def run_parser(
    parser_cls: type[BaseParser],
    *,
    params: dict[str, str] | None = None,
    sink: Any | None = None,
    log: Callable[[str], Awaitable[None]] | None = None,
) -> BaseParser:
    """Run a parser to completion synchronously; return the parser instance.

    ``sink`` is whatever the parser's ``process_item()`` expects — the framework
    only passes it through. ``log`` defaults to an async wrapper around this
    module's logger.
    """
    if log is None:

        async def log(message: str) -> None:  # noqa: A001 — same name by design
            logger.info('[%s] %s', parser_cls.name, message)

    return asyncio.run(crawl(parser_cls, params=params, sink=sink, log=log))
