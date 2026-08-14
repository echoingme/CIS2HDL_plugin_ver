"""Unified Component Catalog — based on CrossRef CSV.

The ComponentCatalog is the single source of truth for component identity
(refdes, value, coordinates, page assignment) in the CrossRef-driven
architecture.  It is built from the OrCAD CIS Cross Reference CSV export
and has zero external dependencies beyond Python stdlib and
``core.ir.component``.

DSN is no longer used as the data source for component identity; it is
only consulted for network topology (Wire / Net connections).

Usage::

    from cis2hdl.core.parser.component_catalog import ComponentCatalog

    catalog = ComponentCatalog.from_cross_ref(Path("design.CSV"))
    print(catalog.summary())
    for entry in catalog.all_entries():
        print(f"{entry.refdes}: {entry.value} @ ({entry.loc_x}, {entry.loc_y})")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cis2hdl.core.ir.component import ComponentDef
from cis2hdl.core.parser.cross_ref_parser import CrossRefEntry, CrossRefParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Footprint hint derivation (refdes prefix → component type)
# ---------------------------------------------------------------------------

#: Refdes prefix → footprint / type hint mapping.
#: Used when the CSV does not provide an explicit package type.
_PREFIX_TO_HINT: dict[str, str] = {
    "C": "capacitor",
    "R": "resistor",
    "L": "inductor",
    "RN": "resistor_network",
    "FB": "ferrite_bead",
    "LB": "ferrite_bead",
    "U": "ic",
    "J": "connector",
    "D": "diode",
    "Q": "transistor",
    "T": "transformer",
    "X": "crystal",
    "Y": "oscillator",
    "F": "fuse",
    "TP": "testpoint",
    "SW": "switch",
    "LED": "led",
    "ZD": "zener_diode",
    "DZ": "zener_diode",    # v0.8.0: DZ3/DZ_L → zener
    "VR": "voltage_regulator",
    "M": "module",
    "S": "switch",
    "IC": "ic",
    "K": "relay",
    "Z": "zener_diode",
    "P": "connector",
    # ROUTE: OrCAD 0 欧姆跳线（COPPER0201 封装，Source Package=ROUTE）。
    # Phase XI P0 修复（2026-08-10）：Value=ROUTE 的 J 跳线是**真实元件**
    # （2 引脚、连接两个不同网络，如 J11: HGPIO_17↔2P5GE_RSTN），
    # 必须保留转换——映射到 resistor（0 欧跳线本质是电阻）。
    # 此前的 `_SKIP_REFDES_VALUES={"ROUTE"}` 错误地把它们当"布线标记"跳过，
    # 导致 con instances 889 vs pstxnet 906 的偏差（25 个 J 跳线丢失）。
    "ROUTE": "resistor",
}

#: Refdes values that should be skipped (not real components).
#: Phase XI P0 修复（2026-08-10）：ROUTE 跳线不再跳过（真实元件），
#: 仅跳过空 refdes / 无引脚标记。
_SKIP_REFDES_VALUES: set[str] = set()

#: Refdes prefix pattern — one or more letters at the start.
_RE_REFDES_PREFIX = re.compile(r"^([A-Za-z]+)")


def _extract_refdes_prefix(refdes: str) -> str:
    """Extract the alphabetic prefix from a reference designator.

    Args:
        refdes: Reference designator (e.g. ``"C502"``, ``"RN10"``).

    Returns:
        Uppercase alphabetic prefix, or ``""`` if not found.
    """
    if not refdes:
        return ""
    m = _RE_REFDES_PREFIX.match(refdes)
    return m.group(1).upper() if m else ""


def _derive_footprint_hint(refdes: str, library_path: str = "", value: str = "") -> str:
    """Derive a footprint / component-type hint from refdes prefix.

    Args:
        refdes: Reference designator.
        library_path: OLB library path (unused currently, reserved for future).
        value: Component value (unused currently, reserved for future).

    Returns:
        A human-readable component type hint (e.g. ``"capacitor"``).
    """
    prefix = _extract_refdes_prefix(refdes)
    # Phase XI P0 修复（2026-08-10）：Value=ROUTE 的元件是 0 欧姆跳线
    # （COPPER0201），映射到 resistor（与 _PREFIX_TO_CELL["ROUTE"] 一致），
    # 而不是按 J 前缀当 connector。
    if value and value.upper().strip("*") == "ROUTE":
        return "resistor"
    if prefix:
        # Try longest match first (e.g. "LED" before "L")
        for pfx in sorted(_PREFIX_TO_HINT, key=len, reverse=True):
            if prefix.startswith(pfx):
                return _PREFIX_TO_HINT[pfx]
    return "unknown"


# ---------------------------------------------------------------------------
#  CatalogEntry
# ---------------------------------------------------------------------------


@dataclass
class CatalogEntry:
    """A single component entry extracted from the CrossRef CSV.

    Attributes:
        refdes: Reference designator (e.g. ``"C502"``).
        value: Component value with trailing ``*`` removed (e.g. ``"0"``).
        footprint_hint: Derived component type hint (e.g. ``"capacitor"``).
        loc_x: X coordinate in **mils** (inches × 100).
        loc_y: Y coordinate in **mils** (inches × 100).
        page_name: Short page name (e.g. ``"19-WIFI5G_FEM_C0"``).
        schematic_name: Full schematic path from CSV.
        library_path: OLB library path from CSV.
        item: Item number from the CSV ``Item`` column.
    """

    refdes: str
    value: str
    footprint_hint: str = ""
    loc_x: int = 0
    loc_y: int = 0
    page_name: str = ""
    schematic_name: str = ""
    library_path: str = ""
    item: int = 0

    # ── Phase XVIII R4: CrossRef 四属性（CSA 属性块注入数据源） ──
    description: str = ""
    jedec_type: str = ""
    package_type: str = ""
    sn_num: str = ""

    # Cached refdes prefix
    _prefix: Optional[str] = field(default=None, repr=False)

    def refdes_prefix(self) -> str:
        """Return the alphabetic prefix of the reference designator.

        Returns:
            Uppercase prefix string (e.g. ``"C"``, ``"R"``, ``"U"``).
        """
        if self._prefix is None:
            self._prefix = _extract_refdes_prefix(self.refdes)
        return self._prefix

    @classmethod
    def from_cross_ref_entry(cls, entry: CrossRefEntry) -> CatalogEntry:
        """Create a CatalogEntry from a CrossRefEntry.

        Args:
            entry: A parsed CrossRefEntry from CrossRefParser.

        Returns:
            CatalogEntry with derived footprint hint and mils coordinates.
        """
        return cls(
            refdes=entry.refdes,
            value=entry.value,
            footprint_hint=_derive_footprint_hint(
                entry.refdes, entry.library, entry.value
            ),
            loc_x=entry.x_mils,
            loc_y=entry.y_mils,
            page_name=entry.page_name(),
            schematic_name=entry.schematic_name,
            library_path=entry.library,
            item=0,  # Item number not directly available from CrossRefEntry
            description=entry.description,
            jedec_type=entry.jedec_type,
            package_type=entry.package_type,
            sn_num=entry.sn_num,
        )


# ---------------------------------------------------------------------------
#  ComponentCatalog
# ---------------------------------------------------------------------------


class ComponentCatalog:
    """Unified component directory — built from CrossRef CSV.

    Provides lookup by refdes, by page, and can export ComponentDef
    objects suitable for the matching pipeline.

    This is the **single source of truth** for component identity in the
    CrossRef-driven architecture (v0.5.0).
    """

    def __init__(self) -> None:
        """Initialise an empty catalog."""
        self._by_refdes: dict[str, CatalogEntry] = {}
        self._by_page: dict[str, list[CatalogEntry]] = {}

    # ------------------------------------------------------------------
    #  Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_cross_ref(cls, csv_path: Path) -> ComponentCatalog:
        """Build a ComponentCatalog from a Cross Reference CSV file.

        Args:
            csv_path: Path to the CrossRef CSV file.

        Returns:
            A populated ComponentCatalog.

        Raises:
            FileNotFoundError: If the CSV file does not exist.
        """
        parser = CrossRefParser()
        raw_entries: dict[str, CrossRefEntry] = parser.parse_file(csv_path)

        catalog = cls()

        _skipped: int = 0
        for idx, (refdes, xref_entry) in enumerate(raw_entries.items(), start=1):
            # ── Skip ROUTE / non-component entries ───────────────
            if refdes.upper() in _SKIP_REFDES_VALUES:
                _skipped += 1
                continue
            if xref_entry.value and xref_entry.value.upper().strip("*") in _SKIP_REFDES_VALUES:
                _skipped += 1
                continue

            catalog_entry = CatalogEntry(
                refdes=refdes,
                value=xref_entry.value,
                footprint_hint=_derive_footprint_hint(
                    refdes, xref_entry.library, xref_entry.value
                ),
                loc_x=xref_entry.x_mils,
                loc_y=xref_entry.y_mils,
                page_name=xref_entry.page_name(),
                schematic_name=xref_entry.schematic_name,
                library_path=xref_entry.library,
                item=idx,
                # ── Phase XVIII R4: CrossRef 四属性（CSA 注入数据源） ──
                description=xref_entry.description,
                jedec_type=xref_entry.jedec_type,
                package_type=xref_entry.package_type,
                sn_num=xref_entry.sn_num,
            )
            catalog._by_refdes[refdes] = catalog_entry
            # Group by page
            pg = catalog_entry.page_name
            if pg not in catalog._by_page:
                catalog._by_page[pg] = []
            catalog._by_page[pg].append(catalog_entry)

        logger.info(
            "ComponentCatalog: loaded %d entries across %d pages from %s"
            " (skipped %d non-component entries)",
            len(catalog._by_refdes),
            len(catalog._by_page),
            csv_path,
            _skipped,
        )
        return catalog

    # ------------------------------------------------------------------
    #  Lookup
    # ------------------------------------------------------------------

    def get_by_refdes(self, refdes: str) -> Optional[CatalogEntry]:
        """Look up a catalog entry by reference designator.

        Args:
            refdes: Reference designator (e.g. ``"C502"``).

        Returns:
            CatalogEntry if found, else ``None``.
        """
        return self._by_refdes.get(refdes)

    def get_page_entries(self, page_name: str) -> list[CatalogEntry]:
        """Return all catalog entries for a given page.

        Args:
            page_name: Page name (e.g. ``"19-WIFI5G_FEM_C0"``).

        Returns:
            List of CatalogEntry objects on that page.
        """
        return list(self._by_page.get(page_name, []))

    def all_entries(self) -> list[CatalogEntry]:
        """Return all catalog entries.

        Returns:
            Sorted list of all CatalogEntry objects.
        """
        return sorted(self._by_refdes.values(), key=lambda e: e.refdes)

    def summary(self) -> dict:
        """Return a summary of the catalog contents.

        Returns:
            Dict with keys: ``total``, ``pages``, ``value_distribution``.
        """
        value_counts: dict[str, int] = {}
        for entry in self._by_refdes.values():
            v = entry.value or "<empty>"
            value_counts[v] = value_counts.get(v, 0) + 1

        return {
            "total": len(self._by_refdes),
            "pages": len(self._by_page),
            "value_distribution": dict(
                sorted(value_counts.items(), key=lambda x: -x[1])[:20]
            ),
        }

    def __len__(self) -> int:
        return len(self._by_refdes)

    def __contains__(self, refdes: str) -> bool:
        return refdes in self._by_refdes

    # ------------------------------------------------------------------
    #  Export: to ComponentDef (for matching pipeline)
    # ------------------------------------------------------------------

    def to_component_defs(self) -> list[ComponentDef]:
        """Convert all catalog entries to ComponentDef objects for matching.

        Each entry becomes a minimal ComponentDef with:
        - ``library_id`` = refdes (the real reference designator)
        - ``part_name`` = refdes
        - ``value`` from CrossRef CSV
        - ``footprint`` = derived footprint hint
        - Zero pins (to be enriched later by net topology)

        Returns:
            List of ComponentDef objects, one per unique entry.
        """
        seen: set[str] = set()
        result: list[ComponentDef] = []

        for entry in self.all_entries():
            if entry.refdes in seen:
                continue
            seen.add(entry.refdes)

            comp = ComponentDef(
                library_id=entry.refdes,
                part_name=entry.refdes,
                value=entry.value,
                footprint=entry.footprint_hint,
                pin_count=0,
            )
            result.append(comp)

        logger.debug(
            "to_component_defs: produced %d ComponentDef(s) from %d catalog entries",
            len(result),
            len(self._by_refdes),
        )
        return result

    def to_component_instance_irs(self) -> list:
        """Convert all catalog entries to ComponentInstanceIR objects.

        Returns:
            List of ComponentInstanceIR with accurate coordinates,
            refdes, and page assignment from the CrossRef CSV.
        """
        from cis2hdl.core.ir.component import ComponentInstanceIR

        result: list[ComponentInstanceIR] = []
        for entry in self.all_entries():
            inst = ComponentInstanceIR(
                refdes=entry.refdes,
                library_id=entry.refdes,
                loc_x=entry.loc_x,
                loc_y=entry.loc_y,
                value_override=entry.value,
                properties={
                    "page_name": entry.page_name,
                    "schematic_name": entry.schematic_name,
                    "footprint_hint": entry.footprint_hint,
                },
            )
            result.append(inst)

        logger.debug(
            "to_component_instance_irs: produced %d instance(s)",
            len(result),
        )
        return result
