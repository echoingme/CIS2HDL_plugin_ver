"""Parser for HDL library symbol.css files.

Parses Cadence HDL symbol.css files containing C/L/A/T/P/M/X graphics
commands and extracts:
- Symbol layout (pin lines, text annotations, attributes)
- Pin name/number annotations with positions
- Attribute key-value pairs with positions
- Bounding box of the symbol

Returns SchematicSymbolDef with structured symbol data.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Data structures
# ---------------------------------------------------------------------------


@dataclass
class SymbolPin:
    """A pin annotation extracted from symbol.css.

    Represents a pin's line and text annotation on the schematic symbol.
    """

    number: str = ""
    name: str = ""
    line_x1: float = 0.0
    line_y1: float = 0.0
    line_x2: float = 0.0
    line_y2: float = 0.0
    text_x: float = 0.0
    text_y: float = 0.0
    #: Electrical type (P1-4): "input" / "output" / "inout" / "power" /
    #: "passive" / "" (unknown).  Filled from the OLB pin properties when
    #: available (port_type), otherwise left empty.
    electrical_type: str = ""
    #: Pin shape (P1-4): "dot" / "line" / "clock" / "short" / "" — from
    #: the OLB pin_shape property; cosmetic, stored for completeness.
    pin_shape: str = ""


@dataclass
class SymbolAttribute:
    """A property annotation from symbol.css (P command)."""

    key: str = ""
    value: str = ""
    x: float = 0.0
    y: float = 0.0


@dataclass
class SymbolGraphic:
    """A graphics command entry (C, L, M, A, T, X commands)."""

    cmd_type: str = ""  # 'C', 'L', 'M', 'A', 'T', 'P', 'X'
    params: list[float] = field(default_factory=list)
    text: str = ""
    text2: str = ""


@dataclass
class SchematicSymbolDef:
    """Structured representation of a symbol.css file.

    Contains all extracted graphics, pin annotations, and attributes
    from a Cadence HDL symbol definition file.
    """

    pins: list[SymbolPin] = field(default_factory=list)
    attributes: list[SymbolAttribute] = field(default_factory=list)
    graphics: list[SymbolGraphic] = field(default_factory=list)

    # Key well-known symbols
    outline: Optional[SymbolAttribute] = None  # CDS_LMAN_SYM_OUTLINE
    location: Optional[SymbolAttribute] = None  # $LOCATION (refdes position)
    value_attr: Optional[SymbolAttribute] = None  # VALUE position

    def bounding_box(self) -> tuple[float, float, float, float]:
        """Compute the bounding box of the symbol.

        Returns:
            (min_x, min_y, max_x, max_y) or (0, 0, 0, 0) if no graphics.
        """
        xs: list[float] = []
        ys: list[float] = []

        for g in self.graphics:
            if g.cmd_type in ("L", "M"):
                # Line or move: x1,y1,x2,y2
                if len(g.params) >= 2:
                    xs.append(g.params[0])
                    ys.append(g.params[1])
                if len(g.params) >= 4:
                    xs.append(g.params[2])
                    ys.append(g.params[3])
            elif g.cmd_type in ("C", "P") and len(g.params) >= 2:
                xs.append(g.params[0])
                ys.append(g.params[1])

        for attr in self.attributes:
            xs.append(attr.x)
            ys.append(attr.y)

        if not xs:
            return (0.0, 0.0, 0.0, 0.0)

        return (min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
#  Regex patterns for symbol.css commands
# ---------------------------------------------------------------------------

# P "KEY" "VALUE" x y [rotation flags...]
# Example: P "$LOCATION" "?" -5 -100 90 0 40 0 0 1 0 ...
_RE_P = re.compile(
    r'^\s*P\s+"([^"]*)"\s+"([^"]*)"\s+(-?[\d.]+)\s+(-?[\d.]+)',
    re.IGNORECASE,
)

# L x1 y1 x2 y2 [flags...]
# Example: L 0 -75 0 -25 -1 0
_RE_L = re.compile(
    r'^\s*L\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)',
    re.IGNORECASE,
)

# C x y "TEXT" [rotation flags...]
# Example: C 0 -75 "1" 0 -60 0 0 32 1 R
_RE_C = re.compile(
    r'^\s*C\s+(-?[\d.]+)\s+(-?[\d.]+)\s+"([^"]*)"',
    re.IGNORECASE,
)

# M x1 y1 x2 y2 [flags...]
_RE_M = re.compile(
    r'^\s*M\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)',
    re.IGNORECASE,
)

# A (arc) — captures parameters loosely
_RE_A = re.compile(
    r'^\s*A\s+',
    re.IGNORECASE,
)

# T (text)
_RE_T = re.compile(
    r'^\s*T\s+"([^"]*)"\s+(-?[\d.]+)\s+(-?[\d.]+)',
    re.IGNORECASE,
)

# X (extended)
_RE_X = re.compile(
    r'^\s*X\s+',
    re.IGNORECASE,
)

# Generic token parser: split on whitespace
_RE_TOKENS = re.compile(r'\S+')


class SymbolCssParser:
    """Parser for symbol.css files (Cadence HDL symbol graphics).

    Extracts structured symbol layout data including pin positions,
    attribute positions, and graphics commands.

    Usage:
        parser = SymbolCssParser()
        symbol = parser.parse_file(Path("symbol.css"))
        print(symbol.bounding_box())
    """

    def __init__(self, encoding: str = "utf-8") -> None:
        """Initialize the parser.

        Args:
            encoding: File encoding to use when reading symbol.css.
        """
        self._encoding = encoding

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def parse_file(self, path: Path) -> SchematicSymbolDef:
        """Parse a symbol.css file.

        Args:
            path: Path to symbol.css file.

        Returns:
            SchematicSymbolDef with parsed symbol data.
            Returns empty SchematicSymbolDef on failure.
        """
        try:
            content = path.read_text(encoding=self._encoding)
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Failed to read symbol.css %s: %s", path, exc)
            return SchematicSymbolDef()

        return self.parse(content, str(path))

    def parse(self, content: str, source_file: str = "") -> SchematicSymbolDef:
        """Parse symbol.css content string.

        Args:
            content: Raw text content of symbol.css.
            source_file: Source file path for metadata (optional).

        Returns:
            SchematicSymbolDef with parsed data.
        """
        result = SchematicSymbolDef()
        lines = content.splitlines()

        raw_commands: list[SymbolGraphic] = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            g = self._parse_line(stripped)
            if g:
                raw_commands.append(g)

        # Post-process: correlate C (pin number) with L (pin line)
        result.graphics = raw_commands
        result.pins = self._correlate_pins(raw_commands)
        result.attributes = self._extract_attributes(raw_commands)

        # Populate well-known attributes
        for attr in result.attributes:
            key_upper = attr.key.upper()
            if key_upper == "CDS_LMAN_SYM_OUTLINE":
                result.outline = attr
            elif key_upper == "$LOCATION":
                result.location = attr
            elif key_upper == "VALUE":
                result.value_attr = attr

        return result

    # ------------------------------------------------------------------
    #  Line-level parsing
    # ------------------------------------------------------------------

    def _parse_line(self, line: str) -> Optional[SymbolGraphic]:
        """Parse a single symbol.css command line.

        Returns:
            SymbolGraphic if the line matches a known command, else None.
        """
        # P command (property/attribute)
        m = _RE_P.match(line)
        if m:
            return SymbolGraphic(
                cmd_type="P",
                params=[float(m.group(3)), float(m.group(4))],
                text=m.group(1),
                text2=m.group(2),
            )

        # C command (circle/text/annotation)
        m = _RE_C.match(line)
        if m:
            return SymbolGraphic(
                cmd_type="C",
                params=[float(m.group(1)), float(m.group(2))],
                text=m.group(3),
            )

        # L command (line)
        m = _RE_L.match(line)
        if m:
            return SymbolGraphic(
                cmd_type="L",
                params=[
                    float(m.group(1)),
                    float(m.group(2)),
                    float(m.group(3)),
                    float(m.group(4)),
                ],
            )

        # M command (move/line)
        m = _RE_M.match(line)
        if m:
            return SymbolGraphic(
                cmd_type="M",
                params=[
                    float(m.group(1)),
                    float(m.group(2)),
                    float(m.group(3)),
                    float(m.group(4)),
                ],
            )

        # T command (text)
        m = _RE_T.match(line)
        if m:
            return SymbolGraphic(
                cmd_type="T",
                params=[float(m.group(2)), float(m.group(3))],
                text=m.group(1),
            )

        # A command (arc) — minimal capture
        if _RE_A.match(line):
            tokens = line.split()
            params: list[float] = []
            for t in tokens[1:]:
                try:
                    params.append(float(t))
                except ValueError:
                    break
            return SymbolGraphic(cmd_type="A", params=params)

        # X command (extended) — minimal capture
        if _RE_X.match(line):
            return SymbolGraphic(cmd_type="X", params=[])

        return None

    # ------------------------------------------------------------------
    #  Post-processing
    # ------------------------------------------------------------------

    def _correlate_pins(
        self, commands: list[SymbolGraphic]
    ) -> list[SymbolPin]:
        """Correlate L (pin line) with nearby C (pin number) commands.

        Strategy: Match C annotations to the closest preceding L line
        by proximity. A tolerance of 50 units is used.
        """
        pins: list[SymbolPin] = []
        pending_lines: list[tuple[int, SymbolGraphic]] = []

        for idx, g in enumerate(commands):
            if g.cmd_type == "L" and len(g.params) >= 4:
                pending_lines.append((idx, g))
            elif g.cmd_type == "C" and g.text and len(g.params) >= 2:
                # Try to match to closest pending line
                cx, cy = g.params[0], g.params[1]

                best_line: Optional[SymbolGraphic] = None
                best_dist = float("inf")
                best_line_idx = -1

                for li, line_g in pending_lines:
                    # Check proximity to line midpoint
                    mx = (line_g.params[0] + line_g.params[2]) / 2.0
                    my = (line_g.params[1] + line_g.params[3]) / 2.0
                    dist = abs(cx - mx) + abs(cy - my)
                    tolerance = 150.0
                    if dist < tolerance and dist < best_dist:
                        best_dist = dist
                        best_line = line_g
                        best_line_idx = li

                if best_line is not None:
                    pin = SymbolPin(
                        number=g.text,
                        line_x1=best_line.params[0],
                        line_y1=best_line.params[1],
                        line_x2=best_line.params[2],
                        line_y2=best_line.params[3],
                        text_x=cx,
                        text_y=cy,
                    )
                    pins.append(pin)
                    # Remove matched line from pending
                    pending_lines = [
                        (li, lg) for li, lg in pending_lines if li != best_line_idx
                    ]
                else:
                    # Unmatched C — still record it as a pin without line coords
                    pin = SymbolPin(
                        number=g.text,
                        text_x=cx,
                        text_y=cy,
                    )
                    pins.append(pin)

        return pins

    def _extract_attributes(
        self, commands: list[SymbolGraphic]
    ) -> list[SymbolAttribute]:
        """Extract P-command attributes."""
        attrs: list[SymbolAttribute] = []
        for g in commands:
            if g.cmd_type == "P" and g.text:
                attr = SymbolAttribute(
                    key=g.text,
                    value=g.text2,
                    x=g.params[0] if len(g.params) >= 1 else 0.0,
                    y=g.params[1] if len(g.params) >= 2 else 0.0,
                )
                attrs.append(attr)
        return attrs


# ---------------------------------------------------------------------------
#  SymbolCssPinParser — pin offset extraction (Phase XI P0-B)
#
#  system_design.md B.2: the pin offset's only authoritative source is the
#  symbol.css ``C x y "pinname"`` command.  LASTPIN coordinates are computed
#  as ``instance body + C-command offset``.  This parser extracts:
#    * pin_name -> (x, y) relative offset
#    * CDS_LMAN_SYM_OUTLINE default value (for body avoidance / csv attr)
# ---------------------------------------------------------------------------


class SymbolCssPinParser:
    """Parse symbol.css pin offsets for LASTPIN/WIRE generation.

    Usage::

        parser = SymbolCssPinParser()
        offsets, outline = parser.parse_file(Path("symbol.css"))
        # offsets == {"1": (0, -75), "2": (0, 50)} for capacitor sym_1
    """

    def __init__(self) -> None:
        self._delegate = SymbolCssParser()

    def parse_file(self, path: Path) -> tuple[dict[str, tuple[int, int]], str]:
        """Parse a symbol.css file.

        Args:
            path: Path to symbol.css.

        Returns:
            (pin_offsets, outline_value): ``pin_offsets`` maps the C-command
            text (pin name or number) to its (x, y) offset; ``outline_value``
            is the ``CDS_LMAN_SYM_OUTLINE`` attribute value or "".
        """
        symbol = self._delegate.parse_file(path)
        return self._from_symbol(symbol)

    def parse(self, content: str, source_file: str = "") -> tuple[dict[str, tuple[int, int]], str]:
        """Parse symbol.css content string.

        Args:
            content: Raw text content of symbol.css.
            source_file: Optional source path for diagnostics.

        Returns:
            (pin_offsets, outline_value).
        """
        symbol = self._delegate.parse(content, source_file)
        return self._from_symbol(symbol)

    @staticmethod
    def _from_symbol(symbol: SchematicSymbolDef) -> tuple[dict[str, tuple[int, int]], str]:
        """Extract pin offsets + outline from a parsed SchematicSymbolDef."""
        offsets: dict[str, tuple[int, int]] = {}
        # Every C command is a pin annotation: C x y "text" [flags...]
        for g in symbol.graphics:
            if g.cmd_type == "C" and g.text and len(g.params) >= 2:
                offsets[g.text] = (int(g.params[0]), int(g.params[1]))
        outline = ""
        for attr in symbol.attributes:
            if attr.key.upper() == "CDS_LMAN_SYM_OUTLINE":
                outline = attr.value
                break
        return offsets, outline
