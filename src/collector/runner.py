"""Bridge between the async parser core and the synchronous RQ task.

Builds a curl_cffi session tailored to the parser class (TLS quirks, anti-bot
hook), runs ``crawl()`` under ``asyncio.run``, and returns the counts. Ported
from the old collector's ``build_http_client`` / CLI wiring, minus the
SQLAlchemy job machinery.
"""

from __future__ import annotations

import functools
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import certifi
from curl_cffi.requests import AsyncSession

from collector.core.spider import BaseParser, ParserContext
from collector.sources.fogsoft.base import TenderFogsoft
from collector.http.client import HttpClient
from collector.sources.fogsoft.inprotect import solve_inprotect
from collector.http.hooks import log_request, log_response
from collector.http.middleware import Middleware
from collector.core.storage.sink import LotSink

logger = logging.getLogger(__name__)

_FOGSOFT_DIR = Path(__file__).parent / 'sources' / 'fogsoft'


@dataclass(slots=True)
class CrawlResult:
    total: int
    new: int
    changed: int


@functools.cache
def _ca_bundle_with_extra_cert(extra_cert_relpath: str) -> str:
    """Build (and disk-cache) a certifi bundle plus a site's extra certificate.

    Some sites omit an intermediate certificate from their TLS chain;
    curl/BoringSSL, unlike browsers, will not fetch it, so we append it here.
    """
    extra_cert_path = _FOGSOFT_DIR / extra_cert_relpath
    combined = Path(certifi.where()).read_text(encoding='utf-8')
    combined += '\n' + extra_cert_path.read_text(encoding='utf-8')
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.pem', prefix='ca-bundle-', delete=False, encoding='utf-8'
    )
    tmp.write(combined)
    tmp.close()
    return tmp.name


def build_http_client(parser_cls: type[BaseParser]) -> HttpClient:
    """Assemble an ``HttpClient`` with the hooks and TLS config for a parser."""
    middleware = Middleware()
    middleware.request(log_request)
    middleware.response(log_response)
    if issubclass(parser_cls, TenderFogsoft):
        middleware.response(solve_inprotect)

    session_kwargs: dict[str, Any] = {'impersonate': 'chrome'}
    extra_ca_cert = getattr(parser_cls, 'EXTRA_CA_CERT', None)
    if extra_ca_cert:
        session_kwargs['verify'] = _ca_bundle_with_extra_cert(extra_ca_cert)
    elif getattr(parser_cls, 'SKIP_TLS_VERIFY', False):
        session_kwargs['verify'] = False

    session: AsyncSession[Any] = AsyncSession(**session_kwargs)
    return HttpClient(session, middleware)


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
    import asyncio

    async def _log(message: str) -> None:
        logger.info('[%s] %s', parser_cls.name, message)

    return asyncio.run(_crawl(parser_cls, params or {}, sink, _log))
