"""Parser for HDL library chips.prt files (FILE_TYPE=LIBRARY_PARTS).

Parses Cadence HDL chips.prt files and extracts:
- Primitive name (part_name)
- Pin definitions (number, name, electrical type)
- Physical design prefix (refdes prefix: R/C/L/U)
- Component class (DISCRETE/IC)

Returns list[ComponentDef], one per primitive block.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from cis2hdl.core.ir.component import ComponentDef, ElectricalType, PinDef

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Regex patterns
# ---------------------------------------------------------------------------

_RE_PRIMITIVE = re.compile(r"^\s*primitive\s+'([^']+)'\s*;\s*$", re.IGNORECASE)
_RE_END_PRIMITIVE = re.compile(r"^\s*end_primitive\s*;\s*$", re.IGNORECASE)
_RE_PIN_DECL = re.compile(r"^\s*'([^']+)'\s*:\s*$")
_RE_PIN_NUMBER = re.compile(r"PIN_NUMBER\s*=\s*'\s*\(\s*(\S+?)\s*\)\s*'\s*;\s*$", re.IGNORECASE)
_RE_PIN_USE = re.compile(r"PINUSE\s*=\s*'([^']+)'\s*;\s*$", re.IGNORECASE)
_RE_PIN_NAME = re.compile(r"PIN_NAME\s*=\s*'([^']+)'\s*;\s*$", re.IGNORECASE)
_RE_BODY_START = re.compile(r"^\s*body\s*;?\s*$", re.IGNORECASE)
_RE_END_BODY = re.compile(r"^\s*end_body\s*;\s*$", re.IGNORECASE)
_RE_PART_NAME = re.compile(r"PART_NAME\s*=\s*'([^']+)'\s*;\s*$", re.IGNORECASE)
_RE_PHYS_DES_PREFIX = re.compile(r"PHYS_DES_PREFIX\s*=\s*'([^']+)'\s*;\s*$", re.IGNORECASE)
_RE_CLASS = re.compile(r"CLASS\s*=\s*'([^']+)'\s*;\s*$", re.IGNORECASE)
_RE_JEDEC_TYPE = re.compile(r"JEDEC_TYPE\s*=\s*'([^']+)'\s*;\s*$", re.IGNORECASE)
_RE_FILE_TYPE = re.compile(r"FILE_TYPE\s*=\s*LIBRARY_PARTS\s*;\s*", re.IGNORECASE)
_RE_PIN_START = re.compile(r"^\s*pin\s*;?\s*$", re.IGNORECASE)
_RE_END_PIN = re.compile(r"^\s*end_pin\s*;\s*$", re.IGNORECASE)

# Electrical type mapping from HDL PINUSE values
_PINUSE_TO_ELECTRICAL: dict[str, ElectricalType] = {
    "INPUT": ElectricalType.INPUT,
    "OUTPUT": ElectricalType.OUTPUT,
    "BIDIR": ElectricalType.BIDIR,
    "BIDIRECTIONAL": ElectricalType.BIDIR,
    "POWER": ElectricalType.POWER,
    "GROUND": ElectricalType.GROUND,
    "UNSPEC": ElectricalType.PASSIVE,
    "PASSIVE": ElectricalType.PASSIVE,
    "TRI_STATE": ElectricalType.TRI_STATE,
    "OPEN_COLLECTOR": ElectricalType.OPEN_COLLECTOR,
    "NC": ElectricalType.NC,
}


class ChipsPrtParser:
    """Parser for chips.prt (FILE_TYPE=LIBRARY_PARTS) files.

    Extracts component definitions including pins, part names,
    refdes prefixes, and component class from Cadence HDL library files.

    Usage:
        parser = ChipsPrtParser()
        components: list[ComponentDef] = parser.parse_file(Path("chips.prt"))
        # OR
        pins: list[PinDef] = parser.parse_pins(Path("chips.prt"))
    """

    def __init__(self, encoding: str = "utf-8") -> None:
        """Initialize the parser.

        Args:
            encoding: File encoding to use when reading chips.prt.
        """
        self._encoding = encoding

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def parse_file(self, path: Path) -> list[ComponentDef]:
        """Parse a chips.prt file and return all ComponentDef entries.

        Each primitive block in the file becomes one ComponentDef.

        Args:
            path: Path to chips.prt file.

        Returns:
            List of ComponentDef objects, one per primitive block.
            Returns empty list on parse failure.
        """
        try:
            content = path.read_text(encoding=self._encoding)
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Failed to read chips.prt %s: %s", path, exc)
            return []

        return self.parse(content, str(path))

    def parse(self, content: str, source_file: str = "") -> list[ComponentDef]:
        """Parse chips.prt content string.

        Args:
            content: Raw text content of chips.prt.
            source_file: Source file path for metadata (optional).

        Returns:
            List of ComponentDef objects.
        """
        if not _RE_FILE_TYPE.search(content):
            logger.warning(
                "chips.prt content does not contain FILE_TYPE=LIBRARY_PARTS header"
            )

        primitives = self._split_primitives(content)
        components: list[ComponentDef] = []

        for primitive_name, primitive_body in primitives:
            pins = self._parse_primitive_pins(primitive_body)
            body_data = self._parse_primitive_body(primitive_body)

            library_id = primitive_name.lower()
            part_name = body_data.get("part_name", primitive_name)
            category = body_data.get("class", "")
            phys_prefix = body_data.get("phys_des_prefix", "")
            jedec_type = body_data.get("jedec_type", "")

            comp = ComponentDef(
                library_id=library_id,
                part_name=part_name,
                category=category,
                phys_des_prefix=phys_prefix,
                pins=pins,
                footprint=jedec_type,  # P0-4: JEDEC_TYPE → footprint
                source_format="HDL",
                source_file=source_file,
            )
            # Store phys_des_prefix in description as auxiliary metadata (backward compat)
            if phys_prefix:
                comp.description = (
                    f"[PHYS_PREFIX={phys_prefix}] {comp.description}".strip()
                )
            components.append(comp)

        return components

    def parse_pins(self, path: Path) -> list[PinDef]:
        """Parse a chips.prt file and return only the pin definitions.

        Convenience method for when only pin data is needed.

        Args:
            path: Path to chips.prt file.

        Returns:
            List of PinDef from the first primitive block found.
            Returns empty list on failure.
        """
        components = self.parse_file(path)
        if components:
            return components[0].pins
        return []

    # ------------------------------------------------------------------
    #  Internal parsing
    # ------------------------------------------------------------------

    def _split_primitives(self, content: str) -> list[tuple[str, str]]:
        """Split content into (primitive_name, primitive_body) pairs."""
        results: list[tuple[str, str]] = []
        lines = content.splitlines()

        current_name: Optional[str] = None
        current_body_lines: list[str] = []
        in_primitive = False

        for line in lines:
            stripped = line.strip()

            if in_primitive:
                if _RE_END_PRIMITIVE.match(stripped):
                    if current_name is not None:
                        body = "\n".join(current_body_lines)
                        results.append((current_name, body))
                    current_name = None
                    current_body_lines = []
                    in_primitive = False
                else:
                    current_body_lines.append(line)
            else:
                m = _RE_PRIMITIVE.match(stripped)
                if m:
                    current_name = m.group(1)
                    current_body_lines = []
                    in_primitive = True

        if in_primitive and current_name is not None:
            logger.warning(
                "Unclosed primitive block '%s' in chips.prt", current_name
            )

        return results

    def _parse_primitive_pins(self, body: str) -> list[PinDef]:
        """Parse pin definitions from a primitive body."""
        pins: list[PinDef] = []
        lines = body.splitlines()

        in_pin_block = False
        current_pin_number: str = ""
        current_pin_name: str = ""
        current_pin_type: ElectricalType = ElectricalType.PASSIVE

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if _RE_PIN_START.match(line):
                in_pin_block = True
                i += 1
                continue

            if in_pin_block:
                if _RE_END_PIN.match(line):
                    in_pin_block = False
                    i += 1
                    continue

                pin_decl = _RE_PIN_DECL.match(line)
                if pin_decl:
                    # Save the previous pin before starting a new one
                    if current_pin_number:
                        pins.append(
                            PinDef(
                                number=current_pin_number,
                                name=current_pin_name,
                                type=current_pin_type,
                            )
                        )
                    # Phase XI T03: the declaration label is the FUNCTIONAL
                    # pin name (e.g. 'RST#', 'TXD1'); PIN_NUMBER below
                    # supplies the numeric id.  Keep the functional name in
                    # PinDef.name so symbol.css offsets and electrical type
                    # can be resolved per pin.
                    current_pin_number = pin_decl.group(1)
                    current_pin_name = pin_decl.group(1)
                    current_pin_type = ElectricalType.PASSIVE
                    i += 1
                    continue

                pin_number_match = _RE_PIN_NUMBER.search(line)
                if pin_number_match:
                    ext_num = pin_number_match.group(1)
                    if ext_num.isdigit():
                        # numeric pin id goes to number; the functional name
                        # (declaration label) is preserved in name
                        current_pin_number = ext_num
                    i += 1
                    continue

                pin_use_match = _RE_PIN_USE.search(line)
                if pin_use_match:
                    raw_type = pin_use_match.group(1).upper().strip()
                    current_pin_type = _PINUSE_TO_ELECTRICAL.get(
                        raw_type, ElectricalType.PASSIVE
                    )
                    i += 1
                    continue

                pin_name_match = _RE_PIN_NAME.search(line)
                if pin_name_match:
                    current_pin_name = pin_name_match.group(1)
                    i += 1
                    continue

            i += 1

        # Save last pin if any
        if current_pin_number:
            pins.append(
                PinDef(
                    number=current_pin_number,
                    name=current_pin_name,
                    type=current_pin_type,
                )
            )

        return pins

    def _parse_primitive_body(self, body: str) -> dict[str, str]:
        """Parse the body section of a primitive."""
        data: dict[str, str] = {}

        in_body = False
        for line in body.splitlines():
            stripped = line.strip()

            if _RE_BODY_START.match(stripped):
                in_body = True
                continue
            if _RE_END_BODY.match(stripped):
                in_body = False
                continue

            if in_body:
                m = _RE_PART_NAME.search(stripped)
                if m:
                    data["part_name"] = m.group(1)
                    continue

                m = _RE_PHYS_DES_PREFIX.search(stripped)
                if m:
                    data["phys_des_prefix"] = m.group(1)
                    continue

                m = _RE_CLASS.search(stripped)
                if m:
                    data["class"] = m.group(1)
                    continue

                # P0-4: Extract JEDEC_TYPE for footprint information.
                # HDL library components (hole, capacitor, resistor, etc.)
                # define JEDEC_TYPE in the body section — e.g.
                # JEDEC_TYPE='hole3_2pad'.  Without this, all HDL
                # components have empty footprint, making fingerprint
                # discrimination impossible.
                m = _RE_JEDEC_TYPE.search(stripped)
                if m:
                    data["jedec_type"] = m.group(1)
                    continue

        return data
