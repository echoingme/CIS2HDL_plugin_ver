from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .base import WriterBase
from ..config import config as cfg
from ..parser.symbol_css import SymbolCssParser

if TYPE_CHECKING:
    from cis2hdl.core.ir.design import PageIR
    from cis2hdl.core.db.component_db import ComponentDB

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  CTW Template DSL data model
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class CTWDevice:
    """A device entry in a CTW circuit template.

    Attributes:
        refdes: Reference designator (e.g. "U1", "R3").
        part_name: HDL library part name.
        x: X coordinate on page.
        y: Y coordinate on page.
    """

    refdes: str
    part_name: str
    x: int = 0
    y: int = 0


@dataclass
class CTWConnection:
    """A net connection in a CTW circuit template.

    Attributes:
        net_name: Name of the net/signal.
        pins: List of "refdes.pin_number" pairs.
    """

    net_name: str
    pins: list[str] = field(default_factory=list)


@dataclass
class CTWReplicate:
    """A device replication directive in a CTW template.

    Attributes:
        refdes: Base reference designator to replicate.
        count: Number of copies.
    """

    refdes: str
    count: int


@dataclass
class CTWTemplate:
    """Parsed CTW circuit template.

    DSL structure::

        BEGIN_CIRCUIT
        BEGIN_DEVICE
          DEVICE <refdes> <part_name> <x> <y>
        END_DEVICE
        BEGIN_CONNECTIONS
          NET <net_name> <refdes>.<pin> ...
        END_CONNECTIONS
        QUERY_REPLICATE_DEVICE <refdes> <count>
    """

    name: str = ""
    devices: list[CTWDevice] = field(default_factory=list)
    connections: list[CTWConnection] = field(default_factory=list)
    replicates: list[CTWReplicate] = field(default_factory=list)


