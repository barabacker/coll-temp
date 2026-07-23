"""Small parsing helpers shared by the source engines.

Engines stay independent of each other but may depend on ``core``; these were
previously duplicated per engine (clean / read_max_pages / parse_price).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r'\s+')
# Leading numeric run: space/nbsp thousands, dot or comma decimal. Stops before
# trailing currency/VAT text (e.g. "280 000,00 руб, НДС не облагается").
_PRICE_HEAD_RE = re.compile(r'[\d\s\xa0.,]+')


def clean(value: str | None) -> str | None:
    """Collapse whitespace to single spaces. None for empty."""
    if value is None:
        return None
    cleaned = _WS_RE.sub(' ', value).strip()
    return cleaned or None


def read_max_pages(params: dict[str, str]) -> int | None:
    """Read ``max_pages`` from job params. None means no limit."""
    raw = params.get('max_pages')
    if raw is None or raw == '':
        return None
    try:
        value = int(raw)
    except (ValueError, TypeError):
        logger.warning('parsing.bad_max_pages value=%s', raw)
        return None
    return value if value > 0 else None


def parse_price(value: str | None) -> float | None:
    """Parse a rouble amount to a float.

    Handles "270 000,00", "1 315 000.00" and "280 000,00 руб, НДС…": takes the
    leading numeric run, drops space/nbsp thousands separators, and treats comma
    or dot as the decimal point.
    """
    if value is None:
        return None
    m = _PRICE_HEAD_RE.match(value)
    if not m:
        return None
    raw = m.group(0).replace('\xa0', '').replace(' ', '').replace(',', '.').strip().rstrip('.')
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning('parsing.bad_price value=%s', value)
        return None
