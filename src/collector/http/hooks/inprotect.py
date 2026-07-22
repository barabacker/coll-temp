"""Response hook: transparently solve the inprotect challenge (Fogsoft sites)."""

from __future__ import annotations

import logging
from typing import Any

from collector.fogsoft.inprotect import build_cookies, looks_like_challenge

logger = logging.getLogger(__name__)


async def solve_inprotect(response: Any, *, session: Any, retry: Any) -> Any:
    """If the response is an inprotect challenge, set the pass cookies and retry."""
    if not looks_like_challenge(response.text, response.status_code):
        return response

    cookies = build_cookies(response.text)
    if not cookies:
        logger.warning(
            'inprotect.unsolvable url=%s status=%s',
            getattr(response, 'url', '?'),
            response.status_code,
        )
        return response

    for name, value in cookies.items():
        session.cookies.set(name, value)
    logger.info(
        'inprotect.solved url=%s cookies=%s', getattr(response, 'url', '?'), sorted(cookies)
    )

    return await retry()