class SCHWriter(WriterBase):
    """Generate .sch page files for Design Entry HDL.

    Translates PageIR (schematic page) into .sch.N.M format files.
    Phase I-B: injects real DSN coordinates (PlacedInstance.locX/Y) when available,
    falls back to auto-layout when coordinates are missing.

    Phase II: adds CTW DSL template support for circuit template-based
    page generation (ROADMAP B2.10).
    """

    FORMAT_NAME = "sch"

    SCH_TEMPLATE = """\
VERSION 6
BEGIN SCHEMATIC
BEGIN ATTR
DeviceFamilyName "{device_family}"
END ATTR
BEGIN NETLIST
{signal_section}
{port_section}
{block_section}
END NETLIST
BEGIN SHEET {page_id} {width} {height}
{instance_section}
{wire_section}
END SHEET
END SCHEMATIC
"""

    def __init__(
        self,
        component_db: "ComponentDB | None" = None,
        use_dsn_coordinates: bool = True,
    ) -> None:
        """Initialize SCH writer.

        Args:
            component_db: Optional ComponentDB for looking up part names.
            use_dsn_coordinates: If True, use real DSN coordinates from PageIR.
                Falls back to auto-layout when coordinates are (0,0) or None.
        """
        self._component_db = component_db
        self._use_dsn_coords = use_dsn_coordinates

    def write(self, page: "PageIR", output_dir: Path) -> list[Path]:
        """Generate a single .sch page file.

        Args:
            page: PageIR instance to convert.
            output_dir: Output directory for the .sch file.

        Returns:
            List containing the generated .sch file path.
        """
        self._ensure_output_dir(output_dir)

        content = self.SCH_TEMPLATE.format(
            device_family=cfg.hdl.device_family,
            signal_section=self._build_signals(page),
            port_section=self._build_ports(page),
            block_section=self._build_blocks(page),
            page_id=page.page_id.replace(".", " "),
            width=page.width,
            height=page.height,
            instance_section=self._build_instances(page),
            wire_section=self._build_wires(page),
        )

        filename = f"top.sch.{page.page_id}"
        output_path = output_dir / filename
        output_path.write_text(content, encoding="utf-8")
        return [output_path]

    # ------------------------------------------------------------------
    #  Internal builders
    # ------------------------------------------------------------------

    def _build_signals(self, page: "PageIR") -> str:
        """Build SIGNAL declarations for the netlist."""
        lines: list[str] = []
        for net in page.nets:
            if net.is_bus and net.bus_members:
                lines.append(f"SIGNAL {net.name}({len(net.bus_members) - 1}:0)")
            else:
                lines.append(f"SIGNAL {net.name}")
        return "\n".join(lines)

    def _build_ports(self, page: "PageIR") -> str:
        """Build PORT declarations for the netlist."""
        lines: list[str] = []
        for port in page.ports:
            if isinstance(port, dict):
                name = port.get("name", "")
                direction = port.get("direction", "BIDIR")
            else:
                name = getattr(port, "name", "")
                direction = getattr(port, "direction", "BIDIR")
            if name:
                lines.append(f"PORT {direction} {name}")
        return "\n".join(lines)

    def _build_blocks(self, page: "PageIR") -> str:
        """Build BEGIN BLOCK / END BLOCK entries for each component."""
        lines: list[str] = []
        for inst in page.instances:
            lib_name = cfg.hdl.default_library_name
            cell_name = self._get_cell_name(inst)
            view_name = "symbol"

            lines.append(
                f"BEGIN BLOCK {inst.refdes} {lib_name} {cell_name} {view_name}"
            )
            for pin_num, net_name in inst.pin_connections.items():
                lines.append(f"  PIN {pin_num} {net_name}")
            lines.append("END BLOCK")
        return "\n".join(lines)

    def _build_instances(self, page: "PageIR") -> str:
        """Build BEGIN INSTANCE / END INSTANCE entries.

        When use_dsn_coordinates is True and instance has real coordinates:
            Uses PlacedInstance.locX/Y directly.
        Otherwise:
            Falls back to auto-layout grid.
        """
        lines: list[str] = []

        # Determine if we have real DSN coordinates
        has_real_coords = self._use_dsn_coords and any(
            inst.loc_x != 0 or inst.loc_y != 0
            for inst in page.instances
        )

        if has_real_coords:
            # Use real DSN coordinates
            for inst in page.instances:
                lines.append(
                    f"BEGIN INSTANCE {inst.refdes} {inst.loc_x} {inst.loc_y} R{inst.rotation}"
                )
                lines.append("END INSTANCE")
        else:
            # Fallback: auto-layout
            x, y = cfg.page.layout_start_x, cfg.page.layout_start_y
            max_x = max(page.width - cfg.page.layout_margin, cfg.page.layout_start_x)

            for inst in page.instances:
                lines.append(f"BEGIN INSTANCE {inst.refdes} {x} {y} R{inst.rotation}")
                lines.append("END INSTANCE")

                x += cfg.page.layout_step_x
                if x > max_x:
                    x = cfg.page.layout_start_x
                    y += cfg.page.layout_step_y

        return "\n".join(lines)

    def _build_wires(self, page: "PageIR") -> str:
        """Build BEGIN WIRE entries from DSN wire segments.

        Each wire segment contains start_x/y, end_x/y coordinates.
        """
        if not page.wires:
            return ""

        lines: list[str] = []
        for wire in page.wires:
            lines.append(
                f"BEGIN WIRE {wire.start_x} {wire.start_y} {wire.end_x} {wire.end_y}"
            )
            lines.append(f"  NET {wire.net_name or 'unnamed'}")
            lines.append("END WIRE")
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════════
    #  CTW DSL Template Support (ROADMAP B2.10)
    # ═══════════════════════════════════════════════════════════════════

    def generate_from_ctw_template(
        self,
        template: CTWTemplate,
        output_dir: Path,
    ) -> list[Path]:
        """Generate HDL schematic pages from a CTW circuit template.

        Parses the CTW mini-DSL:
          - ``BEGIN_DEVICE`` block: device placement
          - ``BEGIN_CONNECTIONS`` block: net wiring
          - ``QUERY_REPLICATE_DEVICE``: device replication

        Each template yields one or more .sch pages.

        Args:
            template: A CTWTemplate parsed from CTW DSL text.
            output_dir: Output directory for the generated .sch files.

        Returns:
            List of generated .sch file paths.
        """
        self._ensure_output_dir(output_dir)
        output_files: list[Path] = []

        # ── Apply replications ─────────────────────────────────────
        devices = list(template.devices)
        for rep in template.replicates:
            base_devices = [d for d in devices if d.refdes == rep.refdes]
            for base in base_devices:
                for i in range(1, rep.count + 1):
                    new_refdes = f"{base.refdes}_{i}"
                    new_x = base.x + (i * cfg.page.layout_step_x)
                    devices.append(CTWDevice(
                        refdes=new_refdes,
                        part_name=base.part_name,
                        x=new_x,
                        y=base.y,
                    ))

        # ── Build page content ─────────────────────────────────────
        page_width = cfg.page.default_width
        page_height = cfg.page.default_height

        # Signal section from connection net names
        net_names: set[str] = set()
        for conn in template.connections:
            net_names.add(conn.net_name)

        signal_lines: list[str] = []
        for name in sorted(net_names):
            signal_lines.append(f"SIGNAL {name}")

        # Block section
        block_lines: list[str] = []
        for dev in devices:
            lib_name = cfg.hdl.default_library_name
            block_lines.append(
                f"BEGIN BLOCK {dev.refdes} {lib_name} {dev.part_name} symbol"
            )
            # Find connections for this device
            for conn in template.connections:
                for pin_ref in conn.pins:
                    if pin_ref.startswith(f"{dev.refdes}."):
                        pin_num = pin_ref[len(dev.refdes) + 1:]
                        block_lines.append(f"  PIN {pin_num} {conn.net_name}")
            block_lines.append("END BLOCK")

        # Instance section
        instance_lines: list[str] = []
        for dev in devices:
            x = dev.x if dev.x != 0 else cfg.page.layout_start_x
            y = dev.y if dev.y != 0 else cfg.page.layout_start_y
            instance_lines.append(f"BEGIN INSTANCE {dev.refdes} {x} {y} R0")
            instance_lines.append("END INSTANCE")

        # Wire section — simple point-to-point for now
        wire_lines: list[str] = []
        for conn in template.connections:
            if len(conn.pins) >= 2:
                p0 = conn.pins[0]
                p1 = conn.pins[1]
                # Approximate wire coordinates from device positions
                d0_refdes = p0.split(".")[0] if "." in p0 else ""
                d1_refdes = p1.split(".")[0] if "." in p1 else ""
                d0 = next((d for d in devices if d.refdes == d0_refdes), None)
                d1 = next((d for d in devices if d1_refdes and d.refdes == d1_refdes), None)

                sx = d0.x if d0 else 100
                sy = d0.y if d0 else 100
                ex = d1.x if d1 else 200
                ey = d1.y if d1 else 100

                wire_lines.append(f"BEGIN WIRE {sx} {sy} {ex} {ey}")
                wire_lines.append(f"  NET {conn.net_name}")
                wire_lines.append("END WIRE")

        # ── Assemble page ───────────────────────────────────────────
        page_id = template.name or "1"
        content = self.SCH_TEMPLATE.format(
            device_family=cfg.hdl.device_family,
            signal_section="\n".join(signal_lines),
            port_section="",
            block_section="\n".join(block_lines),
            page_id=page_id.replace(".", " "),
            width=page_width,
            height=page_height,
            instance_section="\n".join(instance_lines),
            wire_section="\n".join(wire_lines),
        )

        filename = f"top.sch.{page_id}"
        output_path = output_dir / filename
        output_path.write_text(content, encoding="utf-8")
        output_files.append(output_path)

        logger.info(
            "CTW template '%s': generated %d page(s), %d device(s), %d net(s)",
            template.name, len(output_files), len(devices), len(net_names),
        )

        return output_files

    @staticmethod
    def parse_ctw_dsl(text: str) -> CTWTemplate:
        """Parse CTW DSL text into a CTWTemplate data structure.

        The CTW DSL is a mini-language for defining circuit templates::

            BEGIN_CIRCUIT <name>
            BEGIN_DEVICE
              DEVICE <refdes> <part_name> [<x> <y>]
            END_DEVICE
            BEGIN_CONNECTIONS
              NET <net_name> <refdes>.<pin> [<refdes>.<pin> ...]
            END_CONNECTIONS
            [QUERY_REPLICATE_DEVICE <refdes> <count>]

        Args:
            text: Raw CTW DSL text.

        Returns:
            Parsed CTWTemplate instance.
        """
        import re

        template = CTWTemplate()
        current_section: str = ""
        lines = text.strip().splitlines()

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # Section markers
            if line.startswith("BEGIN_CIRCUIT"):
                parts = line.split(maxsplit=1)
                template.name = parts[1] if len(parts) > 1 else ""
                current_section = "circuit"
                continue

            if line == "BEGIN_DEVICE":
                current_section = "device"
                continue

            if line == "BEGIN_CONNECTIONS":
                current_section = "connect"
                continue

            if line == "END_DEVICE" or line == "END_CONNECTIONS":
                current_section = "circuit"
                continue

            # Content lines
            if current_section == "device" and line.startswith("DEVICE"):
                # DEVICE <refdes> <part_name> [<x> <y>]
                parts = line.split()
                if len(parts) >= 3:
                    refdes = parts[1]
                    part_name = parts[2]
                    x = int(parts[3]) if len(parts) >= 4 else 0
                    y = int(parts[4]) if len(parts) >= 5 else 0
                    template.devices.append(CTWDevice(
                        refdes=refdes, part_name=part_name, x=x, y=y,
                    ))

            elif current_section == "connect" and line.startswith("NET"):
                # NET <net_name> <refdes>.<pin> ...
                parts = line.split()
                if len(parts) >= 3:
                    net_name = parts[1]
                    pins = parts[2:]
                    template.connections.append(CTWConnection(
                        net_name=net_name, pins=pins,
                    ))

            elif line.startswith("QUERY_REPLICATE_DEVICE"):
                # QUERY_REPLICATE_DEVICE <refdes> <count>
                parts = line.split()
                if len(parts) >= 3:
                    template.replicates.append(CTWReplicate(
                        refdes=parts[1], count=int(parts[2]),
                    ))

        logger.debug(
            "CTW DSL parsed: %d devices, %d connections, %d replicates",
            len(template.devices), len(template.connections), len(template.replicates),
        )
        return template

    # ── Helpers ──────────────────────────────────────────────────────

    def _get_cell_name(self, inst) -> str:
        """Resolve cell name for a component instance."""
        if self._component_db:
            try:
                comp = self._component_db.get_by_library_id(inst.library_id)
                if comp and comp.part_name:
                    return comp.part_name
            except (KeyError, AttributeError):
                pass

        if inst.library_id:
            return inst.library_id.rsplit("/", 1)[-1]
        return inst.refdes


