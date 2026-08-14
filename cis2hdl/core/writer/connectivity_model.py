"""Connectivity model — shared design/page-level structures for DEHDL writers.

Phase XI P0-B/P0-C: con / xcon / csv / cpc / csa must agree on every
identifier — design-level S/T/N/I/M ids (con/xcon), page-local net ids
(csv), page-local instance k (csv ``I<k>`` / cpc ``pageN_i<k>`` / con
internal name).  This module builds that model ONCE from the DesignIR +
match results, so no writer can drift.

Net-scope rules (reverse-engineered from 8367.con evidence, which
overrides the simplified wording in system_design.md A.1.3/C.6):

  * POWER/GROUND nets — every power net gets BOTH:
      - a global record (scope=2, bare lowercase name, e.g. ``gnd_power``)
        that con instance pins reference, and
      - one page-local record per page it appears on (scope=0,
        ``pageN_<name>``) that carries the page connections and is
        aliased to the global record via the con ``(alias)`` / xcon
        ``<aliases>`` sections.
      (8367 evidence: ``vcc_12`` appears on a single page yet has N12
      global + N13 page1_vcc_12 local + alias N13→N12.)
  * FLAT nets — a single bare record (scope=0, lowercase) shared across
    every page it appears on; no aliases.
  * xcon ``<pages>`` net refs always use the BARE name; xcon
    ``<netScopes>`` are emitted for every scope=2 (global) net.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..config import config as cfg
from ..ir.component import ElectricalType, PinDef
from ..net_utils import (
    auto_net_con_name,
    auto_net_csv_name,
    con_name,
    csv_display_name,
    is_power_or_ground,
)

logger = logging.getLogger(__name__)


def _real_page_number(page) -> int:
    """Extract the real physical sheet number from a PageIR.

    Phase XIII T0: the sheet number shown in the title block (and used by
    DEHDL's page.map) comes from the page NAME prefix (``10-SOC_SerDes`` →
    10), NOT the EDIF parse order.  EDIF page blocks are frequently stored
    out of physical order, so ``page_idx + 1`` previously shifted every
    sheet's content by one.  Falls back to the internal page_id suffix
    ("1.5" → 5) and finally to 0 — mirroring
    ``OutputManager._extract_page_number`` so pageN.csa/con/xcon/csv/cpc
    and page.map all agree on the same numbering.
    """
    name: str = getattr(page, "page_name", "") or ""
    m = re.match(r"(\d+)-", name)
    if m:
        return int(m.group(1))
    pid: str = getattr(page, "page_id", "") or ""
    m2 = re.match(r"(\d+)\.(\d+)", pid)
    if m2:
        return int(m2.group(2))
    return 0

#: Power symbols that never appear in con cells/instances (A.1.2)
#: but DO appear in csv/cpc (as #ISCELL) and csa (FORCEADD + LASTPIN).
#: Phase XI P0-遗留#2 (2026-08-10): HG5015's actual source symbol names are
#: ``GND`` / ``DGND`` (not just ``gnd_power``), so the set now includes the
#: raw source spellings; ``cell_for_instance`` normalises them to the hdl_lib
#: symbol names (gnd_power / vcc_circle) for all writers.
POWER_SYMBOL_CELLS: frozenset[str] = frozenset(
    {"gnd", "dgnd", "gnd_power", "vcc_circle", "gnd_earth",
     "gnd_signal", "vcc_bar", "vcc_arrow"}
)

#: EDIF schematic-element library ids (not real components).
_SCHEMATIC_ELEMENT_LIBS: frozenset[str] = frozenset(
    {
        "junction", "bisheet", "onsheet2", "offsheet2", "route",
        "title123", "page_border_template", "off_page", "offpage_l",
        "offpage_r", "nc", "mark", "test_point", "tp",
    }
)


def _direction_digit(etype: ElectricalType) -> int:
    """ElectricalType → con term direction digit (1=input, 2=output, 3=inout)."""
    if etype == ElectricalType.INPUT:
        return 1
    if etype == ElectricalType.OUTPUT:
        return 2
    return 3


# ---------------------------------------------------------------------------
#  Records
# ---------------------------------------------------------------------------


@dataclass
class TermRecord:
    term_id: str
    name: str
    direction: int


@dataclass
class CellRecord:
    cell_id: str
    cell_name: str
    library: str
    sym: str
    terms: list[TermRecord] = field(default_factory=list)
    #: pin_number -> pin_name resolved from the matched ComponentDef
    pin_names: dict[str, str] = field(default_factory=dict)


@dataclass
class NetRecord:
    net_id: str
    internal_name: str
    display_name: str
    scope: int  # 2 = global, 0 = local
    #: bare (unprefixed) internal name — used for csv/con bridging + xcon refs
    bare_name: str = ""
    #: (refdes, pin_number) connections
    connections: list[tuple[str, str]] = field(default_factory=list)
    #: distinct pages this net appears on
    pages: list[int] = field(default_factory=list)


@dataclass
class PinRecord:
    pin_id: str
    term_id: str
    net_id: str
    pin_number: str
    pin_name: str


@dataclass
class InstanceRecord:
    inst_id: str
    internal_name: str
    cell_id: str
    refdes: str
    page_num: int
    page_local_k: int
    pins: list[PinRecord] = field(default_factory=list)
    section: int = 1
    is_power_symbol: bool = False
    #: raw net names for power symbols (for csv/cpc single-pin blocks)
    power_nets: list[str] = field(default_factory=list)
    #: source placement data (carried through for csv/csa coordinates)
    loc_x: int = 0
    loc_y: int = 0
    value: str = ""
    properties: dict = field(default_factory=dict)
    #: HDL cell name (gnd_power / vcc_circle for power symbols).  Power
    #: symbols intentionally have no con cell record, so writers resolve
    #: the block label from this field instead of conn.cells.
    cell_name: str = ""
    #: Phase XI P2-1: placement orientation carried from the source IR so
    #: csa/csv writers can rotate pin offsets / emit the rotated view.
    rotation: int = 0
    mirror: int = 0


@dataclass
class PageNetRecord:
    page_num: int
    local_id: int
    display_name: str
    internal_name: str
    bare_name: str
    is_global: bool
    #: (refdes, pin_number) connections occurring on this page
    connections: list[tuple[str, str]] = field(default_factory=list)
    #: design-level net id this page net bridges to
    net_id: str = ""
    #: design-level net id that instance pins reference for this net
    #: (global id for power nets — con pins point at the global record)
    pin_net_id: str = ""


@dataclass
class PageConnectivity:
    page_num: int
    page_name: str
    instances: list[InstanceRecord] = field(default_factory=list)
    nets: list[PageNetRecord] = field(default_factory=list)
    inst_by_local_k: dict[int, InstanceRecord] = field(default_factory=dict)
    net_by_bare: dict[str, PageNetRecord] = field(default_factory=dict)
    #: Phase XI P0-C5: cross-page connectors on this page (from the source
    #: PageIR.off_pages) — consumed by csa_writer for IOPORT symbols.
    off_pages: list[dict] = field(default_factory=list)


@dataclass
class DesignConnectivity:
    cell_name: str
    library_alias: str
    hdl_lib_name: str
    cells: list[CellRecord] = field(default_factory=list)
    nets: list[NetRecord] = field(default_factory=list)
    instances: list[InstanceRecord] = field(default_factory=list)
    pages: list[PageConnectivity] = field(default_factory=list)
    #: (local_internal, global_internal) alias pairs
    aliases: list[tuple[str, str]] = field(default_factory=list)
    net_by_internal: dict[str, NetRecord] = field(default_factory=dict)
    net_by_bare: dict[str, NetRecord] = field(default_factory=dict)
    #: raw (pre-normalization) net name → NetRecord (Phase XI P0-遗留#3:
    #: $-prefixed auto-nets are normalized to UN$ names, but instance
    #: pin_connections still carry the raw "$47N777" spelling; this map
    #: lets _pin_net_record resolve them without losing pins).
    net_by_raw: dict[str, NetRecord] = field(default_factory=dict)
    inst_by_refdes: dict[str, InstanceRecord] = field(default_factory=dict)
    global_net_names: set[str] = field(default_factory=set)
    #: source DesignIR (Phase XIV D5: EDIFWireRouter needs the page's
    #: source polylines to reuse them; set by ConnectivityModelBuilder).
    design: object = None

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    @property
    def net_count(self) -> int:
        return len(self.nets)

    @property
    def instance_count(self) -> int:
        return len(self.instances)

    @property
    def pin_count(self) -> int:
        return sum(len(i.pins) for i in self.instances)


# ---------------------------------------------------------------------------
#  Builder
# ---------------------------------------------------------------------------


class ConnectivityModelBuilder:
    """Build DesignConnectivity from DesignIR + match results.

    Args:
        design: The parsed DesignIR (EDIF-sourced under P0-D2).
        matches: List of MatchResult (or objects with source_library_id /
            target_library_id).  Used to resolve cell names + pin definitions.
        hdl_db: Optional ComponentDB for looking up matched ComponentDefs.
        hdl_lib_name: HDL library name (default "hdl_lib").
    """

    def __init__(
        self,
        design,
        matches: Optional[list] = None,
        hdl_db=None,
        hdl_lib_name: str = "hdl_lib",
    ) -> None:
        self._design = design
        self._matches = matches or []
        self._hdl_db = hdl_db
        self._hdl_lib_name = hdl_lib_name
        # source_library_id -> (cell_name, ComponentDef|None)
        self._match_lookup: dict[str, tuple[str, Optional[object]]] = {}
        self._build_match_lookup()

    # ------------------------------------------------------------------
    #  Match lookup
    # ------------------------------------------------------------------

    def _build_match_lookup(self) -> None:
        for m in self._matches:
            sid = getattr(m, "source_library_id", "")
            tid = getattr(m, "target_library_id", "")
            if not sid or not tid:
                continue
            cell = tid.rsplit("/", 1)[-1]
            comp = None
            if self._hdl_db is not None:
                try:
                    comp = self._hdl_db.get_by_library_id(tid)
                except Exception:
                    comp = None
            self._match_lookup[sid] = (cell, comp)

    def cell_for_instance(self, inst) -> tuple[str, Optional[object]]:
        """Resolve (cell_name, ComponentDef) for an instance."""
        lib_id = getattr(inst, "library_id", "") or ""
        if lib_id in self._match_lookup:
            return self._match_lookup[lib_id]
        cell = lib_id.rsplit("/", 1)[-1] if "/" in lib_id else lib_id
        # Phase XI P0-遗留#2: normalise power symbol source names to the
        # hdl_lib symbol names so csv/cpc/csa emit the DEHDL cell that
        # actually exists (GND/DGND → gnd_power, VCC_CIRCLE → vcc_circle).
        # The net name / HDL_POWER keeps the source spelling (e.g. GND).
        lower = cell.lower()
        if lower in POWER_SYMBOL_CELLS:
            if lower in ("gnd", "dgnd", "gnd_power", "gnd_earth",
                         "gnd_signal", "gnd_chassis"):
                cell = "gnd_power"
            elif lower in ("vcc_circle", "vcc_bar", "vcc_arrow"):
                cell = "vcc_circle"
        return (cell, None)

    @staticmethod
    def _power_net_for_symbol(inst) -> str:
        """Derive the power net name for a 0-pin power symbol instance.

        GND/DGND symbols → ``"GND"`` (EDIF POWER_TYPE/NETNAME properties are
        both "GND"); VCC_CIRCLE → the instance refdes (OrCAD stores the net
        name there, e.g. ``&3V3_SOC`` → ``3V3_SOC``) or the NETNAME property;
        returns "" when the net cannot be identified (symbol is skipped).
        """
        lib_id = (getattr(inst, "library_id", "") or "").lower()
        props = getattr(inst, "properties", {}) or {}
        if lib_id in ("gnd", "dgnd", "gnd_power", "gnd_earth",
                      "gnd_signal", "gnd_chassis"):
            return "GND"
        if lib_id in ("vcc_circle", "vcc_bar", "vcc_arrow"):
            refdes = (getattr(inst, "refdes", "") or "").strip()
            if refdes:
                return refdes.lstrip("&")
            netname = (props.get("NETNAME") or props.get("netname") or "").strip()
            if netname:
                return netname.lstrip("&")
        return ""

    # ------------------------------------------------------------------
    #  Main entry
    # ------------------------------------------------------------------

    def build(self) -> DesignConnectivity:
        design = self._design
        project_name = getattr(design, "project_name", "") or "project"
        # Cell name must match OutputManager's derived short name (e.g.
        # "HG5015-BE36_V10" → "5015") so con/xcon files are named like the
        # worklib cell directory.
        cell_name = cfg.output.derive_cell_name(project_name) or project_name
        conn = DesignConnectivity(
            cell_name=cell_name,
            library_alias=f"{cell_name}_lib",
            hdl_lib_name=self._hdl_lib_name,
            design=design,
        )

        # ── 1. Collect real component instances (skip schematic elements) ──
        page_insts: list[list] = []
        for page in design.pages:
            kept = []
            for inst in page.instances:
                lib_id = (getattr(inst, "library_id", "") or "").lower()
                refdes = getattr(inst, "refdes", "") or ""
                if lib_id in _SCHEMATIC_ELEMENT_LIBS:
                    continue
                # EDIF internal instance placeholders (INS###) are not
                # real components
                import re as _re
                if _re.match(r"^ins\d+$", refdes.lower()):
                    continue
                kept.append(inst)
            # Phase XI P0-遗留#2: one power symbol per (page, power net).
            # Raw EDIF portImplementation blocks contain many duplicates
            # (e.g. page14 has 64 GND instances) but a page only needs one
            # symbol per net (8367 evidence).  The derived net is stashed on
            # extra_data so step 5 can fill InstanceRecord.power_nets.
            seen_power_nets: set[str] = set()
            deduped: list = []
            for inst in kept:
                lib_id = (getattr(inst, "library_id", "") or "").lower()
                if lib_id in POWER_SYMBOL_CELLS:
                    net = self._power_net_for_symbol(inst)
                    if not net:
                        continue  # unidentifiable power symbol → skip
                    key = net.lower()
                    if key in seen_power_nets:
                        continue
                    seen_power_nets.add(key)
                    extra = getattr(inst, "extra_data", None)
                    if isinstance(extra, dict):
                        extra["power_net"] = net
                deduped.append(inst)
            page_insts.append(deduped)

        # Phase XIII T0: physical page numbers come from the page NAME
        # prefix (e.g. "10-SOC_SerDes" → 10), matching OutputManager's
        # page.map numbering.  EDIF page blocks are frequently out of
        # physical order, so all downstream indexing sorts by the real
        # number — this keeps pageN.csa / con / xcon / csv / cpc and
        # page.map aligned (1=01-Cover_Page ... 24=24-LED_KEY).
        page_nums: list[int] = [_real_page_number(p) for p in design.pages]
        page_order: list[int] = sorted(
            range(len(design.pages)), key=lambda i: page_nums[i]
        )

        # ── 2. Build cells (unique cell_name × section) ───────────────────
        cell_key_to_record: dict[tuple[str, int], CellRecord] = {}
        cell_key_order: list[tuple[str, int]] = []

        def _get_cell(key: tuple[str, int]) -> CellRecord:
            if key not in cell_key_to_record:
                rec = CellRecord(
                    cell_id=f"S{len(cell_key_to_record) + 1}",
                    cell_name=key[0],
                    library=self._hdl_lib_name,
                    sym=f"sym_{key[1]}",
                )
                cell_key_to_record[key] = rec
                cell_key_order.append(key)
            return cell_key_to_record[key]

        for kept in page_insts:
            for inst in kept:
                cell_name_i, _comp = self.cell_for_instance(inst)
                if not cell_name_i:
                    continue
                # Phase XI P0-遗留#2: power symbols never become con cells
                # (C.5 convention — they only appear in csv/cpc/csa).
                if cell_name_i.lower() in POWER_SYMBOL_CELLS:
                    continue
                section = int(getattr(inst, "section", 1) or 1)
                _get_cell((cell_name_i, section))

        # Populate terms after all cells are known (contiguous T ids)
        term_counter = 0
        for key in cell_key_order:
            rec = cell_key_to_record[key]
            comp = self._first_component_for_cell(page_insts, key[0])
            terms, pin_names = self._build_terms(comp, term_counter)
            if not terms:
                # Fallback: synthesize terms from instances' pin numbers
                # (cells without a matched ComponentDef pin list)
                pin_numbers: set[str] = set()
                for kept in page_insts:
                    for inst in kept:
                        if self.cell_for_instance(inst)[0] != key[0]:
                            continue
                        pin_numbers.update(
                            (getattr(inst, "pin_connections", {}) or {}).keys()
                        )
                for pn in sorted(pin_numbers, key=lambda s: (len(s), s)):
                    terms.append(TermRecord(
                        term_id=f"T{term_counter + len(terms) + 1}",
                        name=pn,
                        direction=3,
                    ))
                    pin_names[pn] = pn
            term_counter += len(terms)
            rec.terms = terms
            rec.pin_names = pin_names

        conn.cells = [cell_key_to_record[k] for k in cell_key_order]

        # ── 3. Raw nets from instance pin_connections ─────────────────────
        raw_conns: dict[str, list[tuple[str, str]]] = defaultdict(list)
        raw_pages: dict[str, set[int]] = defaultdict(set)
        for page_idx in page_order:
            kept = page_insts[page_idx]
            page_num = page_nums[page_idx]
            for inst in kept:
                refdes = getattr(inst, "refdes", "")
                for pin, net_name in (getattr(inst, "pin_connections", {}) or {}).items():
                    if not net_name:
                        continue
                    raw_conns[net_name].append((refdes, pin))
                    raw_pages[net_name].add(page_num)

        # ── 4. Design-level nets (global + per-page local for power) ──────
        def _net_sort_key(name: str):
            return (0 if is_power_or_ground(name) else 1, name.lower())

        inst_page: dict[str, int] = {}
        for page_idx in page_order:
            for inst in page_insts[page_idx]:
                inst_page.setdefault(
                    getattr(inst, "refdes", ""), page_nums[page_idx]
                )

        # Phase XI P0-遗留#3（2026-08-10）：OrCAD EDIF 自动网名（$47N777 等）
        # 应转换为 UN$<page>$<CELL>$<I<k>>$<pin> 形式（con 内部名
        # unnamed_<page>_<cell>_i<k>_<pin>），而不是简单清洗成数字开头网名。
        # 依据：8367 真实工程 unnamed_1_capacitor_i12_1 ↔ UN$1$CAPACITOR$I12$1。
        inst_k_map: dict[str, int] = {}   # refdes -> page-local k
        inst_cell_map: dict[str, str] = {}  # refdes -> cell name
        for page_idx in page_order:
            for k, inst in enumerate(page_insts[page_idx], start=1):
                refdes = getattr(inst, "refdes", "")
                inst_k_map.setdefault(refdes, k)
                cell_nm, _ = self.cell_for_instance(inst)
                inst_cell_map.setdefault(refdes, cell_nm or "unknown")

        def _auto_net_internal(raw_name: str) -> str | None:
            """Return the UN$ internal name for OrCAD auto-nets ($-prefixed),
            else None.  Uses the first connection's (refdes, pin) to derive
            page / cell / instance-k / pin (8367-style)."""
            stripped = raw_name.strip()
            if not stripped.startswith("$"):
                return None
            conns = raw_conns.get(stripped) or raw_conns.get(raw_name) or []
            if not conns:
                return None
            refdes, pin = conns[0]
            page = inst_page.get(refdes, 0)
            k = inst_k_map.get(refdes, 0)
            cell = (inst_cell_map.get(refdes, "") or "").lower()
            if not page or not k or not cell:
                return None
            return auto_net_con_name(page, cell, k, pin)

        for raw_name in sorted(raw_conns.keys(), key=_net_sort_key):
            pages = sorted(raw_pages[raw_name])
            bare = con_name(raw_name)
            display = csv_display_name(raw_name, is_global=True) if is_power_or_ground(raw_name) else raw_name
            # Phase XI P0-遗留#3: convert $-prefixed auto-nets to UN$ form
            auto_internal = _auto_net_internal(raw_name)
            if auto_internal:
                bare = auto_internal
                display = auto_net_csv_name(auto_internal)

            if is_power_or_ground(raw_name):
                # global record (alias target) — con instance pins reference it
                global_rec = NetRecord(
                    net_id=f"N{len(conn.nets) + 1}",
                    internal_name=bare,
                    display_name=display,
                    scope=2,
                    bare_name=bare,
                    connections=list(raw_conns[raw_name]),
                    pages=pages,
                )
                conn.nets.append(global_rec)
                conn.net_by_internal[bare] = global_rec
                conn.net_by_bare[bare] = global_rec
                conn.net_by_raw[raw_name] = global_rec
                conn.global_net_names.add(bare)
                # per-page local records + aliases
                for page_num in pages:
                    local_name = con_name(raw_name, page=page_num, local=True)
                    local_rec = NetRecord(
                        net_id=f"N{len(conn.nets) + 1}",
                        internal_name=local_name,
                        display_name=display,
                        scope=0,
                        bare_name=bare,
                        connections=[
                            c for c in raw_conns[raw_name]
                            if inst_page.get(c[0], -1) == page_num
                        ],
                        pages=[page_num],
                    )
                    conn.nets.append(local_rec)
                    conn.net_by_internal[local_name] = local_rec
                    conn.net_by_bare[bare] = local_rec
                    conn.net_by_raw[raw_name] = local_rec
                    conn.aliases.append((local_name, bare))
            else:
                flat_rec = NetRecord(
                    net_id=f"N{len(conn.nets) + 1}",
                    internal_name=bare,
                    display_name=display,
                    scope=0,
                    bare_name=bare,
                    connections=list(raw_conns[raw_name]),
                    pages=pages,
                )
                conn.nets.append(flat_rec)
                conn.net_by_internal[bare] = flat_rec
                conn.net_by_bare[bare] = flat_rec
                conn.net_by_raw[raw_name] = flat_rec

        # ── 5. Instances (k page-local shared incl. power symbols; ────────
        #        con I ids exclude power symbols) ──────────────────────────
        pin_counter = 0
        for page_idx in page_order:
            kept = page_insts[page_idx]
            page_num = page_nums[page_idx]
            page_conn = PageConnectivity(
                page_num=page_num,
                page_name=design.pages[page_idx].page_name,
                # Phase XI P0-C5: carry page off-page connectors for
                # IOPORT symbol generation in csa_writer.
                off_pages=list(getattr(
                    design.pages[page_idx], "off_pages", []
                ) or []),
            )
            for k, inst in enumerate(kept, start=1):
                refdes = getattr(inst, "refdes", "")
                cell_name_i, _comp = self.cell_for_instance(inst)
                if not cell_name_i:
                    cell_name_i = "unknown"
                section = int(getattr(inst, "section", 1) or 1)
                is_power = cell_name_i.lower() in POWER_SYMBOL_CELLS
                cell_rec = cell_key_to_record.get((cell_name_i, section))
                irec = InstanceRecord(
                    inst_id="",  # assigned below for non-power instances
                    internal_name=f"page{page_num}_i{k}",
                    cell_id=cell_rec.cell_id if cell_rec else (
                        f"S{len(conn.cells) + 1}" if not is_power else ""
                    ),
                    refdes=refdes,
                    page_num=page_num,
                    page_local_k=k,
                    section=section,
                    is_power_symbol=is_power,
                    loc_x=int(getattr(inst, "loc_x", 0) or 0),
                    loc_y=int(getattr(inst, "loc_y", 0) or 0),
                    value=(getattr(inst, "value_override", "") or ""),
                    properties=dict(getattr(inst, "properties", {}) or {}),
                    cell_name=cell_name_i,
                    # Phase XI P2-1: placement orientation from the source
                    # IR (EDIF transform orientation).
                    rotation=int(getattr(inst, "rotation", 0) or 0),
                    mirror=int(getattr(inst, "mirror", 0) or 0),
                )
                for pin, net_name in (getattr(inst, "pin_connections", {}) or {}).items():
                    if not net_name:
                        continue
                    if is_power:
                        irec.power_nets.append(net_name)
                    net_rec = self._pin_net_record(conn, net_name, page_num)
                    if net_rec is None:
                        continue
                    term_id, pin_name = self._resolve_term(cell_rec, pin)
                    # Phase XXI D（用户 Cadence 16.6 实测 P6）：未匹配 cell
                    # 的引脚名回退到引脚号（_resolve_term → pin）时，用
                    # pstchip 真实功能名（AMS1117 → GND/OUTPUT/INPUT/TAP）
                    # 显示在 mock 图标上（替代 1-8 数字名）。
                    # Phase XXI D 增强（08-14）：错误 fallback（如 IC3 →
                    # CH347）时 _resolve_term 用 fallback cell 解析出错误
                    # 引脚名（RST#/CTS/GPIO6…）—— 只要 pstchip 存在该
                    # 引脚号的真实名且与当前名不一致，就按引脚号覆盖为
                    # pstchip 名（AMS1117 → GND/OUTPUT/INPUT/TAP）。
                    _pst_names = (
                        getattr(inst, "extra_data", {}) or {}
                    ).get("pstchip_pin_names")
                    if (_pst_names and str(pin) in _pst_names
                            and pin_name != str(_pst_names[str(pin)])):
                        pin_name = str(_pst_names[str(pin)])
                    pin_counter += 1
                    irec.pins.append(PinRecord(
                        pin_id=f"M{pin_counter}",
                        term_id=term_id,
                        net_id=net_rec.net_id,
                        pin_number=pin,
                        pin_name=pin_name,
                    ))
                # Phase XXI D（用户 Cadence 16.6 实测 P6）：EDIF 网名空且
                # pstxnet 未覆盖的实例（如 AMS1117→IC3）pin_connections 空
                # → irec.pins 空 → mock 占位 1-8 数字名。pstchip.dat
                # primitive 已由 conversion_engine 存入 extra_data
                # ["pstchip_pin_names"]（{引脚号: 真实功能名}）—— 这里恢复
                # 真实引脚名（如 IC3 → GND/OUTPUT/INPUT/TAP）。net_id 空
                # （无网数据）：LASTPIN 照常发射（引脚存在）、不生成 WIRE
                # （悬空，pin_audit [HANGING] 标注）。csv/con 写入器对
                # 空 net_id 均安全跳过。
                if (not irec.pins and not is_power):
                    _pst_pins = (
                        getattr(inst, "extra_data", {}) or {}
                    ).get("pstchip_pin_names")
                    if _pst_pins:
                        for _num in sorted(
                            _pst_pins,
                            key=lambda v: (
                                int(v) if str(v).isdigit() else 0,
                            ),
                        ):
                            pin_counter += 1
                            irec.pins.append(PinRecord(
                                pin_id=f"M{pin_counter}",
                                term_id="T0",
                                net_id="",
                                pin_number=str(_num),
                                pin_name=str(_pst_pins[_num]),
                            ))
                # Phase XI P0-遗留#2: 0-pin power symbols (GND/VCC_CIRCLE)
                # have no pin_connections, so power_nets must be derived from
                # their attributes (GND → "GND"; VCC_CIRCLE → refdes/NETNAME).
                if is_power and not irec.pins:
                    _extra = getattr(inst, "extra_data", None) or {}
                    _pnet = _extra.get("power_net") if isinstance(_extra, dict) else ""
                    if not _pnet:
                        _pnet = self._power_net_for_symbol(inst)
                    if _pnet:
                        irec.power_nets.append(_pnet)
                page_conn.instances.append(irec)
                page_conn.inst_by_local_k[k] = irec
                if not is_power:
                    irec.inst_id = f"I{len(conn.instances) + 1}"
                    conn.instances.append(irec)
                    conn.inst_by_refdes[refdes] = irec
            conn.pages.append(page_conn)

        # ── 6. Page-level nets (csv numbering; power/global first) ────────
        for page_conn in conn.pages:
            page_num = page_conn.page_num
            # gather page nets: for power nets use the page-local record,
            # for flat nets the bare record
            page_net_records: list[NetRecord] = []
            seen_ids: set[str] = set()
            for irec in page_conn.instances:
                for pre in irec.pins:
                    nr = conn.net_by_internal.get(
                        self._page_net_internal(conn, pre.net_id, page_num)
                    )
                    if nr is None or nr.net_id in seen_ids:
                        continue
                    seen_ids.add(nr.net_id)
                    page_net_records.append(nr)
            # fallback: nets whose connections live on this page
            for nr in conn.nets:
                if nr.net_id in seen_ids:
                    continue
                if page_num in nr.pages and nr.scope == 0:
                    seen_ids.add(nr.net_id)
                    page_net_records.append(nr)

            def _page_sort_key(nr: NetRecord):
                return (0 if nr.scope == 2 else 1, nr.internal_name)

            local_id = 0  # 0 = NC placeholder
            for nr in sorted(page_net_records, key=_page_sort_key):
                local_id += 1
                # design-level net id that instance pins reference:
                # power nets → the global (scope=2) record; flat → itself
                pin_net_id = nr.net_id
                if nr.scope == 0 and is_power_or_ground(nr.bare_name):
                    global_rec = conn.net_by_internal.get(nr.bare_name)
                    if global_rec is not None and global_rec.scope == 2:
                        pin_net_id = global_rec.net_id
                pnr = PageNetRecord(
                    page_num=page_num,
                    local_id=local_id,
                    display_name=nr.display_name,
                    internal_name=nr.internal_name,
                    bare_name=nr.bare_name,
                    is_global=(nr.scope == 2),
                    connections=[
                        c for c in nr.connections
                        if inst_page.get(c[0], -1) == page_num
                    ],
                    net_id=nr.net_id,
                    pin_net_id=pin_net_id,
                )
                page_conn.nets.append(pnr)
                page_conn.net_by_bare[nr.bare_name] = pnr

        return conn

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _first_component_for_cell(self, page_insts: list[list], cell_name: str) -> Optional[object]:
        """Return the first matched ComponentDef seen for a cell name."""
        for kept in page_insts:
            for inst in kept:
                cell_i, comp = self.cell_for_instance(inst)
                if cell_i == cell_name and comp is not None:
                    return comp
        return None

    @staticmethod
    def _build_terms(comp, start: int) -> tuple[list[TermRecord], dict[str, str]]:
        """Build term records + pin_number→name map from a ComponentDef.

        Terms are sorted by pin NAME alphabetically (8367 evidence); T ids
        are contiguous from ``start + 1``.  Empty when the component has no
        pin definitions (callers fall back gracefully).
        """
        terms: list[TermRecord] = []
        pin_names: dict[str, str] = {}
        if comp is None:
            return terms, pin_names
        pins: list[PinDef] = list(getattr(comp, "pins", []) or [])
        if not pins:
            return terms, pin_names
        for p in pins:
            name = p.name or str(p.number)
            pin_names[str(p.number)] = name
            pin_names[name] = name
        for idx, p in enumerate(sorted(pins, key=lambda x: (x.name or "").lower())):
            terms.append(TermRecord(
                term_id=f"T{start + idx + 1}",
                name=p.name or str(p.number),
                direction=_direction_digit(p.type),
            ))
        return terms, pin_names

    def _resolve_term(self, cell_rec: Optional[CellRecord], pin: str) -> tuple[str, str]:
        """Resolve (term_id, pin_name) for a pin number/label within a cell."""
        if cell_rec is None or not cell_rec.terms:
            return "T0", pin
        pin_name = cell_rec.pin_names.get(pin, pin)
        for t in cell_rec.terms:
            if t.name == pin_name or t.name == pin:
                return t.term_id, pin_name
        return cell_rec.terms[0].term_id, pin_name

    def _pin_net_record(
        self, conn: DesignConnectivity, raw_net_name: str, page_num: int
    ) -> Optional[NetRecord]:
        """Locate the con net record an instance pin should reference.

        Power nets → the global (bare, scope=2) record; flat nets → the
        bare scope=0 record.
        """
        # Phase XI P0-遗留#3: prefer the raw-name map — $-prefixed auto-nets
        # are normalized to UN$ names in the internal map, so a bare
        # con_name() lookup would miss them and drop pins.
        rec = conn.net_by_raw.get(raw_net_name)
        if rec is not None:
            if rec.scope == 0 and is_power_or_ground(rec.bare_name):
                global_rec = conn.net_by_internal.get(rec.bare_name)
                if global_rec is not None:
                    return global_rec
            return rec
        bare = con_name(raw_net_name)
        if is_power_or_ground(raw_net_name):
            rec = conn.net_by_internal.get(bare)
            if rec is not None:
                return rec
        # flat: bare record
        rec = conn.net_by_internal.get(bare)
        if rec is not None:
            return rec
        # fallback: page-local match
        local_name = con_name(raw_net_name, page=page_num, local=True)
        return conn.net_by_internal.get(local_name)

    def _page_net_internal(self, conn: DesignConnectivity, net_id: str, page_num: int) -> str:
        """Return the page-level internal name for a design net id.

        Power nets → ``page<page>_<bare>``; flat nets → bare.
        """
        for nr in conn.nets:
            if nr.net_id == net_id:
                if nr.scope == 2:
                    return con_name(nr.bare_name, page=page_num, local=True)
                return nr.internal_name
        return ""
