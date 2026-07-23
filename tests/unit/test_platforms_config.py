"""platforms.toml is the source of truth for the parser registry."""

from __future__ import annotations

import tomllib

import pytest

from collector.core.registry import get_parser, registry
from collector.platforms import CONFIG_PATH, ENGINES, build_parser


def _specs() -> list[dict]:
    return tomllib.loads(CONFIG_PATH.read_text(encoding='utf-8'))['platform']


def test_every_enabled_platform_is_registered():
    enabled = {s['key'] for s in _specs() if s.get('enabled', True)}
    assert enabled == set(registry())


def test_disabled_platforms_are_not_registered():
    disabled = {s['key'] for s in _specs() if not s.get('enabled', True)}
    assert disabled  # the config documents at least one disabled platform
    assert disabled.isdisjoint(registry())


def test_every_platform_uses_a_known_engine():
    assert {s['engine'] for s in _specs()} <= set(ENGINES)


def test_per_site_overrides_are_applied():
    assert get_parser('sistematorg').BASE_URL == 'https://sistematorg.com/tradelist.php'
    assert get_parser('arbbitlot').SKIP_TLS_VERIFY is True
    assert get_parser('meta_invest').EXTRA_CA_CERT == (
        'certs/meta_invest_globalsign_gcc_r3_dv_tls_ca_2020.pem'
    )
    # untouched sites keep the engine defaults
    assert get_parser('centerr').SKIP_TLS_VERIFY is False
    assert get_parser('centerr').EXTRA_CA_CERT is None


def test_generated_class_module_points_at_its_engine():
    # http.factory resolves EXTRA_CA_CERT relative to the class's module file,
    # so a generated class must report its engine package, not collector.platforms.
    cls = get_parser('meta_invest')
    assert cls.__module__ == 'collector.sources.fogsoft.base'
    assert get_parser('nistp').__module__ == 'collector.sources.ruson.base'


def test_build_parser_rejects_unknown_engine():
    with pytest.raises(ValueError, match='unknown engine'):
        build_parser({'key': 'x', 'engine': 'nope', 'domain': 'https://example.com'})
