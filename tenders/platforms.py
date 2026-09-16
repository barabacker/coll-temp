"""Build and register every parser class from ``platforms.toml``.

The platform list is data, not code: one TOML entry per site (key, engine,
domain, plus optional per-site quirks). Importing this module reads the config
and registers a parser class per enabled entry — replacing the hand-written
``platforms.py`` that used to sit in each engine package.
"""

from __future__ import annotations

import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

from collector import BaseParser

from tenders.registry import register_parser
from tenders.sources.btorg.base import TenderBtorg
from tenders.sources.fogsoft.base import TenderFogsoft
from tenders.sources.kendo.base import TenderKendo
from tenders.sources.ruson.base import TenderRuson

CONFIG_PATH = Path(__file__).parent / 'platforms.toml'

ENGINES: dict[str, type[BaseParser]] = {
    'fogsoft': TenderFogsoft,
    'kendo': TenderKendo,
    'btorg': TenderBtorg,
    'ruson': TenderRuson,
}

# TOML field -> parser class attribute. Absent fields keep the engine default.
_OPTIONAL_ATTRS = {'listing_path': 'LISTING_PATH'}
# TOML field -> Settings field. Absent fields keep the engine's setting.
_OPTIONAL_SETTINGS = ('extra_ca_cert', 'skip_tls_verify')


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

    overrides = {field: spec[field] for field in _OPTIONAL_SETTINGS if field in spec}
    if overrides:
        attrs['settings'] = replace(base.settings, **overrides)

    title = spec.get('title', key)
    domain = spec['domain']
    attrs['__doc__'] = f'{title} — {domain}.'
    # ``http.factory`` resolves ``settings.extra_ca_cert`` relative to the
    # class's module file, so point the generated class at its engine package
    # (where certs/ lives) rather than at this module.
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
