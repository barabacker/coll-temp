"""Concrete rus-on platforms."""

from __future__ import annotations

from collector.core.registry import register_parser
from collector.sources.ruson.base import TenderRuson


@register_parser('nistp')
class NistpParser(TenderRuson):
    """Новые информационные сервисы — nistp.ru."""

    name = 'nistp'
    DOMAIN = 'https://nistp.ru'


@register_parser('el_torg')
class ElTorgParser(TenderRuson):
    """Электронные торги — el-torg.com."""

    name = 'el_torg'
    DOMAIN = 'https://el-torg.com'


@register_parser('rus_on')
class RusOnParser(TenderRuson):
    """РОССИЯ ОнЛайн — rus-on.ru."""

    name = 'rus_on'
    DOMAIN = 'https://rus-on.ru'


@register_parser('sistematorg')
class SistematorgParser(TenderRuson):
    """Объединённые системы торгов — sistematorg.com."""

    name = 'sistematorg'
    DOMAIN = 'https://sistematorg.com'
    LISTING_PATH = 'tradelist.php'


@register_parser('promkonsalt')
class PromkonsaltParser(TenderRuson):
    """Промконсалт — promkonsalt.ru."""

    name = 'promkonsalt'
    DOMAIN = 'https://promkonsalt.ru'
    LISTING_PATH = 'tradelist.php'
