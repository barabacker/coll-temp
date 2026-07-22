"""Parser registry: register_parser / get_parser, keyed by parser name.

Resolving which parser a Platform uses lives on the Django side
(platforms.resolver) — this package must not know about the ORM.
"""

from __future__ import annotations

from collections.abc import Callable

from collector.base import BaseParser

_REGISTRY: dict[str, type[BaseParser]] = {}


class ParserNotFound(LookupError):
    pass


def register_parser(name: str) -> Callable[[type[BaseParser]], type[BaseParser]]:
    """Register a parser class under ``name``.

    Raises ``ValueError`` if the key is already taken — guards against an
    accidental double registration of the same name by two classes.
    """

    def decorator(cls: type[BaseParser]) -> type[BaseParser]:
        if name in _REGISTRY:
            raise ValueError(f"Parser '{name}' already registered")
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_parser(name: str) -> type[BaseParser]:
    """Return a parser class by key. Raises ParserNotFound if absent."""
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ParserNotFound(name) from None


def registry() -> dict[str, type[BaseParser]]:
    """Return a copy of the registry ``{key: parser_cls}``."""
    return dict(_REGISTRY)
