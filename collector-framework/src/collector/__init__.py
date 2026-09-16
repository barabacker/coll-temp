"""collector — a tiny async scraping framework.

Write a parser as a Spider: subclass :class:`BaseParser`, set ``start_urls``,
and implement ``parse()`` as an async generator that yields ``Request`` objects
to follow and items to emit. ``run_parser`` assembles the HTTP client the parser
declares (impersonation, TLS quirks, response hooks) and runs the crawl.

The framework stores nothing and knows no item schema: override
``process_item()`` to do something with what a parser emits.
"""

from __future__ import annotations

from collector.http import (
    HttpClient,
    Middleware,
    RequestHook,
    ResponseHook,
    build_http_client,
    ca_bundle_with_extra_cert,
)
from collector.params import read_concurrency, read_flag, read_max_pages
from collector.registry import (
    ParserNotFound,
    get_parser,
    register_parser,
    registry,
    unregister_parser,
)
from collector.runner import crawl, run_parser
from collector.spider import BaseParser, ParserContext, Request, Response
from collector.text import clean

__version__ = '0.1.0'

__all__ = [
    'BaseParser',
    'HttpClient',
    'Middleware',
    'ParserContext',
    'ParserNotFound',
    'Request',
    'RequestHook',
    'Response',
    'ResponseHook',
    '__version__',
    'build_http_client',
    'ca_bundle_with_extra_cert',
    'clean',
    'crawl',
    'get_parser',
    'read_concurrency',
    'read_flag',
    'read_max_pages',
    'register_parser',
    'registry',
    'run_parser',
    'unregister_parser',
]
