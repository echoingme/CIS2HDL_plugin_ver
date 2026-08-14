"""Parser for OrCAD CIS Cross Reference CSV export files.

The Cross Reference CSV is exported from OrCAD CIS via
Tools → Cross Reference and contains reference designators, values,
schematic page names, and physical coordinates for every component
instance in the design.

Format (example)::

      Revised: Tuesday, August 04, 2026
              Revision:
    Design Name:  C:\\USERS\\ZHONG\\DESKTOP\\CIS\\HG5015-BE36_V10.DSN
    Cross Reference           August 4,2026      15:59:18,Page1
    Item,Part,Reference,SchematicName,Sheet,Library,X,Y
    ____________________________________________________________________________
    1,0*,C502,TG1C0D8_VB/19-WIFI5G_FEM_C0,0,C:\\...\\LIBRARY1.OLB, 142.50, 57.50

Key characteristics:
    - Lines 1-3: metadata header (Revision, Design Name, Cross Reference title)
    - Line 4: column header row
    - Line 5: separator line (underscores)
    - Line 6+: CSV data rows
    - ``Part`` column = component value (e.g. ``"0*"``, ``"0.2P*"``, ``"10UF"``)
    - ``Reference`` column = RefDes (e.g. ``"C502"``, ``"R75"``)
    - ``SchematicName`` column = page path (e.g. ``"TG1C0D8_VB/19-WIFI5G_FEM_C0"``)
    - X/Y coordinates are in **inches** (must × 100 for CIS internal mils)
    - Trailing ``*`` in values means "non-precise" in CIS; stripped on parse.

Usage::

    from cis2hdl.core.parser.cross_ref_parser import CrossRefParser

    parser = CrossRefParser()
    entries: dict[str, CrossRefEntry] = parser.parse_file(Path("design.CSV"))
    entry = entries.get("C89")
    if entry:
        print(entry.value)          # "0.2P"
        print(entry.refdes)         # "C89"
        print(entry.page_name())    # "19-WIFI5G_FEM_C0"
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Data structures
# ---------------------------------------------------------------------------


@dataclass
class CrossRefEntry:
    """A single row from the OrCAD CIS Cross Reference CSV.

    Attributes:
        refdes: Reference designator (e.g. ``"C502"``).
        value: Component value with trailing ``*`` removed
               (e.g. ``"0"`` from ``"0*"``, ``"0.2P"`` from ``"0.2P*"``).
        schematic_name: Full schematic path (e.g. ``"TG1C0D8_VB/19-WIFI5G_FEM_C0"``).
        sheet: Sheet number within the page.
        library: OLB library path.
        x: X coordinate in **inches** from the CSV.
        y: Y coordinate in **inches** from the CSV.

    Phase XVIII R4：新增 DESCRIPTION / JEDEC_TYPE / PACKAGE_TYPE /
    SN_NUM 四属性字段（真实项目 CSV 头行含这些列；``_parse_row`` 按
    头行列名提取，缺失时保持空串）—— CSA 属性块注入的数据源。
    """

    refdes: str = ""
    value: str = ""
    schematic_name: str = ""
    sheet: str = "0"
    library: str = ""
    x: float = 0.0
    y: float = 0.0

    # ── Phase XVIII R4: CrossRef 四属性（CSA 属性块注入数据源） ──
    description: str = ""
    jedec_type: str = ""
    package_type: str = ""
    sn_num: str = ""

    # Cached page name (lazily populated)
    _page_name: Optional[str] = field(default=None, repr=False)

    def page_name(self) -> str:
        """Return the page-only portion of the schematic name.

        For ``"TG1C0D8_VB/19-WIFI5G_FEM_C0"`` returns ``"19-WIFI5G_FEM_C0"``.

        Returns:
            The page name segment after the last ``/``, or the full
            schematic name if no ``/`` is present.
        """
        if self._page_name is None:
            self._page_name = _normalize_schematic_name(self.schematic_name)
        return self._page_name

    @property
    def x_mils(self) -> int:
        """X coordinate converted to CIS internal mils (inches × 100)."""
        return int(round(self.x * 100))

    @property
    def y_mils(self) -> int:
        """Y coordinate converted to CIS internal mils (inches × 100)."""
        return int(round(self.y * 100))


# ---------------------------------------------------------------------------
#  Helper functions
# ---------------------------------------------------------------------------


def _normalize_schematic_name(name: str) -> str:
    """Extract the page-only name from a full schematic path.

    ``"TG1C0D8_VB/19-WIFI5G_FEM_C0"`` → ``"19-WIFI5G_FEM_C0"``
    ``"19-WIFI5G_FEM_C0"`` → ``"19-WIFI5G_FEM_C0"``

    Args:
        name: Full schematic name from the CSV SchematicName column.

    Returns:
        The page name segment (text after the last ``/``), or the
        original string if no ``/`` is found.
    """
    if "/" in name:
        return name.rsplit("/", 1)[-1]
    return name


def _strip_value_asterisk(value: str) -> str:
    """Remove trailing ``*`` from a CIS component value.

    In OrCAD CIS, ``*`` after a value means "non-precise".
    ``"0*"`` means 0Ω resistor.  We strip the ``*`` for matching.

    Args:
        value: Raw value from the CSV Part column.

    Returns:
        Value with trailing ``*`` removed and whitespace trimmed.

    Examples:
        >>> _strip_value_asterisk("0*")
        "0"
        >>> _strip_value_asterisk("0.2P*")
        "0.2P"
        >>> _strip_value_asterisk("10UF")
        "10UF"
    """
    if not value:
        return ""
    return value.strip().rstrip("*")


def _parse_coordinate(raw: str) -> float:
    """Parse a coordinate string to a float, returning 0.0 on failure.

    Args:
        raw: Raw coordinate string from CSV (may be empty or whitespace).

    Returns:
        Float value, or 0.0 if unparseable.
    """
    if not raw or not raw.strip():
        return 0.0
    try:
        return float(raw.strip())
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
#  Encoding detection
# ---------------------------------------------------------------------------

#: Ordered list of encodings to try when reading Cross Reference CSV files.
_ENCODING_CANDIDATES: tuple[str, ...] = ("utf-8-sig", "utf-8", "gbk", "latin-1")


def _read_with_fallback(path: Path) -> str:
    """Read a file with automatic encoding detection.

    Tries encodings in order: utf-8-sig → utf-8 → gbk → latin-1.

    Args:
        path: Path to the file.

    Returns:
        Decoded file content.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If all encoding attempts fail.
    """
    raw_bytes: bytes = path.read_bytes()
    last_error: Optional[Exception] = None

    for enc in _ENCODING_CANDIDATES:
        try:
            text: str = raw_bytes.decode(enc)
            logger.debug("CrossRef CSV decoded with encoding '%s': %s", enc, path)
            return text
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    # All encodings failed — raise the last error
    raise OSError(
        f"Failed to decode {path} with any encoding "
        f"({', '.join(_ENCODING_CANDIDATES)})"
    ) from last_error


# ---------------------------------------------------------------------------
#  Regex for CSV data-row detection
# ---------------------------------------------------------------------------

#: Matches a valid data row: starts with a digit (Item column), then comma
#: or tab.  Real OrCAD Cross Reference exports (``entire.csv``) are
#: tab-delimited; the simplified fixture CSV is comma-delimited.
_RE_DATA_ROW = re.compile(r"^\s*\d+\s*[,\t]")

#: Matches the column header row (comma- or tab-delimited variants).
_RE_HEADER_ROW = re.compile(
    r"^\s*(?:Item\s*[,\t]\s*Part\s*[,\t]|\"HEADER\"\s*[,\t])",
    re.IGNORECASE,
)

#: Matches the OrCAD "Entire" export header row (tab-delimited).
_RE_ENTIRE_HEADER = re.compile(r'^\s*"HEADER"\s*\t\s*"ID"', re.IGNORECASE)

#: Matches the separator line (at least 10 underscore characters).
_RE_SEPARATOR = re.compile(r"^_{10,}\s*$")


# ---------------------------------------------------------------------------
#  Parser
# ---------------------------------------------------------------------------


class CrossRefParser:
    """Parser for OrCAD CIS Cross Reference CSV export files.

    Parses the Cross Reference CSV and returns a ``dict[str, CrossRefEntry]``
    keyed by reference designator (refdes).

    The CSV is an **optional** data source — if the file does not exist,
    callers should skip injection gracefully.

    Usage::

        parser = CrossRefParser()
        entries: dict[str, CrossRefEntry] = parser.parse_file(Path("design.CSV"))
        for refdes, entry in entries.items():
            print(f"{refdes}: {entry.value} @ ({entry.x_mils}, {entry.y_mils})")
    """

    # Column indices in the data rows (0-based, after csv.split(','))
    COL_ITEM: int = 0
    COL_PART: int = 1
    COL_REFERENCE: int = 2
    COL_SCHEMATIC_NAME: int = 3
    COL_SHEET: int = 4
    COL_LIBRARY: int = 5
    COL_X: int = 6
    COL_Y: int = 7

    # Minimum expected number of columns in a valid data row
    MIN_COLUMNS: int = 6

    def __init__(self) -> None:
        """Initialize the CrossRef parser."""
        #: 头行列名（小写）→ 列索引（Phase XVIII R4 属性提取用）。
        self._col_map: dict[str, int] = {}

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def parse_file(self, path: Path) -> dict[str, CrossRefEntry]:
        """Parse a Cross Reference CSV file.

        Args:
            path: Path to the Cross Reference CSV file.

        Returns:
            Dictionary mapping ``refdes → CrossRefEntry``.  Returns an
            empty dict if the file cannot be parsed or contains no valid
            data rows.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"Cross Reference CSV not found: {path}")

        logger.info("Parsing Cross Reference CSV: %s", path)

        try:
            content: str = _read_with_fallback(path)
        except OSError as exc:
            logger.warning("Failed to read Cross Reference CSV %s: %s", path, exc)
            return {}

        return self.parse(content, str(path))

    def parse(self, content: str, source_path: str = "") -> dict[str, CrossRefEntry]:
        """Parse Cross Reference CSV content string.

        Args:
            content: Raw text content of the Cross Reference CSV.
            source_path: Source file path for logging (optional).

        Returns:
            Dictionary mapping ``refdes → CrossRefEntry``.
        """
        lines: list[str] = content.splitlines()

        # Phase XVIII R4: 支持两种真实格式 ——
        #  1) 简化版：逗号分隔，头行 ``Item,Part,Reference,...``；
        #  2) OrCAD "Entire" 导出：tab 分隔，头行 ``"HEADER"\t"ID"...``，
        #     数据行 ``"PARTINST:..."``（元件）与 ``"PININST:..."``（引脚）。
        #     属性注入只需要 PARTINST 行（含 refdes/value/四属性）。
        if any(_RE_ENTIRE_HEADER.match(ln) for ln in lines[:8]):
            return self._parse_entire(lines, source_path)

        entries: dict[str, CrossRefEntry] = {}
        data_started: bool = False
        header_seen: bool = False
        self._col_map = {}

        for line in lines:
            stripped: str = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Detect header row
            if not header_seen and _RE_HEADER_ROW.match(stripped):
                header_seen = True
                self._col_map = self._build_col_map(stripped)
                continue

            # Skip separator line (underscores) after header
            if header_seen and not data_started:
                if _RE_SEPARATOR.match(stripped):
                    continue

            # Detect first data row after header + separator
            if header_seen and _RE_DATA_ROW.match(stripped):
                data_started = True

            # Parse data rows
            if data_started:
                entry: Optional[CrossRefEntry] = self._parse_row(stripped)
                if entry is not None and entry.refdes:
                    entries[entry.refdes] = entry

        logger.info(
            "CrossRef CSV: loaded %d entries from %s",
            len(entries),
            source_path or "<string>",
        )

        if not entries:
            logger.warning("CrossRef CSV: no valid data rows found in %s",
                           source_path or "<string>")

        return entries

    # ------------------------------------------------------------------
    #  Internal parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_delimiter(line: str) -> str:
        """Detect the CSV delimiter for a header/data line.

        Real OrCAD Cross Reference exports (``entire.csv``) are
        tab-delimited; simplified fixtures are comma-delimited.  Count
        occurrences and pick the larger (ties → comma, the legacy default).

        Args:
            line: A header or data row line.

        Returns:
            ``"\\t"`` or ``","``.
        """
        if "\t" in line and line.count("\t") >= line.count(","):
            return "\t"
        return ","

    @staticmethod
    def _build_col_map(header_line: str) -> dict[str, int]:
        """Build a lowercase column-name → index map from the header row.

        Phase XVIII R4：真实项目 CrossRef CSV 头行含 DESCRIPTION /
        JEDEC_TYPE / PACKAGE_TYPE / SN_NUM（别名 PKG_TYPE）列。支持
        逗号与 tab 两种分隔（``_detect_delimiter`` 自动判定）。

        Args:
            header_line: 头行文本（如 ``"Item,Part,Reference,..."``）。

        Returns:
            ``{列名小写: 列索引}``。
        """
        col_map: dict[str, int] = {}
        try:
            row = next(csv.reader(
                [header_line],
                delimiter=CrossRefParser._detect_delimiter(header_line),
                skipinitialspace=True,
            ))
        except (csv.Error, StopIteration):
            return col_map
        for idx, name in enumerate(row):
            key = name.strip().strip('"').lower()
            if not key:
                continue
            col_map[key] = idx
            # 常见别名归一化
            if key == "pkg_type":
                col_map["package_type"] = idx
        return col_map

    def _parse_row(self, row_text: str) -> Optional[CrossRefEntry]:
        """Parse a single CSV data row.

        Uses Python's ``csv`` module for proper CSV parsing
        (handles quoted fields with embedded commas).

        Args:
            row_text: A single data row string.

        Returns:
            CrossRefEntry or None if the row is invalid/malformed.
        """
        try:
            reader = csv.reader(
                StringIO(row_text),
                delimiter=CrossRefParser._detect_delimiter(row_text),
                skipinitialspace=True,
            )
            fields: list[str] = next(reader)
        except (csv.Error, StopIteration):
            logger.debug("CrossRef CSV: failed to parse row: %s", row_text[:80])
            return None

        if len(fields) < self.MIN_COLUMNS:
            logger.debug(
                "CrossRef CSV: row has %d fields, need >= %d: %s",
                len(fields), self.MIN_COLUMNS, row_text[:80],
            )
            return None

        # Extract fields by column position
        part_raw: str = fields[self.COL_PART] if len(fields) > self.COL_PART else ""
        refdes: str = fields[self.COL_REFERENCE] if len(fields) > self.COL_REFERENCE else ""
        schematic_name: str = fields[self.COL_SCHEMATIC_NAME] if len(fields) > self.COL_SCHEMATIC_NAME else ""
        sheet: str = fields[self.COL_SHEET] if len(fields) > self.COL_SHEET else "0"
        library: str = fields[self.COL_LIBRARY] if len(fields) > self.COL_LIBRARY else ""
        x_raw: str = fields[self.COL_X] if len(fields) > self.COL_X else ""
        y_raw: str = fields[self.COL_Y] if len(fields) > self.COL_Y else ""

        if not refdes:
            return None

        value: str = _strip_value_asterisk(part_raw)
        x: float = _parse_coordinate(x_raw)
        y: float = _parse_coordinate(y_raw)

        # ── Phase XVIII R4: CrossRef 四属性（按头行列名提取） ────
        col_map = self._col_map or {}

        def _col_val(*aliases: str) -> str:
            for alias in aliases:
                idx = col_map.get(alias)
                if idx is not None and idx < len(fields):
                    val = fields[idx].strip()
                    # 过滤 OrCAD 空值占位符（源 CSV 无值时不注入 "?"）。
                    if val and val.upper() not in ("<NULL>", "NULL", "?"):
                        return val
            return ""

        return CrossRefEntry(
            refdes=refdes,
            value=value,
            schematic_name=schematic_name,
            sheet=sheet,
            library=library,
            x=x,
            y=y,
            description=_col_val("description"),
            jedec_type=_col_val("jedec_type", "jedec"),
            package_type=_col_val("package_type", "pkg_type"),
            sn_num=_col_val("sn_num", "sn"),
        )

    def _parse_entire(
        self, lines: list[str], source_path: str = "",
    ) -> dict[str, CrossRefEntry]:
        """Parse an OrCAD "Entire" export (tab-delimited, ``"HEADER"`` row).

        Only ``PARTINST:`` rows (component instances) are parsed; the
        ``PININST:`` rows (pin-level details) are skipped.  Column indices
        come from the ``"HEADER"`` row via ``_build_col_map``.

        Args:
            lines: Raw content lines.
            source_path: Source file path for logging (optional).

        Returns:
            ``{refdes: CrossRefEntry}`` mapping.
        """
        entries: dict[str, CrossRefEntry] = {}
        col_map: dict[str, int] = {}
        header_seen: bool = False

        for raw in lines:
            stripped: str = raw.strip()
            if not stripped:
                continue
            if not header_seen and _RE_ENTIRE_HEADER.match(stripped):
                header_seen = True
                col_map = self._build_col_map(stripped)
                continue
            if not header_seen or not stripped.startswith('"PARTINST:'):
                continue
            try:
                fields: list[str] = next(csv.reader(
                    [stripped],
                    delimiter="\t",
                    skipinitialspace=True,
                ))
            except (csv.Error, StopIteration):
                continue
            if len(fields) < self.MIN_COLUMNS:
                continue

            def _col(*aliases: str) -> str:
                for alias in aliases:
                    idx = col_map.get(alias)
                    if idx is not None and idx < len(fields):
                        val: str = fields[idx].strip().strip('"')
                        # 过滤 OrCAD 空值占位符（源 CSV 无值时不注入）。
                        if val and val.upper() not in ("<NULL>", "NULL", "?"):
                            return val
                return ""

            refdes: str = _col("part reference", "reference")
            if not refdes:
                continue
            # 页面归属：OrCAD "Entire" 导出在 ID 列编码页面路径——
            # ``"PARTINST:<设计>:<页面>:<序号>"``（如
            # ``PARTINST:TG1C0D8_VB:10-SOC_SerDes:265`` → 页面
            # ``10-SOC_SerDes``），与简化版 SchematicName 列
            # ``"TG1C0D8_VB/10-SOC_SerDes"`` 同构。缺此解析时 page_name
            # 为空 → 转换引擎 fuzzy 匹配 ``'' in page_id`` 恒真，全部
            # 实例被塞进 page1（P0-D2 阶段页面归属错乱）。
            schematic_name = _col("schematic name", "schematicname")
            if not schematic_name and fields:
                _pid = (fields[0] or "").strip().strip('"')
                if _pid.startswith("PARTINST:"):
                    _parts = _pid.split(":")
                    if len(_parts) >= 3:
                        # PARTINST:<设计>:<页面>[:...]
                        schematic_name = f"{_parts[1]}/{_parts[2]}"
            # 坐标：Entire 导出含 Location X/Y 列（OrCAD 页面坐标）。
            try:
                _x = float(_col("location x-coordinate") or 0.0)
            except ValueError:
                _x = 0.0
            try:
                _y = float(_col("location y-coordinate") or 0.0)
            except ValueError:
                _y = 0.0
            entries[refdes] = CrossRefEntry(
                refdes=refdes,
                value=_strip_value_asterisk(_col("value")),
                schematic_name=schematic_name,
                sheet=_col("sheet") or "0",
                library=_col("source library", "library"),
                x=_x,
                y=_y,
                description=_col("description"),
                jedec_type=_col("jedec_type", "jedec"),
                package_type=_col("package_type", "pkg_type"),
                sn_num=_col("sn_num", "sn"),
            )

        logger.info(
            "CrossRef CSV (Entire): loaded %d entries from %s",
            len(entries),
            source_path or "<string>",
        )
        if not entries:
            logger.warning(
                "CrossRef CSV (Entire): no PARTINST rows found in %s",
                source_path or "<string>",
            )
        return entries


# ---------------------------------------------------------------------------
#  Convenience function
# ---------------------------------------------------------------------------


def parse_cross_ref(path: Path) -> dict[str, CrossRefEntry]:
    """Parse a Cross Reference CSV file and return a refdes→entry mapping.

    Convenience wrapper around ``CrossRefParser.parse_file()``.

    Args:
        path: Path to the Cross Reference CSV file.

    Returns:
        Dictionary mapping ``refdes → CrossRefEntry``.  Returns an empty
        dict if the file does not exist or cannot be parsed.

    Example:
        >>> entries = parse_cross_ref(Path("design.CSV"))
        >>> entry = entries.get("C89")
        >>> if entry:
        ...     print(entry.value, entry.x_mils, entry.y_mils)
    """
    parser = CrossRefParser()
    try:
        return parser.parse_file(path)
    except FileNotFoundError:
        logger.debug("Cross Reference CSV not found (skipped): %s", path)
        return {}
    except Exception as exc:
        logger.warning("Failed to parse Cross Reference CSV %s: %s", path, exc)
        return {}
