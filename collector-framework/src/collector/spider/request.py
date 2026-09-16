"""Request — describes an HTTP request that ``crawl()`` must perform."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collector.spider.response import Response


@dataclass(slots=True)
class Request:
    """Describes an HTTP request that crawl() must perform.

    ``callback`` receives the :class:`~collector.spider.response.Response` and
    yields further requests or items; ``None`` means the parser's ``parse()``.
    ``metadata`` is carried over to the response untouched.
    """

    url: str
    method: str = 'GET'
    callback: Callable[[Response], AsyncIterator[Request | Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] | None = None
    data: dict[str, str] | str | None = None
