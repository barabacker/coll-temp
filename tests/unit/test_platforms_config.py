"""platforms.toml is the source of truth for the parser registry."""

from __future__ import annotations

import tomllib

import pytest

from collector import get_parser, registry
from tenders.platforms import CONFIG_PATH, ENGINES, build_parser


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
    assert get_parser('arbbitlot').settings.skip_tls_verify is True
    assert get_parser('meta_invest').settings.extra_ca_cert == (
        'certs/meta_invest_globalsign_gcc_r3_dv_tls_ca_2020.pem'
    )
    # untouched sites keep the engine defaults
    assert get_parser('centerr').settings.skip_tls_verify is False
    assert get_parser('centerr').settings.extra_ca_cert is None
    # an override must not drop what the engine declares
    assert get_parser('arbbitlot').settings.response_hooks == (
        get_parser('centerr').settings.response_hooks
    )


def test_generated_class_module_points_at_its_engine():
    # http.factory resolves settings.extra_ca_cert relative to the class's module,
    # so a generated class must report its engine package, not tenders.platforms.
    cls = get_parser('meta_invest')
    assert cls.__module__ == 'tenders.sources.fogsoft.base'
    assert get_parser('nistp').__module__ == 'tenders.sources.ruson.base'


def test_build_parser_rejects_unknown_engine():
    with pytest.raises(ValueError, match='unknown engine'):
        build_parser({'key': 'x', 'engine': 'nope', 'domain': 'https://example.com'})
