"""Concrete btorg/edoc-ETP platforms."""

from __future__ import annotations

from collector.core.registry import register_parser
from collector.sources.btorg.base import TenderBtorg


@register_parser('atctrade')
class AtcTradeParser(TenderBtorg):
    """Аукционный тендерный центр — atctrade.ru."""

    name = 'atctrade'
    DOMAIN = 'https://atctrade.ru'


@register_parser('ausib')
class AusibParser(TenderBtorg):
    """Аукционы Сибири — ausib.ru."""

    name = 'ausib'
    DOMAIN = 'https://ausib.ru'


@register_parser('etp_profit')
class EtpProfitParser(TenderBtorg):
    """ЭТП Профит — etp-profit.ru."""

    name = 'etp_profit'
    DOMAIN = 'https://etp-profit.ru'


@register_parser('aukcioncenter')
class AukcionCenterParser(TenderBtorg):
    """Аукционный центр — aukcioncenter.ru."""

    name = 'aukcioncenter'
    DOMAIN = 'https://aukcioncenter.ru'


@register_parser('regtorg')
class RegTorgParser(TenderBtorg):
    """Региональная торговая площадка — regtorg.com."""

    name = 'regtorg'
    DOMAIN = 'https://regtorg.com'


@register_parser('ptp_center')
class PtpCenterParser(TenderBtorg):
    """ПТП-Центр — ptp-center.ru."""

    name = 'ptp_center'
    DOMAIN = 'https://ptp-center.ru'
