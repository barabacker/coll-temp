"""ParserContext — parser execution context."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collector.http.client import HttpClient
    from collector.sink import LotSink


@dataclass(slots=True)
class ParserContext:
    """Parser execution context: HTTP client, params, optional lot sink and log."""

    http: HttpClient
    params: dict[str, str] = field(default_factory=dict)
    lot_sink: LotSink | None = None
    log: Callable[[str], Awaitable[None]] | None = None
    job_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
