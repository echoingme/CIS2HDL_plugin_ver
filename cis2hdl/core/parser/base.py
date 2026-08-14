from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from ..exceptions import CIS2HDLParseError

if TYPE_CHECKING:
    from ..ir.design import DesignIR

logger = logging.getLogger(__name__)


class ParserBase(ABC):
    """Abstract base for all format parsers.

    Each subclass declares FORMAT_NAME and FILE_EXTENSIONS.
    Call register() to make it available in the global ParserRegistry.
    """

    FORMAT_NAME: str = ""
    FILE_EXTENSIONS: list[str] = []

    # ------------------------------------------------------------------
    #  Core interface
    # ------------------------------------------------------------------

    @abstractmethod
    def parse(self, path: Path) -> "DesignIR":
        """Parse a file and return a unified DesignIR.

        Args:
            path: Absolute or relative path to the input file.

        Returns:
            A fully populated DesignIR instance.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the file content cannot be parsed.
        """
        ...

    # ------------------------------------------------------------------
    #  Introspection
    # ------------------------------------------------------------------

    @classmethod
    def can_handle(cls, path: Path) -> bool:
        """Check whether this parser can handle the given file."""
        suffix = path.suffix.lower()
        return suffix in cls.FILE_EXTENSIONS

    @classmethod
    def supported_extensions(cls) -> list[str]:
        """Return the list of supported file extensions."""
        return cls.FILE_EXTENSIONS[:]


class ParserRegistry:
    """Global registry for format parsers.

    Usage::

        EDIFParser.register()
        parser = ParserRegistry.get_for_file(Path("design.edf"))
        ir = parser.parse(Path("design.edf"))
    """

    _parsers: dict[str, "ParserBase"] = {}

    # ------------------------------------------------------------------
    #  Registration
    # ------------------------------------------------------------------

    @classmethod
    def register(cls, parser: "ParserBase") -> None:
        """Register a parser instance."""
        if parser.FORMAT_NAME in cls._parsers:
            logger.warning(
                "Parser %s already registered; overwriting.", parser.FORMAT_NAME
            )
        cls._parsers[parser.FORMAT_NAME] = parser
        logger.info("Registered parser: %s (%s)", parser.FORMAT_NAME, parser.FILE_EXTENSIONS)

    @classmethod
    def unregister(cls, format_name: str) -> None:
        """Remove a parser from the registry."""
        cls._parsers.pop(format_name, None)

    # ------------------------------------------------------------------
    #  Lookup
    # ------------------------------------------------------------------

    @classmethod
    def get_for_file(cls, path: Path) -> "ParserBase":
        """Find a parser that can handle the given file.

        Raises:
            CIS2HDLParseError: If no registered parser matches the file extension.
        """
        suffix = path.suffix.lower()
        for parser in cls._parsers.values():
            if suffix in parser.FILE_EXTENSIONS:
                return parser
        raise CIS2HDLParseError(
            f"No parser registered for extension '{suffix}'. "
            f"Available: {cls.list_formats()}",
            file_path=str(path),
        )

    @classmethod
    def get_by_format(cls, format_name: str) -> "ParserBase":
        """Look up a parser by its FORMAT_NAME.

        Raises:
            CIS2HDLParseError: If no parser is registered for the given format.
        """
        try:
            return cls._parsers[format_name]
        except KeyError:
            raise CIS2HDLParseError(
                f"No parser registered for format '{format_name}'. "
                f"Available: {cls.list_formats()}"
            ) from None

    # ------------------------------------------------------------------
    #  Queries
    # ------------------------------------------------------------------

    @classmethod
    def list_formats(cls) -> list[str]:
        """Return the list of all registered format names."""
        return list(cls._parsers.keys())

    @classmethod
    def list_extensions(cls) -> dict[str, list[str]]:
        """Return a mapping of format name → supported extensions."""
        return {fmt: p.FILE_EXTENSIONS for fmt, p in cls._parsers.items()}

    @classmethod
    def clear(cls) -> None:
        """Remove all registered parsers (useful for testing)."""
        cls._parsers.clear()