# ═══════════════════════════════════════════════════════════════════════════════
#  CSA (Cadence Schematic Automation) 格式写入器
# ═══════════════════════════════════════════════════════════════════════════════
#  基于参考库 generate_hdl_sch.py 的 CSA 宏生成逻辑移植
#  生成 DEHDL 可直接编译的 CSA 宏文件 (page1.csa)
#
#  参考:
#    - CIStoHDL_standard/generate_hdl_sch.py (lines 127-249)
#    - CIStoHDL_standard/page1.scr (DEHDL macro format)
#    - CIS2HDL_IMPROVEMENT_DOC.md §3.2.1, §3.2.2, §3.2.3, §3.2.6
# ═══════════════════════════════════════════════════════════════════════════════

# symbol.css 属性偏移默认值（当 symbol.css 不可用时使用）
_DEFAULT_PROP_OFFSETS: dict[str, tuple[int, int, int, int]] = {
    "VALUE": (50, 5, 0, 1),
    "$LOCATION": (-220, 5, 0, 1),
    "PATH": (0, 0, 0, 0),
    "PART_NAME": (0, 0, 0, 0),
    "PACKAGE_TYPE": (0, -15, 0, 1),
    "JEDEC_TYPE": (0, 0, 0, 1),
    "DESCRIPTION": (0, 0, 0, 1),
    "SN_NUM": (0, 0, 0, 1),
}


