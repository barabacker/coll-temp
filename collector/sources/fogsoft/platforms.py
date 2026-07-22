"""Concrete iTender (Fogsoft) platforms."""

from __future__ import annotations

from collector.sources.fogsoft.base import TenderFogsoft
from collector.core.registry import register_parser


@register_parser('centerr')
class CenterrParser(TenderFogsoft):
    """Центр реализации — bankrupt.centerr.ru."""

    name = 'centerr'
    DOMAIN = 'https://bankrupt.centerr.ru'


# TODO(utender): disabled — pagination does not advance, the job re-downloads
# page 1 (see the old "utender-pagination-debt" note). Re-enable after the fix.
# @register_parser("utender")
# class UTenderParser(TenderFogsoft):
#     """uTender — utender.ru."""
#
#     name = "utender"
#     DOMAIN = "http://utender.ru"


@register_parser('alfalot')
class AlfalotParser(TenderFogsoft):
    """АЛЬФАЛОТ — bankrupt.alfalot.ru."""

    name = 'alfalot'
    DOMAIN = 'https://bankrupt.alfalot.ru'


@register_parser('etpu_bankrupt')
class EtpuBankruptParser(TenderFogsoft):
    """Уральская электронная торговая площадка — etpu.ru."""

    name = 'etpu_bankrupt'
    DOMAIN = 'https://bankrupt.etpu.ru'


@register_parser('bep')
class BepParser(TenderFogsoft):
    """Балтийская электронная площадка — bepspb.ru."""

    name = 'bep'
    DOMAIN = 'https://bankruptcy.bepspb.ru'


@register_parser('arbbitlot')
class ArbBitLotParser(TenderFogsoft):
    """АРБбитЛот — torgi.arbbitlot.ru.

    The site's TLS certificate is expired on its side (verified independently
    of our code via openssl s_client / system curl) — no CA bundle fixes that.
    We disable certificate verification entirely until the site renews it.
    """

    name = 'arbbitlot'
    DOMAIN = 'https://torgi.arbbitlot.ru'
    SKIP_TLS_VERIFY = True


@register_parser('arbitat')
class ArbitatParser(TenderFogsoft):
    """Арбитат — arbitat.ru."""

    name = 'arbitat'
    DOMAIN = 'http://arbitat.ru'


@register_parser('utp_lot')
class UtpLotParser(TenderFogsoft):
    """Объединённая торговая площадка — utpl.ru."""

    name = 'utp_lot'
    DOMAIN = 'https://bankrupt.utpl.ru'


@register_parser('tender_one')
class TenderOneParser(TenderFogsoft):
    """Tender Technologies — tender.one."""

    name = 'tender_one'
    DOMAIN = 'https://bankrupt.tender.one'


@register_parser('etpugra')
class EtpUgraParser(TenderFogsoft):
    """ЭТП Югра — etpugra.ru."""

    name = 'etpugra'
    DOMAIN = 'https://etpugra.ru'


@register_parser('tendergarant')
class TenderGarantParser(TenderFogsoft):
    """ТЕНДЕР ГАРАНТ — tendergarant.com."""

    name = 'tendergarant'
    DOMAIN = 'https://tendergarant.com'


@register_parser('yuzhnyy_etp')
class YuzhnyEtpParser(TenderFogsoft):
    """ЮЭТП — torgibankrot.ru."""

    name = 'yuzhnyy_etp'
    DOMAIN = 'https://torgibankrot.ru'


@register_parser('meta_invest')
class MetaInvestParser(TenderFogsoft):
    """МЕТА-ИНВЕСТ — meta-invest.ru.

    The server does not send the intermediate certificate of its TLS chain —
    we supply it explicitly (see certs/meta_invest_*.pem).
    """

    name = 'meta_invest'
    DOMAIN = 'https://meta-invest.ru'
    EXTRA_CA_CERT = 'certs/meta_invest_globalsign_gcc_r3_dv_tls_ca_2020.pem'


# @register_parser("property_trade")
# class PropertyTradeParser(TenderFogsoft):
#     """Property Trade — propertytrade.ru."""
#
#     name = "property_trade"
#     DOMAIN = "https://propertytrade.ru"


@register_parser('gloria_service')
class GloriaServiceParser(TenderFogsoft):
    """ЭТП Регион (GloriaService) — gloriaservice.ru."""

    name = 'gloria_service'
    DOMAIN = 'https://gloriaservice.ru'


@register_parser('zakazrf')
class ZakazRfParser(TenderFogsoft):
    """ЭТП Заказ РФ — bankrot.zakazrf.ru."""

    name = 'zakazrf'
    DOMAIN = 'http://bankrot.zakazrf.ru'


@register_parser('etb')
class EtbParser(TenderFogsoft):
    """ЕЭТП / ets24.ru."""

    name = 'etb'
    DOMAIN = 'http://bankrupt.ets24.ru'
