"""Concrete Kendo-ETP platforms."""

from __future__ import annotations

from collector.core.registry import register_parser
from collector.sources.kendo.base import TenderKendo


@register_parser('trade_alliance')
class TradeAllianceParser(TenderKendo):
    """Альянс Трэйд — trade-alliance.ru."""

    name = 'trade_alliance'
    DOMAIN = 'https://trade-alliance.ru'


@register_parser('seltim')
class SeltimParser(TenderKendo):
    """Селтим — bankrupt.seltim.ru."""

    name = 'seltim'
    DOMAIN = 'https://bankrupt.seltim.ru'


@register_parser('electro_torgi')
class ElectroTorgiParser(TenderKendo):
    """Электро-Торги — bankrotstvo.electro-torgi.ru."""

    name = 'electro_torgi'
    DOMAIN = 'https://bankrotstvo.electro-torgi.ru'


@register_parser('torgi82')
class Torgi82Parser(TenderKendo):
    """Торги82 — lot.torgi82.ru."""

    name = 'torgi82'
    DOMAIN = 'https://lot.torgi82.ru'


@register_parser('vetp')
class VetpParser(TenderKendo):
    """ВЭТП — банкрот.вэтп.рф (IDN)."""

    name = 'vetp'
    DOMAIN = 'https://банкрот.вэтп.рф'
