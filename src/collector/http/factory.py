"""build_http_client — assemble an HttpClient from a parser class, engine-agnostic."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from curl_cffi.requests import AsyncSession

from collector.core.spider import BaseParser
from collector.http.client import HttpClient
from collector.http.hooks import log_request, log_response
from collector.http.middleware import Middleware
from collector.http.tls import ca_bundle_with_extra_cert


def build_http_client(parser_cls: type[BaseParser]) -> HttpClient:
    """Assemble an ``HttpClient`` with the hooks and TLS config a parser declares."""
    middleware = Middleware()
    middleware.request(log_request)
    middleware.response(log_response)
    for hook in parser_cls.RESPONSE_HOOKS:
        middleware.response(hook)

    session_kwargs: dict[str, Any] = {'impersonate': 'chrome'}
    if parser_cls.EXTRA_CA_CERT:
        cert_path = Path(inspect.getfile(parser_cls)).parent / parser_cls.EXTRA_CA_CERT
        session_kwargs['verify'] = ca_bundle_with_extra_cert(str(cert_path))
    elif parser_cls.SKIP_TLS_VERIFY:
        session_kwargs['verify'] = False

    session: AsyncSession[Any] = AsyncSession(**session_kwargs)
    return HttpClient(session, middleware)
