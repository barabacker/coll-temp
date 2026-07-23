"""Build and register every parser class from ``platforms.toml``.

The platform list is data, not code: one TOML entry per site (key, engine,
domain, plus optional per-site quirks). Importing this module reads the config
and registers a parser class per enabled entry — replacing the hand-written
``platforms.py`` that used to sit in each engine package.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from collector.core.registry import register_parser
from collector.core.spider import BaseParser
from collector.sources.btorg.base import TenderBtorg
from collector.sources.fogsoft.base import TenderFogsoft
from collector.sources.kendo.base import TenderKendo
from collector.sources.ruson.base import TenderRuson

CONFIG_PATH = Path(__file__).parent / 'platforms.toml'

ENGINES: dict[str, type[BaseParser]] = {
    'fogsoft': TenderFogsoft,
    'kendo': TenderKendo,
    'btorg': TenderBtorg,
    'ruson': TenderRuson,
}

# TOML field -> parser class attribute. Absent fields keep the engine default.
_OPTIONAL_ATTRS = {
    'listing_path': 'LISTING_PATH',
    'extra_ca_cert': 'EXTRA_CA_CERT',
    'skip_tls_verify': 'SKIP_TLS_VERIFY',
}


def _class_name(key: str) -> str:
    """``meta_invest`` -> ``MetaInvestParser`` (readable in logs/tracebacks)."""
    return ''.join(part.capitalize() for part in key.split('_')) + 'Parser'


def build_parser(spec: dict[str, Any]) -> type[BaseParser]:
    """Create (but do not register) a parser class from one config entry."""
    key = spec['key']
    engine = spec['engine']
    try:
        base = ENGINES[engine]
    except KeyError:
        raise ValueError(f"platform '{key}': unknown engine '{engine}'") from None

    attrs: dict[str, Any] = {'name': key, 'DOMAIN': spec['domain']}
    for field, attr in _OPTIONAL_ATTRS.items():
        if field in spec:
            attrs[attr] = spec[field]

    title = spec.get('title', key)
    domain = spec['domain']
    attrs['__doc__'] = f'{title} — {domain}.'
    # ``http.factory`` resolves EXTRA_CA_CERT relative to the class's module
    # file, so point the generated class at its engine package (where certs/
    # lives) rather than at this module.
    attrs['__module__'] = base.__module__

    return type(_class_name(key), (base,), attrs)


def load_platforms(config_path: Path | None = None) -> dict[str, type[BaseParser]]:
    """Read the config and register a parser per enabled platform."""
    path = config_path or CONFIG_PATH
    specs = tomllib.loads(path.read_text(encoding='utf-8'))['platform']
    built: dict[str, type[BaseParser]] = {}
    for spec in specs:
        if not spec.get('enabled', True):
            continue
        cls = build_parser(spec)
        register_parser(spec['key'])(cls)
        built[spec['key']] = cls
    return built


PLATFORMS = load_platforms()