class SCHWriterCSA(WriterBase):
    """(DEPRECATED) Generate CSA macro files for Design Entry HDL.

    .. deprecated::
        Use ``CSAWriter`` from ``cis2hdl.core.writer.csa_writer`` instead.
        This class is retained only for backward compatibility and will be
        removed in a future release.

    生成 DEHDL 可直接编译的 CSA 宏文件（FORCEADD/FORCEPROP 指令流），
    对齐参考库 `generate_hdl_sch.py` 的 CSA 输出格式。

    特性:
        - C 纸网格布局 (col=idx%5, row=idx//5)
        - symbol.css 驱动的属性定位 (get_prop_offsets)
        - DISPLAY 缩放因子
        - VALUE / $LOCATION 可见属性 (绿色 PAINT)
        - 配套文件生成 (page1.cpc, page1.csv, page.map, master.tag)

    Usage:
        writer = SCHWriterCSA(hdl_lib_path=Path("hdl_lib"))
        files = writer.write(page_ir, output_dir)
    """

    FORMAT_NAME = "sch_csa"

    # ── 布局常量（C 纸坐标系统）───────────────────────────────────
    _COLS: int = 5
    _START_X: int = -10500
    _START_Y: int = 7500
    _SPACING_X: int = 2000
    _SPACING_Y: int = 1500

    def __init__(
        self,
        hdl_lib_path: Path | None = None,
        page_name: str = "DDR3",
        design_name: str = "test",
        library_name: str = "hdl_lib",
    ) -> None:
        """Initialize CSA writer (deprecated).

        Args:
            hdl_lib_path: Path to HDL library root directory
                          (needed for symbol.css lookups).
            page_name: Page name for the generated CSA page.
            design_name: Design name for master.tag and module_order.dat.
            library_name: Library name for CDS_LIB property.
        """
        warnings.warn(
            "SCHWriterCSA is deprecated. Use CSAWriter from "
            "cis2hdl.core.writer.csa_writer instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._hdl_lib_path = hdl_lib_path
        self._page_name = page_name
        self._design_name = design_name
        self._library_name = library_name
        self._css_parser = SymbolCssParser()

    # ------------------------------------------------------------------
    #  公共 API
    # ------------------------------------------------------------------

    def write(self, page: "PageIR", output_dir: Path) -> list[Path]:
        """Generate CSA macro file and supporting files.

        Args:
            page: PageIR instance to convert.
            output_dir: Output directory for the generated files.

        Returns:
            List of all generated file paths.
        """
        self._ensure_output_dir(output_dir)
        output_files: list[Path] = []

        # ── 1. 生成 page1.csa ────────────────────────────────────
        csa_content = self._generate_csa(page)
        csa_path = output_dir / "page1.csa"
        csa_path.write_text(csa_content, encoding="ascii")
        output_files.append(csa_path)

        # ── 2. 配套文件 ─────────────────────────────────────────
        for fname, content in self._generate_support_files().items():
            fpath = output_dir / fname
            fpath.write_text(content, encoding="ascii")
            output_files.append(fpath)

        logger.info(
            "CSA writer: generated %d files for page '%s' (%d instances)",
            len(output_files),
            self._page_name,
            len(page.instances),
        )
        return output_files

    # ------------------------------------------------------------------
    #  CSA 核心生成
    # ------------------------------------------------------------------

    def _generate_csa(self, page: "PageIR") -> str:
        """Generate CSA macro content for a page.

        为每个器件生成 FORCEADD / FORCEPROP / DISPLAY / PAINT 指令。
        """
        lines: list[str] = []
        nl = lines.append

        # ── 文件头 ──────────────────────────────────────────────
        nl("FILE_TYPE = MACRO_DRAWING;")
        nl("SET COLOR_WIRE YELLOW;")
        nl("SET COLOR_PROP ORANGE;")
        nl("SET COLOR_DOT WHITE;")
        nl("SET COLOR_ARC YELLOW;")
        nl("SET COLOR_BODY GREEN;")
        nl("SET COLOR_NOTE PURPLE;")
        nl("SET PROP_DISPLAY VALUE;")
        nl(f"SET PAGE_NUMBER P1;")

        # ── 页面边框 (C SIZE PAGE) ──────────────────────────────
        self._write_page_border(nl)

        # ── 器件列表 ────────────────────────────────────────────
        instances = page.instances
        total = len(instances)

        for idx, inst in enumerate(instances):
            # 计算网格位置
            x, y = self._calc_position(idx, total)

            # 获取器件信息
            body_name = self._resolve_body_name(inst)
            cell_name = body_name.upper()
            refdes = getattr(inst, "refdes", "")
            value = self._resolve_value(inst)

            # symbol.css 属性偏移
            prop_offsets = self._get_prop_offsets(body_name)

            # ── FORCEADD ────────────────────────────────────────
            nl(f"FORCEADD {cell_name}..1")
            nl(f"({x} {y});")

            # ── PATH (隐藏) ─────────────────────────────────────
            po = prop_offsets.get("PATH", (0, 0, 0, 0))
            nl(f"FORCEPROP 1 LAST PATH I{idx + 1}")
            nl("J 0")
            nl(f"({x + po[0]} {y + po[1]});")
            nl(f"DISPLAY {cfg.page.display_scale_transition} ({x + po[0]} {y + po[1]});")
            nl(f"DISPLAY INVISIBLE ({x + po[0]} {y + po[1]});")

            # ── PART_NAME (隐藏) ────────────────────────────────
            pno = prop_offsets.get("PART_NAME", (0, 0, 0, 0))
            primitive = self._resolve_primitive(inst)
            nl(f"FORCEPROP 1 LAST PART_NAME {primitive}")
            nl("J 0")
            nl(f"({x + pno[0]} {y + pno[1]});")
            nl(f"DISPLAY {cfg.page.display_scale_transition} ({x + pno[0]} {y + pno[1]});")
            nl(f"DISPLAY INVISIBLE ({x + pno[0]} {y + pno[1]});")

            # ── JEDEC_TYPE (隐藏) ───────────────────────────────
            jedec = self._resolve_property(inst, "JEDEC_TYPE")
            if jedec:
                jto = prop_offsets.get("JEDEC_TYPE", (0, 0, 0, 1))
                nl(f"FORCEPROP 1 LAST JEDEC_TYPE {jedec}")
                nl("J 0")
                nl(f"({x + jto[0]} {y + jto[1]});")
                nl(f"DISPLAY {cfg.page.display_scale_transition} ({x + jto[0]} {y + jto[1]});")
                nl(f"DISPLAY INVISIBLE ({x + jto[0]} {y + jto[1]});")

            # ── PACKAGE_TYPE (隐藏) ─────────────────────────────
            pkg_type = self._resolve_property(inst, "PACKAGE_TYPE")
            if pkg_type:
                pko = prop_offsets.get("PACKAGE_TYPE", (0, -15, 0, 1))
                nl(f"FORCEPROP 1 LAST PACKAGE_TYPE {pkg_type}")
                nl("J 0")
                nl(f"({x + pko[0]} {y + pko[1]});")
                nl(f"DISPLAY {cfg.page.display_scale_transition} ({x + pko[0]} {y + pko[1]});")
                nl(f"DISPLAY INVISIBLE ({x + pko[0]} {y + pko[1]});")

            # ── SN_NUM (隐藏) ───────────────────────────────────
            sn_num = self._resolve_property(inst, "SN_NUM")
            if sn_num:
                sno = prop_offsets.get("SN_NUM", (0, 0, 0, 1))
                nl(f"FORCEPROP 1 LAST SN_NUM {sn_num}")
                nl("J 0")
                nl(f"({x + sno[0]} {y + sno[1]});")
                nl(f"DISPLAY {cfg.page.display_scale_transition} ({x + sno[0]} {y + sno[1]});")
                nl(f"DISPLAY INVISIBLE ({x + sno[0]} {y + sno[1]});")

            # ── DESCRIPTION (隐藏) ──────────────────────────────
            desc = self._resolve_property(inst, "DESCRIPTION")
            if desc:
                dso = prop_offsets.get("DESCRIPTION", (0, 0, 0, 1))
                nl(f"FORCEPROP 1 LAST DESCRIPTION {desc}")
                nl("J 0")
                nl(f"({x + dso[0]} {y + dso[1]});")
                nl(f"DISPLAY {cfg.page.display_scale_transition} ({x + dso[0]} {y + dso[1]});")
                nl(f"DISPLAY INVISIBLE ({x + dso[0]} {y + dso[1]});")

            # ── VALUE (可见) ────────────────────────────────────
            vo = prop_offsets.get("VALUE", (50, 5, 0, 1))
            nl(f"FORCEPROP 1 LAST VALUE {value}")
            nl("R 1")
            nl("J 1")
            nl(f"({x + vo[0]} {y + vo[1]});")
            nl(f"DISPLAY {cfg.page.display_scale_value} ({x + vo[0]} {y + vo[1]});")

            # ── $LOCATION (可见, 绿色) ──────────────────────────
            lo = prop_offsets.get("$LOCATION", (-220, 5, 0, 1))
            nl(f"FORCEPROP 1 LAST $LOCATION {refdes}")
            nl("R 1")
            nl("J 1")
            nl(f"({x + lo[0]} {y + lo[1]});")
            nl(f"DISPLAY {cfg.page.display_scale_value} ({x + lo[0]} {y + lo[1]});")
            nl(f"PAINT GREEN ({x + lo[0]} {y + lo[1]});")

            # ── CDS_LMAN_SYM_OUTLINE (隐藏, 绿色) ───────────────
            oo = prop_offsets.get("CDS_LMAN_SYM_OUTLINE", (0, 0, 0, 0))
            nl("FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE -50,0,50,-25")
            nl("J 0")
            nl(f"({x + oo[0]} {y + oo[1]});")
            nl(f"DISPLAY {cfg.page.display_scale_outline} ({x + oo[0]} {y + oo[1]});")
            nl(f"PAINT GREEN ({x + oo[0]} {y + oo[1]});")
            nl(f"DISPLAY INVISIBLE ({x + oo[0]} {y + oo[1]});")

            # ── CDS_LIB (隐藏) ──────────────────────────────────
            clo = prop_offsets.get("CDS_LIB", (0, 0, 0, 0))
            nl(f"FORCEPROP 2 LAST CDS_LIB {self._library_name}")
            nl("J 0")
            nl(f"({x + clo[0]} {y + clo[1]});")
            nl(f"DISPLAY INVISIBLE ({x + clo[0]} {y + clo[1]});")

        # ── 结束 ────────────────────────────────────────────────
        nl("QUIT")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    #  页面边框
    # ------------------------------------------------------------------

    def _write_page_border(self, nl) -> None:
        """生成 C SIZE PAGE 页面边框宏。

        C SIZE PAGE..1 边框放在 (-250, 0)，其 outline 覆盖
        x:-10750~0, y:0~8275。器件网格在边框内部。
        """
        nl("FORCEADD C SIZE PAGE..1")
        nl("(-250 0);")
        nl("FORCEPROP 1 LAST COMMENT_BODY TRUE")
        nl("J 0")
        nl("(1750 225);")
        nl(f"DISPLAY 0.872340 (1750 225);")
        nl("PAINT GREEN (1750 225);")
        nl("DISPLAY INVISIBLE (1750 225);")
        nl("FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE -10750,8275,0,0")
        nl("J 0")
        nl("(-250 0);")
        nl(f"DISPLAY {cfg.page.display_scale_outline} (-250 0);")
        nl("PAINT GREEN (-250 0);")
        nl("DISPLAY INVISIBLE (-250 0);")
        nl(f"FORCEPROP 2 LAST CDS_LIB {self._library_name}")
        nl("J 0")
        nl("(-250 0);")
        nl("DISPLAY INVISIBLE (-250 0);")
        nl(f"FORCEPROP 0 LAST EDIT PAGE NAME {self._page_name}")
        nl("J 0")
        nl("(-250 0);")
        nl("DISPLAY INVISIBLE (-250 0);")

    # ------------------------------------------------------------------
    #  网格位置计算
    # ------------------------------------------------------------------

    @classmethod
    def _calc_position(cls, index: int, total: int) -> tuple[int, int]:
        """计算器件网格位置 (col = index % COLS, row = index // COLS).

        对齐参考库 calc_position() 算法。

        Args:
            index: 器件在列表中的零基索引。
            total: 器件总数（保留参数，用于未来优化）。

        Returns:
            (x, y) C 纸坐标。
        """
        _ = total  # reserved for future multi-page splitting
        col = index % cls._COLS
        row = index // cls._COLS
        x = cls._START_X + col * cls._SPACING_X
        y = cls._START_Y - row * cls._SPACING_Y
        return x, y

    # ------------------------------------------------------------------
    #  symbol.css 属性偏移集成 (Task #3 & #6)
    # ------------------------------------------------------------------

    def _get_prop_offsets(self, body_name: str) -> dict[str, tuple[int, int, int, int]]:
        """从 symbol.css 获取属性显示偏移量。

        解析 symbol.css 的 P 指令获取属性 (x, y, rot, just) 偏移。
        对齐参考库 get_prop_offsets() 函数。

        L 指令坐标格式: L x1 y1 x2 y2
        其中 x1/x2 是 offset_x，y1 是 baseline_y。

        Args:
            body_name: HDL 库中的器件目录名（如 "capacitor", "resistor"）。

        Returns:
            {属性名: (offset_x, offset_y, rotation, justification), ...}
            如果 symbol.css 不可用，返回默认偏移。
        """
        if not self._hdl_lib_path:
            return dict(_DEFAULT_PROP_OFFSETS)

        css_path = self._hdl_lib_path / body_name / "sym_1" / "symbol.css"
        if not css_path.exists():
            logger.debug(
                "symbol.css not found for '%s' at %s, using default offsets",
                body_name,
                css_path,
            )
            return dict(_DEFAULT_PROP_OFFSETS)

        try:
            symbol = self._css_parser.parse_file(css_path)
        except Exception as exc:
            logger.warning(
                "Failed to parse symbol.css for '%s': %s, using defaults",
                body_name,
                exc,
            )
            return dict(_DEFAULT_PROP_OFFSETS)

        # 构建偏移字典
        offsets: dict[str, tuple[int, int, int, int]] = dict(_DEFAULT_PROP_OFFSETS)

        for attr in symbol.attributes:
            # 提取旋转和 justification（从 symbol.css P 指令的第 8-9 个 token）
            rot: int = 0
            just: int = 1
            if hasattr(attr, "key"):
                offsets[attr.key] = (
                    int(attr.x),
                    int(attr.y),
                    rot,
                    just,
                )

        # 也从 graphics 中的 L 指令提取额外信息
        for g in symbol.graphics:
            if g.cmd_type == "L" and len(g.params) >= 4:
                # L 指令: L x1 y1 x2 y2
                # 用于确定属性行基线位置
                pass

        return offsets

    # ------------------------------------------------------------------
    #  器件信息解析
    # ------------------------------------------------------------------

    def _resolve_body_name(self, inst) -> str:
        """Resolve HDL body_name (component category directory name).

        Delegates to ``WriterBase._resolve_body_name`` for the core
        library_id / refdes-prefix resolution logic.

        Args:
            inst: ComponentInstanceIR or similar.

        Returns:
            body_name string, e.g. ``"capacitor"``, ``"resistor"``.
        """
        return WriterBase._resolve_body_name(inst)

    def _resolve_primitive(self, inst) -> str:
        """解析器件 primitive 名称（如 CAPACITOR_0201）。

        Args:
            inst: ComponentInstanceIR 或类似对象。

        Returns:
            Primitive 名称。
        """
        # 尝试从 properties 获取
        props = getattr(inst, "properties", {})
        if "PART_NAME" in props:
            return props["PART_NAME"]
        if "part_name" in props:
            return props["part_name"]

        # 从 library_id 或 body_name 构建
        body = self._resolve_body_name(inst)
        return body.upper()

    def _resolve_value(self, inst) -> str:
        """解析器件值（如 "100nF", "10K"）。

        Args:
            inst: ComponentInstanceIR 或类似对象。

        Returns:
            器件值字符串。
        """
        props = getattr(inst, "properties", {})
        if "VALUE" in props:
            return props["VALUE"]
        if "value" in props:
            return props["value"]
        if "Value" in props:
            return props["Value"]
        # Fallback: use library_id
        return getattr(inst, "library_id", "?")

    def _resolve_property(self, inst, prop_name: str) -> str:
        """从器件实例的属性字典中查找指定属性。

        Args:
            inst: ComponentInstanceIR 或类似对象。
            prop_name: 属性名（如 "SN_NUM", "PACKAGE_TYPE"）。

        Returns:
            属性值，或空字符串。
        """
        props = getattr(inst, "properties", {})
        # 大小写不敏感查找
        if prop_name in props:
            return props[prop_name]
        prop_lower = prop_name.lower()
        for key, val in props.items():
            if key.lower() == prop_lower:
                return val
        return ""

    # ------------------------------------------------------------------
    #  配套文件生成
    # ------------------------------------------------------------------

    def _generate_support_files(self) -> dict[str, str]:
        """生成 CSA 模式所需的配套文件。

        Returns:
            {filename: content} 字典。
        """
        files: dict[str, str] = {}

        # page1.cpc — 页面配置
        files["page1.cpc"] = (
            "#ISCELL\n"
            f"  {self._library_name} c#20size#20page *\n"
            "  *\n"
        )

        # page1.csv — 连通性文件
        from datetime import datetime as _dt
        _build_date: str = _dt.now().strftime("%a %b %d %H:%M:%S %Y")
        files["page1.csv"] = (
            "FILE_TYPE = CONNECTIVITY;\n"
            "{Allegro Design Entry HDL 16.6-S115 (v16-6-112JX)} "
            + _build_date + "\n"
            '"PAGE_NUMBER" = 1;\n'
            '0"NC";\n'
            "END.\n"
        )

        # page.map — 页面映射
        files["page.map"] = f"1 1 {self._page_name}\n"

        # master.tag — 项目文件标签
        files["master.tag"] = (
            f"{self._design_name}.csa\n"
            f"{self._design_name}.xcon\n"
            f"{self._design_name}.dcf\n"
        )

        return files
