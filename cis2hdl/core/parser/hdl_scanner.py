"""HDL Library Scanner — discovers and indexes Cadence HDL component libraries.

Scans a directory tree containing HDL component libraries (one subdirectory
per component), parses chips.prt / symbol.css / part.ptf files, and assembles
a unified ComponentDB.

Usage:
    scanner = HDLLibScanner()
    db = scanner.scan(Path("/path/to/hdl_lib"))
    print(scanner.stats())  # {'total': 124, 'by_category': {'IC': 45, ...}}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cis2hdl.core.db.component_db import ComponentDB
from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.parser.chips_prt import ChipsPrtParser
from cis2hdl.core.parser.part_ptf import PartProperty, PartPtfParser
from cis2hdl.core.parser.symbol_css import SchematicSymbolDef, SymbolCssParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Scan statistics
# ---------------------------------------------------------------------------


@dataclass
class ScanStats:
    """Statistics collected during HDL library scanning."""

    total_dirs_scanned: int = 0
    total_components_found: int = 0
    chips_prt_parsed: int = 0
    chips_prt_missing: int = 0
    chips_prt_error: int = 0
    part_ptf_parsed: int = 0
    part_ptf_missing: int = 0
    symbol_css_parsed: int = 0
    symbol_css_missing: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
#  Scanner
# ---------------------------------------------------------------------------


class HDLLibScanner:
    """Scans a Cadence HDL library directory and builds a ComponentDB.

    For each component directory, parses available chips.prt, symbol.css,
    and part.ptf files, then assembles a unified ComponentDef.

    Error handling: individual file parse failures are logged as warnings
    and do not block the overall scan. Components with at least chips.prt
    are included; missing optional files result in empty/default values.

    Usage:
        scanner = HDLLibScanner()
        db = scanner.scan(Path("/path/to/hdl_lib"))
        stats = scanner.stats()
    """

    def __init__(
        self,
        chips_encoding: str = "utf-8",
        symbol_encoding: str = "utf-8",
        ptf_encoding: str = "utf-8",
        recursive: bool = True,
        exclude_dirs: Optional[list[str]] = None,
    ) -> None:
        """Initialize the scanner.

        Args:
            chips_encoding: Encoding for chips.prt files.
            symbol_encoding: Encoding for symbol.css files.
            ptf_encoding: Encoding for part.ptf files.
            recursive: Whether to scan subdirectories recursively.
            exclude_dirs: Directory names to skip during scanning.
        """
        self._chips_parser = ChipsPrtParser(encoding=chips_encoding)
        self._symbol_parser = SymbolCssParser(encoding=symbol_encoding)
        self._ptf_parser = PartPtfParser(encoding=ptf_encoding)
        self._recursive = recursive
        self._exclude_dirs: set[str] = set(exclude_dirs or [])
        self._exclude_dirs.update({".git", "__pycache__", "temp"})

        self._stats = ScanStats()

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def scan(self, lib_root: Path) -> ComponentDB:
        """Scan the HDL library directory and build a ComponentDB.

        Args:
            lib_root: Root directory of the HDL component library.

        Returns:
            ComponentDB containing all discovered components.

        Raises:
            FileNotFoundError: If lib_root does not exist.
            NotADirectoryError: If lib_root is not a directory.
        """
        if not lib_root.exists():
            raise FileNotFoundError(f"HDL library root not found: {lib_root}")
        if not lib_root.is_dir():
            raise NotADirectoryError(f"Not a directory: {lib_root}")

        # Reset stats
        self._stats = ScanStats()

        db = ComponentDB()
        logger.info("Starting HDL library scan: %s", lib_root)

        # Find all component directories
        comp_dirs = self._discover_components(lib_root)
        self._stats.total_dirs_scanned = len(comp_dirs)

        logger.info("Discovered %d potential component directories", len(comp_dirs))

        for comp_dir in comp_dirs:
            try:
                comp_def = self._parse_component(comp_dir)
                if comp_def is not None:
                    db.add(comp_def)
                    self._stats.total_components_found += 1
            except Exception as exc:
                msg = f"Unexpected error parsing component {comp_dir.name}: {exc}"
                logger.error(msg)
                self._stats.errors.append(msg)

        logger.info(
            "HDL library scan complete: %d components indexed",
            self._stats.total_components_found,
        )
        return db

    def stats(self) -> dict:
        """Return scan statistics as a dictionary.

        Returns:
            dict with keys: total_dirs_scanned, total_components_found,
            chips_prt_parsed, chips_prt_missing, chips_prt_error,
            part_ptf_parsed, part_ptf_missing,
            symbol_css_parsed, symbol_css_missing,
            errors, warnings.
        """
        return {
            "total_dirs_scanned": self._stats.total_dirs_scanned,
            "total_components_found": self._stats.total_components_found,
            "chips_prt_parsed": self._stats.chips_prt_parsed,
            "chips_prt_missing": self._stats.chips_prt_missing,
            "chips_prt_error": self._stats.chips_prt_error,
            "part_ptf_parsed": self._stats.part_ptf_parsed,
            "part_ptf_missing": self._stats.part_ptf_missing,
            "symbol_css_parsed": self._stats.symbol_css_parsed,
            "symbol_css_missing": self._stats.symbol_css_missing,
            "errors": list(self._stats.errors),
            "warnings": list(self._stats.warnings),
        }

    # ------------------------------------------------------------------
    #  Directory discovery
    # ------------------------------------------------------------------

    def _discover_components(self, lib_root: Path) -> list[Path]:
        """Find all component directories within the library root.

        A component directory is a subdirectory that contains at least
        one of: chips/ subdirectory, sym_1/ subdirectory, or
        part_table/ subdirectory (indicating it is a valid HDL component).

        Args:
            lib_root: Root directory to scan.

        Returns:
            Sorted list of component directory paths.
        """
        components: list[Path] = []

        pattern = "**/*" if self._recursive else "*"
        for entry in sorted(lib_root.glob(pattern)):
            if not entry.is_dir():
                continue

            # Skip excluded directories
            if entry.name in self._exclude_dirs:
                continue

            # A component directory has at least one of the expected subdirs
            if self._is_component_dir(entry):
                components.append(entry)

        return components

    def _is_component_dir(self, directory: Path) -> bool:
        """Check if a directory looks like an HDL component directory.

        Criteria: contains at least one of chips/, sym_1/, or part_table/.
        """
        indicators = ["chips", "sym_1", "part_table"]
        for indicator in indicators:
            if (directory / indicator).is_dir():
                return True
        # Also check for chips.prt directly
        if (directory / "chips" / "chips.prt").is_file():
            return True
        return False

    # ------------------------------------------------------------------
    #  Component parsing
    # ------------------------------------------------------------------

    def _parse_component(self, comp_dir: Path) -> Optional[ComponentDef]:
        """Parse a single component directory into a ComponentDef.

        Orchestrates the three parsers and merges results.

        Args:
            comp_dir: Path to the component directory.

        Returns:
            ComponentDef if chips.prt was successfully parsed, else None.
        """
        part_name = comp_dir.name
        library_id = part_name.lower()

        # 1. Parse chips.prt → get pins + part_name + category
        chips_components = self._parse_chips_prt(comp_dir)
        if not chips_components:
            logger.warning(
                "Skipping component '%s': no valid chips.prt data", part_name
            )
            return None

        # Use the first (and typically only) primitive
        base_comp = chips_components[0]

        # 2. Parse part.ptf → get footprint, value, BOM data
        ptf_properties = self._parse_part_ptf(comp_dir)
        ptf_data: PartProperty = (
            ptf_properties[0] if ptf_properties else PartProperty()
        )

        # 3. Parse symbol.css → get symbol graphics
        symbol_data: list[SchematicSymbolDef] = []
        for sym_dir in sorted(comp_dir.glob("sym_*")):
            if sym_dir.is_dir():
                sym = self._parse_symbol_css(sym_dir)
                if sym:
                    symbol_data.append(sym)

        # Assemble ComponentDef
        footprint = ptf_data.jedec_type or ptf_data.package_type
        value = ptf_data.value
        description = ptf_data.description
        bom_seq = ptf_data.bom_seq
        sn_num = ptf_data.sn_num

        # Fallback: if no part.ptf, use the base component's existing field values
        if not footprint:
            footprint = base_comp.footprint
        if not value:
            value = base_comp.value

        comp_def = ComponentDef(
            library_id=library_id,
            part_name=base_comp.part_name or part_name,
            category=base_comp.category,
            phys_des_prefix=getattr(base_comp, 'phys_des_prefix', ''),
            pins=list(base_comp.pins),
            footprint=footprint,
            value=value,
            description=description,
            bom_seq=bom_seq,
            sn_num=sn_num,
            symbols=[self._symbol_to_dict(s) for s in symbol_data],
            source_format="HDL",
            source_file=str(comp_dir),
        )

        # ── Store ALL primitives from chips.prt ─────────────────────
        # v0.7.0: Previously only chips_components[0] was used for the
        # ComponentDef fields.  Now all primitives are stored so that
        # downstream matchers (FallbackMatcher Step 5.5) can select the
        # correct primitive (e.g. CAPACITOR_0402 vs CAPACITOR_0603)
        # based on the source component's value.
        comp_def.extra_data["all_primitives"] = [
            {
                "part_name": c.part_name,
                "library_id": c.library_id,
                "pins": [{"number": p.number, "name": p.name} for p in c.pins],
                "category": c.category,
                "footprint": c.footprint,
                "description": c.description,
            }
            for c in chips_components
        ]

        # ── Store complete part.ptf rows for ValueMatcher ────────────
        if ptf_properties:
            comp_def.extra_data["ptf_rows"] = [
                {
                    "package_type": row.package_type,
                    "value": row.value,
                    "jedec_type": row.jedec_type,
                    "description": row.description,
                }
                for row in ptf_properties
            ]

        return comp_def

    # ------------------------------------------------------------------
    #  Sub-parsers
    # ------------------------------------------------------------------

    def _parse_chips_prt(self, comp_dir: Path) -> list[ComponentDef]:
        """Parse the chips.prt file for a component.

        Args:
            comp_dir: Component directory path.

        Returns:
            List of ComponentDef from chips.prt, or empty list.
        """
        chips_path = comp_dir / "chips" / "chips.prt"
        if not chips_path.is_file():
            logger.debug("chips.prt not found: %s", chips_path)
            self._stats.chips_prt_missing += 1
            self._stats.warnings.append(
                f"chips.prt missing for {comp_dir.name}"
            )
            return []

        try:
            components = self._chips_parser.parse_file(chips_path)
            self._stats.chips_prt_parsed += 1
            return components
        except Exception as exc:
            logger.warning("Error parsing chips.prt for %s: %s", comp_dir.name, exc)
            self._stats.chips_prt_error += 1
            self._stats.errors.append(
                f"chips.prt parse error for {comp_dir.name}: {exc}"
            )
            return []

    def _parse_symbol_css(self, sym_dir: Path) -> Optional[SchematicSymbolDef]:
        """Parse symbol.css from a sym_N directory.

        Args:
            sym_dir: Path to sym_1/, sym_2/, etc.

        Returns:
            SchematicSymbolDef or None.
        """
        css_path = sym_dir / "symbol.css"
        if not css_path.is_file():
            self._stats.symbol_css_missing += 1
            return None

        try:
            symbol = self._symbol_parser.parse_file(css_path)
            self._stats.symbol_css_parsed += 1
            return symbol
        except Exception as exc:
            logger.warning(
                "Error parsing symbol.css in %s: %s", sym_dir.name, exc
            )
            return None

    def _parse_part_ptf(self, comp_dir: Path) -> list[PartProperty]:
        """Parse the part.ptf file for a component.

        Args:
            comp_dir: Component directory path.

        Returns:
            List of PartProperty from part.ptf, or empty list.
        """
        ptf_path = comp_dir / "part_table" / "part.ptf"
        if not ptf_path.is_file():
            logger.debug("part.ptf not found: %s", ptf_path)
            self._stats.part_ptf_missing += 1
            return []

        try:
            properties = self._ptf_parser.parse_file(ptf_path)
            self._stats.part_ptf_parsed += 1
            return properties
        except Exception as exc:
            logger.warning("Error parsing part.ptf for %s: %s", comp_dir.name, exc)
            return []

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _symbol_to_dict(symbol: SchematicSymbolDef) -> dict:
        """Convert a SchematicSymbolDef to a serializable dict.

        This is stored in ComponentDef.symbols (list[dict]).
        """
        return {
            "pin_count": len(symbol.pins),
            "pins": [
                {
                    "number": p.number,
                    "name": p.name,
                    "line_x1": p.line_x1,
                    "line_y1": p.line_y1,
                    "line_x2": p.line_x2,
                    "line_y2": p.line_y2,
                    "text_x": p.text_x,
                    "text_y": p.text_y,
                }
                for p in symbol.pins
            ],
            "attribute_count": len(symbol.attributes),
            "graphic_count": len(symbol.graphics),
            "bounding_box": list(symbol.bounding_box()),
            "has_outline": symbol.outline is not None,
            "has_location": symbol.location is not None,
            "has_value_attr": symbol.value_attr is not None,
        }
