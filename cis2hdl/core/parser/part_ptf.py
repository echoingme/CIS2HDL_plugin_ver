"""Parser for HDL library part.ptf files (FILE_TYPE=MULTI_PHYS_TABLE).

Parses Cadence HDL part.ptf files and extracts:
- Part name
- Multi-physical table rows with columns: PACKAGE_TYPE, VALUE,
  DESCRIPTION, JEDEC_TYPE, SN_NUM, BOM_SEQ, etc.

Returns list[PartProperty] with structured property data.
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
class PartProperty:
    """A single row from the part.ptf MULTI_PHYS_TABLE.

    Represents one physical variant of a component with its attributes.
    """

    package_type: str = ""
    value: str = ""
    description: str = ""
    jedec_type: str = ""
    sn_num: str = ""
    bom_seq: str = ""
    part_name: str = ""

    # Additional columns beyond the standard set
    extras: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        """Convert to a flat dictionary of all properties."""
        result: dict[str, str] = {
            "PACKAGE_TYPE": self.package_type,
            "VALUE": self.value,
            "DESCRIPTION": self.description,
            "JEDEC_TYPE": self.jedec_type,
            "SN_NUM": self.sn_num,
            "BOM_SEQ": self.bom_seq,
            "PART_NAME": self.part_name,
        }
        result.update(self.extras)
        return result


# ---------------------------------------------------------------------------
#  Regex patterns
# ---------------------------------------------------------------------------

_RE_FILE_TYPE = re.compile(
    r"FILE_TYPE\s*=\s*MULTI_PHYS_TABLE\s*;\s*", re.IGNORECASE
)
_RE_PART = re.compile(r"^\s*PART\s+'([^']+)'\s*$", re.IGNORECASE)
# Table header: :COL1 | COL2 | COL3 | ... ;
_RE_HEADER = re.compile(r"^\s*:\s*(.+?)\s*;\s*$")
# Table data: 'VAL1' | 'VAL2' | ... ;
_RE_DATA_ROW = re.compile(r"^\s*'([^']*)'\s*\|", re.IGNORECASE)


class PartPtfParser:
    """Parser for part.ptf (FILE_TYPE=MULTI_PHYS_TABLE) files.

    Extracts component property rows from Cadence HDL part table files.

    Usage:
        parser = PartPtfParser()
        properties: list[PartProperty] = parser.parse_file(Path("part.ptf"))
        for p in properties:
            print(p.package_type, p.value, p.bom_seq)
    """

    # Standard column names and their property mappings
    COLUMN_MAP: dict[str, str] = {
        "PACKAGE_TYPE": "package_type",
        "VALUE": "value",
        "DESCRIPTION": "description",
        "JEDEC_TYPE": "jedec_type",
        "SN_NUM": "sn_num",
        "BOM_SEQ": "bom_seq",
        "PART_NAME": "part_name",
    }

    def __init__(self, encoding: str = "utf-8") -> None:
        """Initialize the parser.

        Args:
            encoding: File encoding to use when reading part.ptf.
        """
        self._encoding = encoding

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def parse_file(self, path: Path) -> list[PartProperty]:
        """Parse a part.ptf file.

        Args:
            path: Path to part.ptf file.

        Returns:
            List of PartProperty objects, one per table row.
            Returns empty list on failure.
        """
        try:
            content = path.read_text(encoding=self._encoding)
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="gbk")
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning("Failed to read part.ptf %s: %s", path, exc)
                return []
        except OSError as exc:
            logger.warning("Failed to read part.ptf %s: %s", path, exc)
            return []

        return self.parse(content)

    def parse(self, content: str) -> list[PartProperty]:
        """Parse part.ptf content string.

        Args:
            content: Raw text content of part.ptf.

        Returns:
            List of PartProperty objects.
        """
        if not _RE_FILE_TYPE.search(content):
            logger.warning(
                "part.ptf content does not contain FILE_TYPE=MULTI_PHYS_TABLE header"
            )

        results: list[PartProperty] = []
        current_part_name: str = ""
        current_columns: list[str] = []

        lines = content.splitlines()

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # PART 'NAME' line
            part_match = _RE_PART.match(stripped)
            if part_match:
                current_part_name = part_match.group(1)
                continue

            # : Header line
            header_match = _RE_HEADER.match(stripped)
            if header_match:
                current_columns = self._parse_header(header_match.group(1))
                # Filter out empty column names
                current_columns = [c.strip() for c in current_columns if c.strip()]
                continue

            # Data row: starts with a quoted string followed by |
            if stripped.startswith("'") and "|" in stripped and current_columns:
                row = self._parse_data_row(stripped, current_columns)
                if row.part_name == "":
                    row.part_name = current_part_name
                # Only add if we got meaningful data
                if any(
                    [
                        row.package_type,
                        row.value,
                        row.description,
                        row.jedec_type,
                        row.sn_num,
                        row.bom_seq,
                    ]
                ):
                    results.append(row)

        return results

    # ------------------------------------------------------------------
    #  Internal parsing
    # ------------------------------------------------------------------

    def _parse_header(self, header_line: str) -> list[str]:
        """Parse the column header line.

        Format: 'PACKAGE_TYPE | VALUE | DESCRIPTION | ...'

        Args:
            header_line: The header text between ':' and ';'.

        Returns:
            List of column name strings.
        """
        columns: list[str] = []
        # Split on '|' boundaries (verbatim pipe)
        parts = header_line.split("|")
        for part in parts:
            col = part.strip()
            # Remove surrounding quotes if present
            if col.startswith("'") and col.endswith("'"):
                col = col[1:-1]
            columns.append(col)
        return columns

    def _parse_data_row(
        self, row_text: str, columns: list[str]
    ) -> PartProperty:
        """Parse a single data row using the column positions.

        Args:
            row_text: The data row text (e.g., "'C0402' | '100NF' | ...").
            columns: Column names from the header.

        Returns:
            PartProperty with values mapped to standard fields.
        """
        # Strip trailing semicolon
        row_text = row_text.rstrip().rstrip(";").rstrip()

        # Extract values between pipe separators
        values = self._split_row_values(row_text)

        prop = PartProperty()

        for i, col_name in enumerate(columns):
            if i >= len(values):
                break

            val = values[i]
            attr_name = self.COLUMN_MAP.get(col_name.upper(), "")

            if attr_name and hasattr(prop, attr_name):
                setattr(prop, attr_name, val)
            else:
                prop.extras[col_name] = val

        return prop

    def _split_row_values(self, row_text: str) -> list[str]:
        """Split a pipe-delimited or equals-delimited row into values.

        Handles two formats:
          1. Pipe-delimited: ``'C0402' | '100NF' | ...``
          2. Equals-delimited: ``'D_3mm'(!) = 'hole120np'``

        HDL library part.ptf files sometimes use ``=`` instead of ``|``
        as the column separator (e.g. hole component).  This method
        auto-detects the delimiter.

        Args:
            row_text: A data row string.

        Returns:
            List of extracted value strings.
        """
        # P1-3: Detect equals-delimited format
        if "=" in row_text and "|" not in row_text:
            # Equals-delimited: extract all quoted values via regex
            fields = re.findall(r"'([^']*)'", row_text)
            return [f.strip() for f in fields]

        # Original pipe-delimited parsing
        values: list[str] = []
        current_val = ""
        in_quote = False
        i = 0

        while i < len(row_text):
            ch = row_text[i]

            if ch == "'" and not in_quote:
                in_quote = True
                i += 1
                continue
            elif ch == "'" and in_quote:
                # Check for escaped quote ''
                if i + 1 < len(row_text) and row_text[i + 1] == "'":
                    current_val += "'"
                    i += 2
                    continue
                else:
                    in_quote = False
                    i += 1
                    continue

            if ch == "|" and not in_quote:
                values.append(current_val.strip())
                current_val = ""
                i += 1
                continue

            if in_quote:
                current_val += ch

            i += 1

        # Append last value
        values.append(current_val.strip())

        return values
