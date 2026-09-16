"""Domain parsing helpers shared by the source engines.

Trade-specific reading of Russian bankruptcy listings: prices, dates, and what
a status means. The domain-free helpers (``clean``, ``read_max_pages``) come
from the ``collector`` framework and are re-exported here so engine modules keep
one import site.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from collector import clean, read_flag, read_max_pages

__all__ = [
    'clean',
    'is_active_status',
    'parse_datetime',
    'parse_price',
    'pick_status',
    'read_max_pages',
    'read_only_active',
]

logger = logging.getLogger(__name__)

# Leading numeric run: space/nbsp thousands, dot or comma decimal. Stops before
# trailing currency/VAT text (e.g. "280 000,00 руб, НДС не облагается").
_PRICE_HEAD_RE = re.compile(r'[\d\s\xa0.,]+')
# DD.MM.YYYY with an optional HH:MM[:SS]; trailing text (e.g. "(33 дн.)") ignored.
_DATETIME_RE = re.compile(r'(\d{2})\.(\d{2})\.(\d{4})(?:\D+(\d{2}):(\d{2})(?::(\d{2}))?)?')

# Statuses that mean the trade is over. Anything else (including an unknown or
# missing status) counts as live — we never cut a crawl short on doubt.
_FINISHED_MARKERS = (
    'завершен', 'завершён', 'состоял', 'отменен', 'отменён',
    'приостановлен', 'аннулирован', 'признан', 'окончен',
)
# Words that make a short cell recognisable as a status at all.
_STATUS_HINTS = (*_FINISHED_MARKERS, 'объявлен', 'прием', 'приём', 'утверждени')


def is_active_status(status: str | None) -> bool:
    """Is a trade still live? Unknown/empty statuses count as live."""
    if not status:
        return True
    lowered = status.lower()
    return not any(marker in lowered for marker in _FINISHED_MARKERS)


def pick_status(texts: list[str | None]) -> str | None:
    """First short text that reads like a trade status (listing status cell)."""
    for text in texts:
        cleaned = clean(text)
        if cleaned and len(cleaned) < 40 and any(h in cleaned.lower() for h in _STATUS_HINTS):
            return cleaned
    return None


def read_only_active(params: dict[str, str]) -> bool:
    """Whether to dive only into live trades (default: on).

    When on, finished trades are skipped from the (expensive) detail dive, but
    the listing is still paged through in full — this flag does not stop
    pagination. Set ``only_active=0`` to also collect finished/archive lots.
    """
    return read_flag(params, 'only_active', True)


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


def parse_datetime(value: str | None) -> datetime | None:
    """Parse a "DD.MM.YYYY[ HH:MM[:SS]]" string to a datetime, else None."""
    if not value:
        return None
    m = _DATETIME_RE.search(value)
    if not m:
        return None
    day, month, year, hour, minute, second = m.groups()
    try:
        return datetime(
            int(year), int(month), int(day),
            int(hour or 0), int(minute or 0), int(second or 0),
        )
    except ValueError:
        return None
