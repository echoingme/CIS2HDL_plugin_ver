"""CSA writer — generates DEHDL native .csa page files.

The .csa format (FILE_TYPE = MACRO_DRAWING) is the native DEHDL format
that Cadence Concept HDL reads directly.  Each page generates a
FORCEADD/FORCEPROP/DISPLAY/PAINT macro sequence.

Reference format from worklib/8367/sch_1/page1.csa:
    FILE_TYPE = MACRO_DRAWING;
    SET COLOR_WIRE YELLOW;
    SET COLOR_PROP MONO;
    SET COLOR_DOT WHITE;
    SET COLOR_ARC YELLOW;
    SET COLOR_BODY GREEN;
    SET COLOR_NOTE MONO;
    SET PROP_DISPLAY VALUE;
    SET PAGE_NUMBER P1;
    FORCEADD DC_DC..1
    (-5350 6675);
    FORCEPROP 1 LAST VALUE SY8113BADC
    J 0
    (-5500 6425);
    DISPLAY 0.851064 (-5500 6425);
    PAINT ORANGE (-5500 6425);
    ...

This replaces CPCWriter — .cpc files are not the DEHDL native format.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .base import WriterBase
from .coord_transform import rotate_point
from .output_manager import OutputManager

if TYPE_CHECKING:
    from cis2hdl.core.config import RoutingConfig
    from cis2hdl.core.ir.design import PageIR, DesignIR
    from cis2hdl.core.db.component_db import ComponentDB
    from .aesthetic_report import AestheticReport
    from .ioport_audit import IOPortAuditor
    from .router_base import WireRouterBase
    from .text_layout import TextLayoutOptimizer

logger = logging.getLogger(__name__)

# ── DISPLAY scale factors (from DEHDL page1.scr internal rendering) ─────
_SCALE_VALUE: float = 0.851064       # VALUE / $LOCATION / LOCATION
_SCALE_OUTLINE: float = 0.468085     # CDS_LMAN_SYM_OUTLINE
_SCALE_TRANSITION: float = 1.021277  # Invisible properties (transition before hide)
_SCALE_SIG_NAME: float = 0.659574    # SIG_NAME pin labels
_SCALE_PN: float = 0.808511          # $PN pin numbers
_SCALE_SEC: float = 0.680851         # $SEC / section display
#: Phase XXI B（用户 P5"做成标签的方式比较大个显示、可改颜色"）：MOCK_TEXT
#: 实例属性标签的 DISPLAY 缩放 ≥1.5（远大于 VALUE 0.85 → 大字醒目）。
_SCALE_MOCK_TEXT: float = 1.5
#: IOPORT/INPORT block label scale (04p4 page15.csa evidence: every
#: PATH/HDL_PORT/VHDL_PORT label uses 0.872340).
_SCALE_IOPORT: float = 0.872340

# ── PAINT colours ───────────────────────────────────────────────────────
_PAINT_ORANGE: str = "ORANGE"
_PAINT_GREEN: str = "GREEN"
_PAINT_MONO: str = "MONO"
_PAINT_PINK: str = "PINK"

# ── Grid layout defaults (when DSN coordinates are absent) ──────────────
_GRID_START_X: int = -10500
_GRID_START_Y: int = 7500
_GRID_STEP_X: int = 2000
_GRID_STEP_Y: int = 1500
_GRID_COLS: int = 5


def _dehdl_rotation(edif_rotation: int) -> int:
    """Map an EDIF rotation angle to the DEHDL ``R n`` line angle.

    Phase XV P0-E (Cadence 16.6 user feedback): an instance whose EDIF
    ``(orientation R90)`` is emitted as DEHDL ``R 1`` renders **flipped
    180°** — the pin order comes out swapped (verified on L20:
    EDIF R90, our ``R 1`` put pin 1 on the right / pin 2 on the left;
    the user saw "右边的引脚拉出来的线连到了左边的芯片").

    OrCAD Capture's EDIF orientation uses the opposite angular sign to
    DEHDL's ``R n`` convention, so a 90° source rotation must render as
    the 270° DEHDL view (and vice versa); 180° is its own inverse and
    stays unchanged.

    Args:
        edif_rotation: Source rotation in degrees (0/90/180/270).

    Returns:
        DEHDL ``R``-line angle (0/90/180/270).
    """
    rot = int(edif_rotation or 0) % 360
    if rot == 90:
        return 270
    if rot == 270:
        return 90
    return rot


#: Phase XXII D7: 标签方向 R 行（dehdl 旋转角 → DEHDL R n）。
_LABEL_R_LINE: dict[int, int] = {90: 1, 180: 2, 270: 3}


def _is_horizontal_view(offsets: dict) -> bool:
    """判定 sym_N 视图是否为横向（Q2 方案 A 启发式）。

    横向判定：全部引脚 offset 同 y（如 capacitor sym_2
    ``{"1": (-50, 0), "2": (75, 0)}``），或 x 方差 > y 方差 3 倍
    （x 方向主导）。非横向（如 sym_1 竖直 ``(0,-75)/(0,50)``）视为
    变体视图，禁止误切换。

    Args:
        offsets: ``{pin: (x, y)}`` symbol.css C 指令偏移表。

    Returns:
        True = 横向视图（可安全切换）。
    """
    pts = list((offsets or {}).values())
    if len(pts) < 2:
        return False
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    if all(y == ys[0] for y in ys):
        return True
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs) / len(xs)
    vy = sum((y - my) ** 2 for y in ys) / len(ys)
    return vx > 3.0 * vy


class CSAWriter(WriterBase):
    """Generate DEHDL native .csa page files (MACRO_DRAWING format).

    Writes FORCEADD / FORCEPROP / DISPLAY / PAINT macros for each
    component instance on every schematic page.  Files are placed at
    ``worklib/<cell>/sch_1/pageN.csa``.

    The writer uses an OutputManager for directory layout and writes
    one .csa file per page, plus the supporting .con and module_order.dat
    files via OutputManager methods.
    """

    FORMAT_NAME: str = "csa"

    def __init__(
        self,
        component_db: "ComponentDB | None" = None,
        hdl_lib_name: str = "hdl_lib",
        hdl_lib_path: "Path | None" = None,
        router: "WireRouterBase | None" = None,
        text_optimizer: "TextLayoutOptimizer | None" = None,
        aesthetic_report: "AestheticReport | None" = None,
        ioport_auditor: "IOPortAuditor | None" = None,
        routing_cfg: "RoutingConfig | None" = None,
    ) -> None:
        """Initialize CSA writer.

        Phase XIV D5: 布线器 / 文本优化器 / 报告收集器通过依赖注入传入，
        本类不 import 具体布线器类（防循环依赖）。缺省时由工厂创建。

        Phase XVI T2: ``ioport_auditor`` 可选注入；缺省且 ``ioport.audit``
        开启时懒创建 ``IOPortAuditor``（接线核对/网名一致性/孤立检测）。

        Args:
            component_db: Optional ComponentDB for looking up part names.
            hdl_lib_name: Name of the HDL component library (default: "hdl_lib").
            hdl_lib_path: Path to the HDL library root directory.  When provided,
                symbol.css files are parsed for dynamic property offsets
                (VALUE, $LOCATION/LOCATION) and ROTATION/JUSTIFICATION
                parameters, replacing hardcoded defaults.
            router: WireRouterBase 实例（routing.mode 决定；缺省工厂创建）。
            text_optimizer: TextLayoutOptimizer 实例（D1，默认懒创建）。
            aesthetic_report: AestheticReport 收集器（D1/D2，可选）。
            ioport_auditor: IOPortAuditor 实例（T2，可选；缺省按开关懒创建）。
            routing_cfg: RoutingConfig（缺省用全局 config.routing）。
        """
        from ..config import config as _cfg
        from .aesthetic_report import AestheticReport
        from .placeholder_lib import PlaceholderLibrary

        self._component_db: "ComponentDB | None" = component_db
        self._hdl_lib_name: str = hdl_lib_name
        self._hdl_lib_path: "Path | None" = Path(hdl_lib_path) if hdl_lib_path else None
        self._instance_counter: int = 0
        self._match_map: dict[str, "ComponentDef"] = {}  # library_id → ComponentDef
        # Cache for symbol.css property offsets: body_name → {prop_name: (x, y, rot, just)}
        self._prop_offset_cache: dict[str, dict[str, tuple[int, int, int, int]]] = {}
        # ── Phase XIV D5: routing / text-layout / report injection ──
        self._routing_cfg = routing_cfg if routing_cfg is not None else _cfg.routing
        self._router: "WireRouterBase | None" = router
        self._text_optimizer = text_optimizer
        # Phase XVI（用户要求）：默认转换也在输出目录生成诊断报告。
        # always_write=true（默认）时报告收集器无条件创建；aesthetic.enabled
        # 开启完整美化时同样创建。报告只读，不影响 CSA 输出内容。
        _report_on = bool(
            getattr(self._routing_cfg, "report", None).always_write
            if getattr(self._routing_cfg, "report", None) is not None
            else False
        ) or bool(getattr(self._routing_cfg, "aesthetic", None).enabled)
        self._aesthetic_report: "AestheticReport | None" = (
            aesthetic_report if aesthetic_report is not None
            else (AestheticReport() if _report_on else None)
        )
        if self._aesthetic_report is not None:
            self._aesthetic_report.enabled = bool(
                getattr(self._routing_cfg, "aesthetic", None).report
            ) or bool(
                getattr(getattr(self._routing_cfg, "report", None),
                        "aesthetic", True)
            )
        # ── Phase XV P0-F: 占位符号服务（无具体符号的多引脚芯片） ──
        self._placeholder_lib = PlaceholderLibrary(
            enabled=self._routing_cfg.placeholder.enabled,
        )
        # ── Phase XVII M1: temp_lib 模拟图标（优先；替代 placeholder） ──
        from .mock_icon_lib import MockIconLibrary
        self._mock_lib = MockIconLibrary(
            enabled=self._routing_cfg.temp_lib.enabled,
            lib_name=self._routing_cfg.temp_lib.lib_name,
            annotate=self._routing_cfg.temp_lib.annotate,
            mock_text=self._routing_cfg.temp_lib.mock_text,
        )
        # refdes → PlaceholderSymbol | MockSymbol | None（页级 memo）
        self._placeholder_for_refdes: dict[str, object | None] = {}
        # ── Phase XV P1-D: 每页 GND 分布符号计划（page_num → 列表） ──
        self._page_gnd_symbols: dict[int, list[dict]] = {}
        # ── Phase XVIII R6: 每页 GND 簇内并联 WIRE 段（page_num → 组 → 段）。
        # 聚类计划时预计算（hub 短接 + 1 条引出），路由后挂回对应组。
        self._gnd_cluster_wires: dict[int, dict[str, list]] = {}
        # ── Phase XVII M8: chip_config 悬空引脚/放置覆盖（set_matches 填充） ──
        self._hanging_pins: dict[str, set[str]] = {}
        self._placement_offsets: dict[str, tuple[int, int]] = {}
        # ── Phase XVI T1: mirror 归一化状态 ─────────────────────────
        # Pass 1 计算 refdes → 等效 DEHDL R 行角度（0/90/180/270），
        # Pass 2 发射时读取（同 _page_gnd_symbols 既有模式）。
        self._mirror_rline: dict[str, int] = {}
        # 报告用镜像条目（aesthetic_report [MIRROR] 节）。
        self._mirror_entries: list = []
        # ── Phase XVIII R3 (Q2): 有效视图（sym_2 切换）状态 ────────
        # Pass 1 计算 refdes → (视图号, dehdl 旋转角)；Pass 2 FORCEADD/
        # LASTPIN 发射时读取 —— 坐标唯一原则：pin_coords/net_pin_map/
        # LASTPIN/WIRE 全部由"体坐标 + 所选视图 css 偏移"派生。
        self._effective_views: dict[str, tuple[int, int]] = {}
        #: R3d：被 _unique_pin_coord 25 网格微移的引脚键（跳过坐标强校验）。
        self._nudged_pin_keys: set[str] = set()
        # ── Phase XXII D8: 引脚偏移单源（LASTPIN expected 与 Pass 1 同源）──
        # ``refdes.pin → 实际使用的 resolved offset``（旋转/镜像后）；每页
        # _compute_pin_geometry 开始时清空，避免跨页串扰。
        self._pin_offset_map: dict[str, tuple[int, int]] = {}
        # ── Phase XXII D5: IOPORT 聚类槽位（edge_layout 开启时）─────────
        # ``effective_idx → ordinal``（按同网页内引脚 y 均值降序分配槽位，
        # 确定性无重叠）。
        self._ioport_cluster_order: dict[int, int] = {}
        # ── Phase XVIII R4: CrossRef CSV 属性注入数据源 ────────────
        self._crossref_map: dict = {}
        # ── Phase XVI T2: IOPORT 审计注入 ──────────────────────────
        # Phase XVI（用户要求）：默认转换也输出 ioport_audit_report.txt。
        _audit_on = bool(
            getattr(getattr(self._routing_cfg, "report", None),
                    "ioport_audit", True)
        ) or bool(getattr(self._routing_cfg, "ioport", None).audit)
        if ioport_auditor is not None:
            self._ioport_auditor = ioport_auditor
        elif _audit_on:
            from .ioport_audit import IOPortAuditor
            self._ioport_auditor = IOPortAuditor(
                enabled=True,
                skip_orphan=self._routing_cfg.ioport.skip_orphan,
                manual_names=self._routing_cfg.ioport.manual_names,
            )
        else:
            self._ioport_auditor = None
        # 孤立 IOPORT 原始网名集合（skip_orphan 预计算；默认空=不跳过）。
        self._orphan_ioport_names: set[str] = set()
        # 审计接线核对是否已逐页调用（write 时未调用 → 报告注明 wires skipped）。
        self._ioport_audit_called: bool = False

    def set_matches(self, match_results: "list[MatchResult]") -> None:
        """Set match results for looking up full HDL component pin data.
        
        This enables generating complete LASTPIN entries for all chip pins,
        not just the sparse pin_connections from the DSN instance.

        Phase XVII M8: 同时提取 ``hanging_pins``（悬空引脚，保留 LASTPIN
        不生成 WIRE）与 ``placement``（放置覆盖，写回 body 坐标偏移）——
        来自 chip_config.yaml v2.0 的 extra_data。
        """
        for m in match_results:
            if m.target_library_id and hasattr(self, '_component_db') and self._component_db:
                try:
                    comp = self._component_db.get_by_library_id(m.target_library_id)
                    if comp:
                        self._match_map[m.source_library_id] = comp
                except Exception:
                    pass
            extra = getattr(m, "extra_data", None) or {}
            ref_key = str(getattr(m, "source_library_id", "") or "").upper()
            hanging = extra.get("hanging_pins")
            if hanging:
                self._hanging_pins[ref_key] = {
                    str(h).upper() for h in hanging
                }
            placement = extra.get("placement")
            if placement and isinstance(placement, dict):
                try:
                    self._placement_offsets[ref_key] = (
                        int(placement.get("dx", 0) or 0),
                        int(placement.get("dy", 0) or 0),
                    )
                except (TypeError, ValueError):
                    pass

    def set_crossref_map(self, crossref_map: "dict | None") -> None:
        """Set the CrossRef refdes→entry map for CSA 属性注入（Phase XVIII R4）。

        数据源铁律：DESCRIPTION / JEDEC_TYPE / PACKAGE_TYPE / SN_NUM
        只能来自 CrossRef CSV 解析结果（conversion_engine 注入），
        writer 禁止自造数据。

        Args:
            crossref_map: ``{refdes: CrossRefEntry}`` 映射（可为 None）。
        """
        self._crossref_map = dict(crossref_map or {})

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def write(self, page: "PageIR", output_dir: Path) -> list[Path]:
        """Generate a single .csa page file (standalone usage).

        Args:
            page: PageIR instance to convert.
            output_dir: Output root directory.

        Returns:
            List containing the generated .csa file path.
        """
        self._ensure_output_dir(output_dir)
        project_name: str = getattr(page, "page_name", "") or "page"
        mgr: OutputManager = OutputManager(
            project_name=project_name, output_root=output_dir,
        )
        mgr.setup_directory_structure()
        page_num: int = self._extract_page_number(
            page.page_id, getattr(page, "page_name", "")
        )
        content: str = self._build_csa_content(page, page_num)
        csa_path: Path = mgr.write_csa_page(page_num, content)
        return [csa_path]

    def write_with_manager(
        self,
        page: "PageIR",
        mgr: OutputManager,
    ) -> list[Path]:
        """Generate a .csa page file using an existing OutputManager.

        Args:
            page: PageIR instance to convert.
            mgr: Pre-configured OutputManager instance.

        Returns:
            List of generated file paths (single .csa file).
        """
        page_num: int = self._extract_page_number(
            page.page_id, getattr(page, "page_name", "")
        )
        content: str = self._build_csa_content(page, page_num)
        csa_path: Path = mgr.write_csa_page(page_num, content)
        logger.info(
            "CSA writer: page %d generated (%d instances) → %s",
            page_num, len(page.instances), csa_path,
        )
        return [csa_path]

    def write_all(
        self,
        design: "DesignIR",
        mgr: OutputManager,
    ) -> list[Path]:
        """Generate .csa files for all pages in a design.

        Args:
            design: Full DesignIR with all pages.
            mgr: Pre-configured OutputManager.

        Returns:
            List of all generated .csa file paths.
        """
        output_files: list[Path] = []
        self._instance_counter = 0
        for page in design.pages:
            paths: list[Path] = self.write_with_manager(page, mgr)
            output_files.extend(str(p) for p in paths)  # type: ignore[arg-type]
        return output_files  # type: ignore[return-value]

    # ------------------------------------------------------------------
    #  CSA content builder
    # ------------------------------------------------------------------

    def _build_csa_content(self, page: "PageIR", page_num: int) -> str:
        """Build complete .csa MACRO_DRAWING content for a page.

        Args:
            page: PageIR with component instances.
            page_num: Page number (1-based).

        Returns:
            Complete .csa content string.
        """
        lines: list[str] = []

        # ── FILE header ────────────────────────────────────────────
        lines.append("FILE_TYPE = MACRO_DRAWING;")
        lines.append("SET COLOR_WIRE YELLOW;")
        lines.append("SET COLOR_PROP ORANGE;")
        lines.append("SET COLOR_DOT WHITE;")
        lines.append("SET COLOR_ARC YELLOW;")
        lines.append("SET COLOR_BODY GREEN;")
        lines.append("SET COLOR_NOTE PURPLE;")
        lines.append("SET PROP_DISPLAY VALUE;")

        # Resolve page_name for EDIT PAGE NAME
        page_name = getattr(page, "page_name", "") or page.page_id or "DDR3"

        # PAGE_NUMBER must use "P" format (e.g. "P1", "P2") — Cadence 16.6
        # DEHDL does not support arbitrary text here.
        lines.append(f"SET PAGE_NUMBER P{page_num};")

        # ── C SIZE PAGE border block (required by Cadence DEHDL) ───
        lines.append("FORCEADD C SIZE PAGE..1")
        lines.append("(-250 0);")
        lines.append("FORCEPROP 1 LAST COMMENT_BODY TRUE")
        lines.append("J 0")
        lines.append("(1750 225);")
        lines.append("DISPLAY 0.872340 (1750 225);")
        lines.append("PAINT GREEN (1750 225);")
        lines.append("DISPLAY INVISIBLE (1750 225);")
        lines.append("FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE -10750,8275,0,0")
        lines.append("J 0")
        lines.append("(-250 0);")
        lines.append("DISPLAY 0.468085 (-250 0);")
        lines.append("PAINT GREEN (-250 0);")
        lines.append("DISPLAY INVISIBLE (-250 0);")
        lines.append("FORCEPROP 2 LAST CDS_LIB hdl_lib")
        lines.append("J 0")
        lines.append("(-250 0);")
        lines.append("DISPLAY INVISIBLE (-250 0);")
        lines.append(f"FORCEPROP 0 LAST EDIT PAGE NAME {page_name}")
        lines.append("J 0")
        lines.append("(-250 0);")
        lines.append("DISPLAY INVISIBLE (-250 0);")

        # ── Info page graphics (text/annotations) ──────────────────
        graphic_lines = self._build_csa_graphic_elements(page)
        if graphic_lines:
            lines.append("")
            lines.extend(graphic_lines)

        # v0.8.2: Add page title for info pages (no component instances)
        if not page.instances and page_name:
            lines.append("")

        # ── Component instances ────────────────────────────────────
        instances: list = page.instances
        total: int = len(instances)
        has_coords: bool = any(
            inst.loc_x != 0 or inst.loc_y != 0 for inst in instances
        )

        # ── Coordinate mapping (CIS/DSN → DEHDL C SIZE PAGE) ─────
        coord_map: dict[str, tuple[int, int]] = {}
        if has_coords:
            coord_map = self._map_coords_to_dehdl(instances)

        # C SIZE PAGE full boundary for out-of-bounds fallback check
        _PAGE_X_MIN: int = -10750
        _PAGE_X_MAX: int = 0
        _PAGE_Y_MIN: int = 0
        _PAGE_Y_MAX: int = 8275

        for idx, inst in enumerate(instances):
            refdes: str = getattr(inst, "refdes", "")
            if refdes in coord_map:
                dx, dy = coord_map[refdes]
                # Fallback to grid if mapped coordinate exceeds page bounds
                if (_PAGE_X_MIN <= dx <= _PAGE_X_MAX
                        and _PAGE_Y_MIN <= dy <= _PAGE_Y_MAX):
                    x, y = dx, dy
                else:
                    logger.warning(
                        "Instance %s mapped (%d, %d) outside C SIZE PAGE "
                        "range, falling back to grid layout", refdes, dx, dy,
                    )
                    x, y = self._grid_position(idx)
            else:
                x, y = self._grid_position(idx)
            _ = total

            body_name: str = self._resolve_body_name(inst)
            section: int = getattr(inst, "section", 1) or 1
            refdes: str = getattr(inst, "refdes", "?")
            props: dict[str, str] = getattr(inst, "properties", {}) or {}
            pin_conns: dict[str, str] = getattr(inst, "pin_connections", {}) or {}
            rot: int = getattr(inst, "rotation", 0)
            # ── Dynamic property offsets from symbol.css ─────────────
            prop_offsets: dict[str, tuple[int, int, int, int]] = (
                self._get_prop_offsets(body_name)
            )
            
            # ── Resolve full pin data from matched HDL component ────
            lib_id: str = getattr(inst, "library_id", "") or ""
            matched_pins: list = []
            if lib_id in self._match_map:
                matched_pins = list(self._match_map[lib_id].pins)
            elif pin_conns:
                # Fallback: use pin_connections directly
                matched_pins = [
                    type('Pin', (), {'number': k, 'name': v})()
                    for k, v in pin_conns.items()
                ]

            # Determine rotation letter (R0 → "", R1 → "R 1", etc.)
            # Phase XV P0-E: EDIF angle → DEHDL R convention (90↔270 swap).
            _rot_dehdl = _dehdl_rotation(rot)
            rot_str: str = f"R {_rot_dehdl}" if _rot_dehdl != 0 else ""

            # ── Instance tag for PATH property ─────────────────────
            self._instance_counter += 1
            inst_tag: str = f"I{self._instance_counter}"

            # ── FORCEADD ──────────────────────────────────────────
            lines.append(f"FORCEADD {body_name}..{section}")
            lines.append(f"({x} {y});")

            # ── VALUE (visible, ORANGE) ───────────────────────────
            # Priority: CIS value_override (from CrossRef) > HDL VALUE (from part.ptf) > refdes
            value: str = getattr(inst, "value_override", "")
            if not value:
                value = self._resolve_prop(props, "VALUE")
            if not value:
                value = refdes

            # Resolve VALUE offset from symbol.css with fallback to hardcoded defaults
            if "VALUE" in prop_offsets:
                val_px, val_py, val_rot, val_just = prop_offsets["VALUE"]
                vx, vy = x + val_px, y + val_py
                val_rot_str: str = f"R {val_rot}" if val_rot != 0 else "R 1"
                val_just_str: str = f"J {val_just}"
            else:
                vx, vy = x - 5, y - 50
                val_rot_str = "R 1"
                val_just_str = "J 1"

            lines.append(f"FORCEPROP 1 LAST VALUE {value}")
            lines.append(val_rot_str)
            lines.append(val_just_str)
            lines.append(f"({vx} {vy});")
            lines.append(f"DISPLAY {_SCALE_VALUE} ({vx} {vy});")
            lines.append(f"PAINT {_PAINT_ORANGE} ({vx} {vy});")

            # ── PATH (invisible) ───────────────────────────────────
            lines.append(f"FORCEPROP 1 LAST PATH {inst_tag}")
            lines.append("J 0")
            lines.append(f"({x} {y});")
            lines.append(f"DISPLAY {_SCALE_TRANSITION} ({x} {y});")
            lines.append(f"PAINT {_PAINT_ORANGE} ({x} {y});")
            lines.append(f"DISPLAY INVISIBLE ({x} {y});")

            # ── CDS_LMAN_SYM_OUTLINE (visible, GREEN) ──────────────
            outline: str = "-50,0,50,-25"
            lines.append(f"FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE {outline}")
            lines.append("J 0")
            lines.append(f"({x} {y});")
            lines.append(f"DISPLAY {_SCALE_OUTLINE} ({x} {y});")
            lines.append(f"PAINT {_PAINT_GREEN} ({x} {y});")
            lines.append(f"DISPLAY INVISIBLE ({x} {y});")

            # ── CDS_LIB (invisible) ────────────────────────────────
            lines.append(f"FORCEPROP 2 LAST CDS_LIB {self._hdl_lib_name}")
            lines.append("J 0")
            lines.append(f"({x} {y});")
            lines.append(f"PAINT {_PAINT_ORANGE} ({x} {y});")
            lines.append(f"DISPLAY INVISIBLE ({x} {y});")

            # ── PART_NAME (invisible) ──────────────────────────────
            part_name: str = self._resolve_prop(props, "PART_NAME")
            if not part_name:
                part_name = self._resolve_part_name(inst, body_name)
            lines.append(f"FORCEPROP 1 LAST PART_NAME {part_name}")
            lines.append("J 0")
            lines.append(f"({x} {y});")
            lines.append(f"DISPLAY {_SCALE_TRANSITION} ({x} {y});")
            lines.append(f"PAINT {_PAINT_ORANGE} ({x} {y});")
            lines.append(f"DISPLAY INVISIBLE ({x} {y});")

            # ── DESCRIPTION (invisible) ────────────────────────────
            desc: str = self._resolve_prop(props, "DESCRIPTION")
            if desc:
                lines.append(f"FORCEPROP 1 LAST DESCRIPTION {desc}")
                lines.append("J 0")
                lines.append(f"({x} {y});")
                lines.append(f"DISPLAY {_SCALE_TRANSITION} ({x} {y});")
                lines.append(f"PAINT {_PAINT_ORANGE} ({x} {y});")
                lines.append(f"DISPLAY INVISIBLE ({x} {y});")

            # ── PACKAGE_TYPE (invisible) ───────────────────────────
            pkg: str = self._resolve_prop(props, "PACKAGE_TYPE")
            if pkg:
                lines.append(f"FORCEPROP 1 LAST PACKAGE_TYPE {pkg}")
                lines.append("J 0")
                lines.append(f"({x} {y});")
                lines.append(f"DISPLAY {_SCALE_TRANSITION} ({x} {y});")
                lines.append(f"PAINT {_PAINT_ORANGE} ({x} {y});")
                lines.append(f"DISPLAY INVISIBLE ({x} {y});")

            # ── SN_NUM (invisible) ─────────────────────────────────
            sn: str = self._resolve_prop(props, "SN_NUM")
            if sn:
                lines.append(f"FORCEPROP 1 LAST SN_NUM {sn}")
                lines.append("J 0")
                lines.append(f"({x} {y});")
                lines.append(f"DISPLAY {_SCALE_TRANSITION} ({x} {y});")
                lines.append(f"PAINT {_PAINT_ORANGE} ({x} {y});")
                lines.append(f"DISPLAY INVISIBLE ({x} {y});")

            # ── JEDEC_TYPE (invisible) ─────────────────────────────
            jedec: str = self._resolve_prop(props, "JEDEC_TYPE")
            if jedec:
                lines.append(f"FORCEPROP 1 LAST JEDEC_TYPE {jedec}")
                lines.append("J 0")
                lines.append(f"({x} {y});")
                lines.append(f"DISPLAY {_SCALE_TRANSITION} ({x} {y});")
                lines.append(f"PAINT {_PAINT_ORANGE} ({x} {y});")
                lines.append(f"DISPLAY INVISIBLE ({x} {y});")

            # ── $LOCATION / LOCATION (visible, GREEN) ──────────────
            # Resolve LOCATION offset from symbol.css with fallback to hardcoded defaults
            # Reference engineering (8367/04p4) shows $LOCATION is the
            # dominant attribute name for BOTH single- and multi-section
            # parts (04p4: CAPACITOR $LOCATION×46 vs LOCATION×0, RESISTOR
            # ×20 vs ×1); the plain "LOCATION" spelling appears only for a
            # few parts whose symbol.css declares it.  Prefer $LOCATION.
            loc_prop_name: str = "$LOCATION"
            if loc_prop_name in prop_offsets:
                loc_px, loc_py, loc_rot, loc_just = prop_offsets[loc_prop_name]
                loc_x: int = x + loc_px
                loc_y: int = y + loc_py
                loc_rot_str: str = f"R {loc_rot}" if loc_rot != 0 else "R 1"
                loc_just_str: str = f"J {loc_just}"
            elif "LOCATION" in prop_offsets:
                loc_px, loc_py, loc_rot, loc_just = prop_offsets["LOCATION"]
                loc_x = x + loc_px
                loc_y = y + loc_py
                loc_rot_str = f"R {loc_rot}" if loc_rot != 0 else "R 1"
                loc_just_str = f"J {loc_just}"
            else:
                loc_x = x - 5
                loc_y = y + 220
                loc_rot_str = "R 1"
                loc_just_str = "J 1"

            # $LOCATION is the standard DEHDL attribute name — used for
            # single- and multi-section parts alike (P1-3, reference
            # engineering 8367/04p4).
            lines.append(f"FORCEPROP 1 LAST $LOCATION {refdes}")
            lines.append(loc_rot_str)
            lines.append(loc_just_str)
            lines.append(f"({loc_x} {loc_y});")
            lines.append(f"DISPLAY {_SCALE_VALUE} ({loc_x} {loc_y});")
            lines.append(f"PAINT {_PAINT_GREEN} ({loc_x} {loc_y});")

            # ── CDS_LOCATION (invisible) ───────────────────────────
            lines.append(f"FORCEPROP 2 LAST CDS_LOCATION {refdes}")
            lines.append("J 0")
            lines.append(f"({loc_x} {loc_y + 55});")
            lines.append(f"DISPLAY {_SCALE_TRANSITION} ({loc_x} {loc_y + 55});")
            lines.append(f"PAINT {_PAINT_ORANGE} ({loc_x} {loc_y + 55});")
            lines.append(f"DISPLAY INVISIBLE ({loc_x} {loc_y + 55});")

            # ── $SEC / CDS_SEC (invisible) ─────────────────────────
            lines.append(f"FORCEPROP 2 LAST $SEC {section}")
            lines.append("J 0")
            lines.append(f"({loc_x} {loc_y + 55});")
            lines.append(f"DISPLAY {_SCALE_SEC} ({loc_x} {loc_y + 55});")
            lines.append(f"PAINT {_PAINT_MONO} ({loc_x} {loc_y + 55});")
            lines.append(f"DISPLAY INVISIBLE ({loc_x} {loc_y + 55});")

            lines.append(f"FORCEPROP 2 LAST CDS_SEC {section}")
            lines.append("J 0")
            lines.append(f"({loc_x} {loc_y + 55});")
            lines.append(f"DISPLAY {_SCALE_TRANSITION} ({loc_x} {loc_y + 55});")
            lines.append(f"PAINT {_PAINT_ORANGE} ({loc_x} {loc_y + 55});")
            lines.append(f"DISPLAY INVISIBLE ({loc_x} {loc_y + 55});")

        # ── QUIT: required termination statement for Cadence DEHDL ──
        lines.append("QUIT")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    #  Info page graphic elements
    # ------------------------------------------------------------------

    @staticmethod
    def _build_csa_graphic_elements(page: "PageIR") -> list[str]:
        """为包含图形元素的信息页生成 CSA 文本注释。

        信息页（Cover_Page, Block_Diagram, Clock_Tree, Power_Tree）
        中的 TitleBlock/GraphicInst 文本通过二进制扫描提取，存储为
        graphic_elements。此方法将其转换为 CSA 注释格式，
        供 Cadence DEHDL 在 LOAD_MACRO 时渲染。

        注意：由于二进制扫描不提供精确坐标，文本以注释形式
        （ADD_COMMENT）添加到 CSA 文件中。后续可通过完整解析
        PrimCommentText 来获取精确坐标。

        Args:
            page: PageIR 实例，可能包含 graphic_elements。

        Returns:
            CSA 注释行列表。
        """
        elements = getattr(page, 'graphic_elements', None)
        if not elements:
            return []

        lines: list[str] = []
        for elem in elements:
            if elem.get('type') != 'text':
                continue
            text = elem.get('text', '')
            if not text:
                continue
            # Skip garbled binary text (non-printable characters beyond basic ASCII/latin)
            if any(ord(c) < 32 and c not in '\t\n\r' for c in text):
                continue
            # Skip text that looks like raw binary (high concentration of high bytes)
            non_ascii = sum(1 for c in text if ord(c) > 127)
            if non_ascii > len(text) * 0.5:  # more than 50% non-ASCII
                continue

            # 转义特殊字符
            escaped = text.replace('\\', '\\\\').replace('"', '\\"')
            # 截断过长文本
            if len(escaped) > 200:
                escaped = escaped[:197] + "..."

            # 使用 ADD_COMMENT 注释格式（DEHDL 信息页的通用做法）
            # position 是字节偏移，不是坐标 — 用作排序依据
            pos = elem.get('position', 0)
            # Skip ADD_COMMENT — not supported in Cadence 16.6 CSA
            # (text annotations would require full TitleBlock parsing)
            pass

        return lines

    @staticmethod
    def _extract_page_number(page_id: str, page_name: str = "") -> int:
        """Extract page number from page metadata.

        For DSN pages: prefer page_name "23-USB_UART" → 23 over page_id "1.19" → 19.
        For xref pages: page_id "xref.21-4GE" → 21.

        Args:
            page_id: Page ID like "1.1", "xref.21-4GE".
            page_name: Optional page name like "23-USB_UART".

        Returns:
            Page number as integer (1-based).
        """
        # v0.8.2: Prefer page_name for DSN pages (correct number)
        if page_name:
            import re
            m = re.match(r'(\d+)', page_name)
            if m:
                return int(m.group(1))

        # Handle xref pages
        if page_id.startswith("xref."):
            import re
            m = re.search(r'(\d+)', page_id)
            if m:
                return int(m.group(1))
            return 99

        try:
            parts = page_id.rsplit(".", 1)
            return int(parts[-1])
        except (ValueError, IndexError):
            return 1

    def _resolve_body_name(self, inst) -> str:
        """Resolve the HDL body name (cell/directory name) for a component instance.

        Always returns the cell (directory) name, never the primitive name.
        This is what FORCEADD expects in the CSA format.

        Resolution order:
          1. Match via ``_match_map`` → uses matched HDL ComponentDef's
             library_id (e.g. ``hdl_lib/capacitor`` → ``CAPACITOR``).
          2. Delegate to ``WriterBase._resolve_body_name`` for library_id /
             refdes-prefix resolution.
          3. Return result uppercased (CSA format convention).
        """
        library_id: str = getattr(inst, "library_id", "")

        # 1. Prefer match_map — gives the actual HDL library directory name
        if (library_id
                and hasattr(self, '_match_map')
                and library_id in self._match_map):
            comp = self._match_map[library_id]
            hdl_id: str = comp.library_id
            return hdl_id.rsplit("/", 1)[-1].upper()

        # 2. Fallback: delegate to base class (library_id / refdes prefix)
        base_name: str = WriterBase._resolve_body_name(inst)

        return base_name.upper()

    # ------------------------------------------------------------------
    #  Phase XV P0-F: placeholder symbol integration
    # ------------------------------------------------------------------

    @staticmethod
    def _is_passive_body(body_name: str) -> bool:
        """True when ``body_name`` is a canonical 2-pin passive symbol.

        Passives (capacitor/resistor/inductor/diode/led/bead and their
        single-letter prefixes) always have a real HDL symbol and must NOT
        be replaced by a placeholder — the placeholder is only for
        multi-pin ICs whose concrete symbol is missing/mismatched.

        Args:
            body_name: HDL cell name (case-insensitive).

        Returns:
            True for known passive body names.
        """
        b = (body_name or "").lower().rstrip("0123456789_")
        return b in (
            "capacitor", "resistor", "inductor", "diode", "led", "bead", "fb",
            "c", "r", "l", "d", "fb",
            "ferrite_bead", "zener", "tvs", "fuse", "sw", "sw_dpst",
            "crystal", "xtal", "osc", "connector", "header", "mark",
            "test_point", "hole", "tp", "j", "jumper",
        )

    @staticmethod
    def _is_connector_body(body_name: str) -> bool:
        """connector 类 body（Phase XX：mock_all 时一律模拟图标）。

        ``_is_passive_body`` 把 connector/header/j/jumper 归为 passive
        （因真实库有符号）——但用户 08-13 决策：**所有芯片与 connector
        无论是否匹配，默认全部用模拟图标**。本函数单独识别 connector
        类，使 mock_all 分支将其排除出 passive 保留名单。

        Args:
            body_name: HDL cell 名（大小写不敏感）。

        Returns:
            True 为 connector/header/j/jumper 等连接器类。
        """
        b = (body_name or "").lower()
        if not b:
            return False
        # Phase XX 补丁（08-13 复测）：旧实现 ``rstrip("0123456789_")`` +
        # 精确匹配 —— "RJ45" 的型号数字 45 被 rstrip 删掉 → "rj" ≠ "rj45"
        # → False；"RJ45_2X2_LED"、"CONNECTOR_2X5" 等复合名也全部落空 →
        # connector 被误当 passive 保留 → 用户实测 J 系列仍是真实库错误
        # 图标。改为**分词 + 前缀 + 型号**多路匹配（rj45/usb/hdmi 等型号
        # 数字是名字的一部分，不能删）。
        tokens = set(b.replace("-", "_").split("_"))
        # 型号数字（dsub9/dsub15）是名字一部分：token 去尾数字再比对。
        if tokens & {
            "connector", "header", "jumper", "socket", "rj45", "usb",
            "hdmi", "sata", "pcie", "dsub", "bnc", "fpc", "ffc", "edge",
        } or any(
            t.rstrip("0123456789") in {
                "dsub", "rj45", "usb", "hdmi", "sata", "pcie", "bnc",
            } for t in tokens
        ):
            return True
        if b.startswith((
            "connector", "header", "jumper", "socket",
            "rj45", "usb", "hdmi", "edge",
        )):
            return True
        # 短前缀 j 单独处理：仅 j + 数字/空（避免误伤 j 开头的其他词）
        if b == "j" or (b.startswith("j") and b[1:].isdigit()):
            return True
        return False

    @staticmethod
    def _is_schematic_element(body_name: str) -> bool:
        """schematic 元素（非元件）保留真实库（Phase XX 补丁）。

        IOPORT/OFFPAGE/MARK/TP/BISHEET/JUNCTION/NC 等是**图纸元素**而非
        可 mock 的元件——mock_all 分支若把它们当芯片 mock（矩形+引脚）
        会破坏端口符号与电源符号（GND_POWER 等已被 is_power_symbol 拦
        截；IOPORT 等在此拦截）。

        Args:
            body_name: HDL cell 名（大小写不敏感）。

        Returns:
            True 为 schematic 元素。
        """
        b = (body_name or "").lower().rstrip("0123456789_")
        return b in {
            "ioport", "offpage", "offpage_l", "offpage_r", "off_page",
            "bisheet", "onsheet2", "offsheet2", "junction", "route",
            "title123", "page_border_template", "nc", "mark",
            "test_point", "tp", "hole",
        }

    @staticmethod
    def _is_passive_view_body(body_name: str) -> bool:
        """True 时 body 是被动元件且有横向 sym_2 视图（Q2 方案 A）。

        仅 capacitor / resistor / inductor（refdes 前缀 C/R/L、2 引脚）
        可切换到 ``..2`` 横向视图（golden page9 L354 先例）；dc_dc 等
        sym_N 是**器件变体**，禁止切换（保留 R 行或 mock 接管）。

        Args:
            body_name: HDL cell 名（大小写不敏感）。

        Returns:
            True 仅对 capacitor/resistor/inductor。
        """
        b = (body_name or "").lower().rstrip("0123456789_")
        return b in ("capacitor", "resistor", "inductor")

    def _pin_offset_resolves(
        self,
        pre,
        css_offsets: dict[str, tuple[int, int]],
        pinmap: dict[str, str],
    ) -> bool:
        """True when a pin's offset resolves on the matched symbol.

        Mirrors the resolution order in ``_compute_pin_geometry``:
        css by pin_name → css by pin_number → chips.prt functional-name
        bridge → css by functional name.

        Args:
            pre: PinRecord (pin_number / pin_name).
            css_offsets: symbol.css C-command offsets of the matched body.
            pinmap: chips.prt number → functional name map.

        Returns:
            True when the pin lands on a known symbol pin.
        """
        if css_offsets.get(pre.pin_name) or css_offsets.get(pre.pin_number):
            return True
        if pinmap:
            fname = pinmap.get(str(pre.pin_number).upper())
            if fname is None:
                fname = pinmap.get(str(pre.pin_number))
            if fname and css_offsets.get(fname):
                return True
        return False

    def _select_rotation_view(
        self, body_name: str, refdes: str, rot: int, section: int = 1,
    ) -> tuple[int, int]:
        """Q2 方案 A 判定：被动元件旋转 → sym_2 横向视图（不写 R 行）。

        仅对 capacitor/resistor/inductor（``_is_passive_view_body``）且
        dehdl 旋转 ≠ 0 的实例尝试切换；sym_2 必须存在且为横向视图
        （``_is_horizontal_view``）。sym_3/sym_4 是电解电容变体（引脚
        A/B）禁止误用；dc_dc 等非被动体保持 R 行。

        Args:
            body_name: HDL cell 名。
            refdes: 实例位号（refdes 前缀 C/R/L 才切）。
            rot: EDIF 旋转角（0/90/180/270）。
            section: 原始视图号（默认 1）。

        Returns:
            ``(视图号, dehdl 旋转角)`` —— 命中返回 ``(2, 0)``；
            否则保持 ``(section, rot_dehdl)``。
        """
        rot_dehdl = _dehdl_rotation(int(rot or 0))
        if not (rot_dehdl and self._is_passive_view_body(body_name)):
            return int(section or 1), rot_dehdl
        if not self._is_passive_refdes(refdes):
            return int(section or 1), rot_dehdl
        sym2 = self._get_css_pin_offsets(body_name, 2)
        if not sym2 or not _is_horizontal_view(sym2):
            return int(section or 1), rot_dehdl
        return 2, 0

    def _effective_view(
        self, irec, body_name: str, section: int,
    ) -> tuple[int, int, dict]:
        """返回 (视图号, dehdl 旋转角度, css_offsets)。

        Q2 方案 A（用户决策）：被动元件（capacitor/resistor/inductor，
        2 引脚 C/R/L）且 dehdl 旋转 ≠ 0 且非 mirror 时，若
        hdl_lib/<body>/sym_2 存在且为横向视图，返回
        ``(2, 0, sym_2_offsets)`` —— FORCEADD ``..2`` + 无 R 行；
        pin_coords/net_pin_map/LASTPIN/WIRE 全部改用 sym_2 offsets
        （坐标唯一原则同源切换）。判定失败 → 保持
        ``(section, rot_dehdl, sym_1_offsets)``。

        Args:
            irec: InstanceRecord。
            body_name: HDL cell 名。
            section: 原始视图号。

        Returns:
            ``(视图号, dehdl 旋转角, css 偏移表)``。
        """
        mirror = int(getattr(irec, "mirror", 0) or 0)
        rot = int(getattr(irec, "rotation", 0) or 0)
        refdes = str(getattr(irec, "refdes", "") or "")
        pins = list(getattr(irec, "pins", []) or [])
        if not mirror:
            eff_section, eff_rot = self._select_rotation_view(
                body_name, refdes, rot, section,
            )
            if eff_section == 2 and eff_rot == 0 and len(pins) == 2:
                return 2, 0, self._get_css_pin_offsets(body_name, 2)
        return int(section or 1), _dehdl_rotation(rot), self._get_css_pin_offsets(
            body_name, section,
        )

    def _lastpin_coord_hit(
        self, coord: tuple[int, int], body: tuple[int, int],
        offset: tuple[int, int], rot: int, mirror: int,
    ) -> bool:
        """强校验：LASTPIN 绝对坐标 == body + rotate_point(offset, rot, mirror)。

        Phase XVIII R3d：在 ``_pin_offset_resolves``（名称/编号解析命中）
        之上追加坐标数学校验 —— 旋转分支数学一致性；未命中 →
        跳过 LASTPIN + ``logger.warning`` + aesthetic_report
        ``[LASTPIN_MISS]``。被 ``_unique_pin_coord`` 25 网格微移的引脚
        （``self._nudged_pin_keys``）由调用方跳过本校验（微移后坐标
        与 css 偏移严格不等）。

        Args:
            coord: LASTPIN 实际绝对坐标（pin_coords）。
            body: 实例体坐标 (x, y)。
            offset: symbol.css 引脚相对偏移 (ox, oy)。
            rot: 旋转角（镜像实例用 EDIF rot，其余用有效视图 dehdl 角）。
            mirror: 镜像标志（0/1/2）。

        Returns:
            True = 坐标严格命中（可安全发射 LASTPIN）。
        """
        bx, by = body
        ex, ey = rotate_point(offset[0], offset[1], rot, mirror)
        return coord == (bx + ex, by + ey)

    def _get_prop_value(self, body_name: str, key: str) -> str:
        """读取 body sym_1 symbol.css 中 ``P "KEY" "value"`` 的属性值。

        Args:
            body_name: HDL cell 名。
            key: 属性名（如 ``"HDL_POWER"``）。

        Returns:
            属性值字符串；缺失返回 ``""``。
        """
        cache_key = f"propval:{body_name}:{key}"
        if cache_key in self._prop_offset_cache:
            return self._prop_offset_cache[cache_key]  # type: ignore[return-value]
        if not self._hdl_lib_path:
            self._prop_offset_cache[cache_key] = ""
            return ""
        css_path = (
            self._hdl_lib_path / body_name.lower() / "sym_1" / "symbol.css"
        )
        if not css_path.exists():
            css_path = self._hdl_lib_path / body_name / "sym_1" / "symbol.css"
        val = ""
        if css_path.exists():
            try:
                text = css_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            for line in text.splitlines():
                if not line.startswith("P "):
                    continue
                parts = line.split('"')
                # P "KEY" "VALUE" ... → parts[1]=KEY, parts[3]=VALUE。
                if len(parts) >= 4 and parts[1] == key:
                    val = parts[3]
                    break
        self._prop_offset_cache[cache_key] = val
        return val

    def _gnd_power_sig_name(self, body_name: str, net: str) -> str:
        """GND_POWER SIG_NAME 值（golden 对齐，Phase XVIII R3c）。

        GND_POWER 块 SIG_NAME = symbol.css ``P "HDL_POWER"`` 值
        （如 ``GND_POWER``），回退 page 网名；统一加 ``\\g`` 后缀 →
        ``"GND_POWER\\g"``（golden page9 L12 实锤）。非 GND 电源符号
        （VCC_CIRCLE 等）保持 page 网名（golden VCC 块 SIG_NAME 用
        DC12V 等实际网名）。

        Args:
            body_name: HDL cell 名（如 ``gnd_power``）。
            net: page 网名（已 rstrip ``\\g``）。

        Returns:
            ``"<value>\\g"`` 格式的 SIG_NAME 值。
        """
        base = str(net or "GND").rstrip("\\g") or "GND"
        body_lower = (body_name or "").lower()
        if body_lower in ("gnd_power", "gnd", "gnd_earth", "gnd_signal"):
            hdl_power = self._get_prop_value(body_name, "HDL_POWER")
            if hdl_power and hdl_power.strip() not in ("", "?"):
                base = hdl_power.strip()
        return f"{base}\\g"

    @staticmethod
    def _is_plumbing_power(body_name: str) -> bool:
        """plumbing 电源符号（Cadence 不镜像、图形对称）。

        Args:
            body_name: HDL cell 名（如 ``gnd_power`` / ``vcc_circle``）。

        Returns:
            True = plumbing 电源符号（忽略 mirror，offset 恒为符号原始值）。
        """
        return (body_name or "").lower() in (
            "gnd_power", "gnd", "vcc_circle",
        )

    def _power_pin_offset(self, body_name: str) -> tuple[int, int]:
        """电源符号引脚相对偏移（Pass 1 与 LASTPIN 同源，坐标唯一原则）。

        R3c/SPCOCN-543 修复：GND_POWER 用
        ``gnd_distribution.gnd_power_lastpin_offset``（默认 [0,50] =
        fixture symbol.css 引脚 C 0 50；旧 golden (50,100) 不匹配符号
        引脚 → Cadence 删 SIG_NAME）；值 ``"css"`` 动态读 symbol.css；
        VCC_CIRCLE 保持 (0,-50)；其他电源符号 (0,50)。

        Args:
            body_name: HDL cell 名（如 ``gnd_power`` / ``vcc_circle``）。

        Returns:
            (ox, oy) 相对偏移。
        """
        body_lower = (body_name or "").lower()
        if body_lower == "vcc_circle":
            return (0, -50)
        if body_lower in ("gnd_power", "gnd"):
            cfg_off = getattr(
                self._routing_cfg.gnd_distribution,
                "gnd_power_lastpin_offset", [50, 100],
            )
            if isinstance(cfg_off, (list, tuple)) and len(cfg_off) == 2:
                return (int(cfg_off[0]), int(cfg_off[1]))
            return (0, 50)  # "css" → symbol.css 引脚
        return (0, 50)

    def _un_policy_display(self, name: str) -> str:
        """按 ``ioport.un_name_policy`` 处理 UN$ 自动网名显示（R3⑤）。

        - ``rename``（默认）：``stabilize_un_name`` 稳定可读名；
        - ``keep``：保留现状；
        - ``omit``：返回 ``""``（调用方跳过 SIG_NAME）。

        只改 CSA 显示名（con 内部名不变，数据源铁律）。

        Args:
            name: CSA 网名显示值（可能带 ``\\g`` 后缀）。

        Returns:
            处理后的显示名；``omit`` 时 UN$ 网名返回 ``""``。
        """
        raw = str(name or "")
        if "UN$" not in raw:
            return raw
        bare = raw.rstrip("\\g")
        suffix = "\\g" if raw.endswith("\\g") else ""
        policy = getattr(self._routing_cfg.ioport, "un_name_policy", "rename")
        if policy == "rename":
            from cis2hdl.utils.naming import stabilize_un_name
            return stabilize_un_name(bare) + suffix
        if policy == "omit":
            return ""
        return raw

    def _inject_crossref_props(
        self, irec, props: dict, x: int, y: int,
    ) -> list[str]:
        """从 CrossRef CSV 行注入 CSA 属性块（golden CAPACITOR 格式，R4）。

        golden page9 CAPACITOR..2 块字段顺序：VALUE → $LOCATION →
        LASTPIN → JEDEC_TYPE → SN_NUM → PACKAGE_TYPE → DESCRIPTION →
        PART_NAME → CDS_LIB → PATH。本函数输出四字段块（在
        ``_emit_conn_instance_block`` 中 PART_NAME 之后、$LOCATION
        之前插入，位置与既有属性块一致）。

        字段：JEDEC_TYPE / SN_NUM / PACKAGE_TYPE / DESCRIPTION。
        数据源：CrossRef CSV（refdes → CrossRefEntry，优先）+
        irec.properties（回退）；缺失字段跳过不注入（禁止 "?" 默认值）。

        Args:
            irec: InstanceRecord。
            props: 实例属性字典。
            x/y: 属性块坐标（body 原点，golden 同 body）。

        Returns:
            CSA 属性块行（FORCEPROP 1 LAST <KEY> <value> + J 0 +
            (x y); + DISPLAY 1.021277 + DISPLAY INVISIBLE）。
        """
        if not getattr(self._routing_cfg.attribute, "inject_crossref", True):
            return []
        refdes = str(getattr(irec, "refdes", "") or "")
        xref = self._crossref_map.get(refdes) if self._crossref_map else None
        values: dict[str, str] = {}
        for key in ("JEDEC_TYPE", "SN_NUM", "PACKAGE_TYPE", "DESCRIPTION"):
            xref_val = ""
            if xref is not None:
                xref_val = str(
                    getattr(xref, {
                        "JEDEC_TYPE": "jedec_type",
                        "SN_NUM": "sn_num",
                        "PACKAGE_TYPE": "package_type",
                        "DESCRIPTION": "description",
                    }[key], "") or ""
                ).strip()
            values[key] = xref_val or self._resolve_prop(props, key)
        lines: list[str] = []
        for key in ("JEDEC_TYPE", "SN_NUM", "PACKAGE_TYPE", "DESCRIPTION"):
            val = values[key]
            if not val or val.strip() in ("", "?", "<null>"):
                continue
            lines.append(f"FORCEPROP 1 LAST {key} {val}")
            lines.append("J 0")
            lines.append(f"({x} {y});")
            lines.append(f"DISPLAY {_SCALE_TRANSITION} ({x} {y});")
            lines.append(f"DISPLAY INVISIBLE ({x} {y});")
        return lines

    @staticmethod
    def _ref_prefix(refdes: str) -> str:
        """refdes 字母前缀（大写，如 ``R118`` → ``R``）。"""
        import re as _re
        m = _re.match(r"^([A-Za-z]+)", str(refdes or ""))
        return (m.group(1) if m else "").upper()

    @staticmethod
    def _is_passive_refdes(refdes: str) -> bool:
        """True when a refdes prefix is a canonical passive.

        Args:
            refdes: Instance reference designator (e.g. ``L20``).

        Returns:
            True for C/R/L/D/FB/LED/BEAD/Y/X/J/TP prefixes.
        """
        import re as _re
        m = _re.match(r"^([A-Za-z]+)", str(refdes or ""))
        prefix = (m.group(1) if m else "").upper()
        return prefix in (
            "C", "R", "L", "D", "FB", "LED", "BEAD", "FERRITE",
            "Y", "X", "XTAL", "J", "TP", "TESTPOINT", "MH", "NH", "UH",
        )

    def _needs_placeholder(
        self,
        irec,
        body_name: str,
        section: int,
    ) -> bool:
        """Decide whether an instance needs a placeholder symbol (P0-F).

        Phase XX（用户 08-13 决策）：``temp_lib.mock_all=true`` 时——
        **所有多引脚芯片/connector（U/J/T/S 等）无论是否匹配成功，默认
        全部用模拟图标输出**（跳过"引脚解析 ≥ 一半用真实库"的判定）。
        仅 passive（C/R/L/D/LED/FB）与 power 符号保留真实库。``mock_all
        =false`` 恢复旧行为（仅匹配失败/错误匹配才 mock）。GUI 面板可切换。

        Trigger (legacy): instance matched to NO concrete symbol (or a
        mismatched fallback such as U6 → CH347) with more than one
        connected pin and NOT a canonical passive (2-pin C/R/L/D… have
        real symbols and must not be replaced).  A symbol is "concrete"
        when more than half of the instance's pins resolve on its css
        offsets.

        Args:
            irec: InstanceRecord.
            body_name: Resolved HDL cell name (may be a wrong fallback).
            section: Symbol view number.

        Returns:
            True when a placeholder should replace the fallback symbol.
        """
        if not self._placeholder_lib.enabled:
            return False
        if irec.is_power_symbol:
            return False
        pins = list(getattr(irec, "pins", []) or [])
        # Phase XX（用户 08-13 决策）：后端默认**全部**多引脚芯片与
        # connector 用模拟图标（无论匹配结果）。GUI 面板可切换。
        # passive（C/R/L/D/LED/FB/fuse/crystal/osc/mark 等）保留真实库；
        # **connector 类排除在 passive 之外**（J4/RJ45 等即使真实库有
        # 符号也一律模拟图标）。
        # Phase XX 补丁（08-13 复测）：mock_all 分支**不检查 pins≤1** ——
        # 匹配数据缺失（pins 空/少，如 AMS1117→CH347、RJ45_2X2_LED）的
        # 实例此前被 ``len(pins) <= 1`` 拦下不 mock → 用户实测"IC3/J19
        # 还是错误图标"。pins≤1 拦截仅对 legacy（mock_all=false）生效。
        _mock_all = bool(getattr(
            getattr(self._routing_cfg, "temp_lib", None),
            "mock_all", True,
        ))
        if self._mock_lib.enabled and _mock_all:
            # schematic 元素（IOPORT/OFFPAGE/MARK/TP/BISHEET…）不是元件，
            # 保留真实库（mock 会破坏端口/电源符号）。
            if self._is_schematic_element(body_name):
                return False
            if self._is_passive_body(body_name) and not self._is_connector_body(body_name):
                return False
            # 2-pin passive refdes（L20/C20/R10 等，body 可能为变体 L_E）：
            # 真实库符号正确，保留。connector 类（J/JP/CN）除外——用户
            # 要求所有 connector 一律模拟图标。
            if (len(pins) == 2
                    and self._is_passive_refdes(getattr(irec, "refdes", ""))
                    and not self._is_connector_body(body_name)):
                return False
            return True
        # ── legacy（mock_all=false）：仅匹配失败/错误匹配才 mock ──
        if len(pins) <= 1:
            return False
        if self._is_passive_body(body_name):
            return False
        # 2-pin passive refdes (L20 etc.) must never become placeholders —
        # their canonical 2-pin symbols/offsets are correct.
        if len(pins) == 2 and self._is_passive_refdes(getattr(irec, "refdes", "")):
            return False
        css_offsets = self._get_css_pin_offsets(body_name, section)
        if not css_offsets:
            # No concrete symbol at all → placeholder (was: silent fallback).
            return True
        pinmap = self._get_pin_name_map(body_name)
        resolved = sum(
            1 for pre in pins if self._pin_offset_resolves(pre, css_offsets, pinmap)
        )
        # Fewer than half of the pins resolve → wrong fallback symbol
        # (e.g. U6 real BGA pins vs CH347 numeric 1..20) → placeholder.
        return resolved * 2 < len(pins)

    def _placeholder_for_irec(
        self,
        irec,
        body_name: str,
        section: int,
    ) -> object | None:
        """Return the memoized placeholder symbol for an instance, or None.

        Args:
            irec: InstanceRecord.
            body_name: Resolved HDL cell name.
            section: Symbol view number.

        Returns:
            ``PlaceholderSymbol`` when the instance needs one, else None.
        """
        refdes = getattr(irec, "refdes", "") or ""
        if refdes in self._placeholder_for_refdes:
            return self._placeholder_for_refdes[refdes]
        symbol = None
        if self._needs_placeholder(irec, body_name, section):
            pins = [(pre.pin_number, pre.pin_name) for pre in irec.pins]
            # Phase XVII M1: temp_lib 模拟图标优先（替代 placeholder）。
            if self._mock_lib.enabled:
                symbol = self._mock_lib.symbol_for(refdes, section, pins)
            if symbol is None:
                symbol = self._placeholder_lib.symbol_for(refdes, section, pins)
        self._placeholder_for_refdes[refdes] = symbol
        return symbol

    def _effective_body(
        self,
        conn,
        irec,
    ) -> tuple[str, object | None]:
        """Resolve the FORCEADD body name + optional placeholder symbol.

        Args:
            conn: DesignConnectivity model.
            irec: InstanceRecord.

        Returns:
            ``(body_name, placeholder)`` — when ``placeholder`` is not
            None its ``cell_name`` is the FORCEADD body and its offsets
            drive LASTPIN/WIRE geometry.
        """
        body_name = irec.cell_name or self._cell_label(conn, irec.cell_id)
        section = irec.section
        placeholder = self._placeholder_for_irec(irec, body_name, section)
        if placeholder is not None:
            return placeholder.cell_name, placeholder
        return body_name, None

    def _resolve_part_name(self, inst, body_name: str = "") -> str:
        """Resolve the PART_NAME (primitive name) for a component instance.

        Returns the specific primitive name (e.g. CAPACITOR_0402) from:
          1. match_map extra_data["selected_primitive_body"]
          2. JEDEC_TYPE → primitive lookup (PST data)
          3. Fallback to body_name (cell name, uppercased)

        Args:
            inst: Component instance IR node.
            body_name: Already-resolved cell (directory) name.

        Returns:
            Primitive part name string, uppercased.
        """
        library_id: str = getattr(inst, "library_id", "")

        if (library_id
                and hasattr(self, '_match_map')
                and library_id in self._match_map):
            comp = self._match_map[library_id]

            # 1. Check for precise primitive from FallbackMatcher/ValueMatcher
            primitive_body = comp.extra_data.get("selected_primitive_body")
            if primitive_body:
                return primitive_body.upper()

            # 2. Try JEDEC_TYPE → primitive from PST data
            jedec_type = (comp.extra_data.get("pst_jedec_type")
                          or getattr(inst, "extra_data", {}).get("pst_jedec_type", ""))
            if jedec_type:
                jedec_body = self._find_body_by_jedec_type(jedec_type, comp)
                if jedec_body:
                    return jedec_body.upper()

        # 3. Fallback: use cell/body name
        return (body_name or library_id.rsplit("/", 1)[-1] if "/" in library_id else library_id).upper()

    # ------------------------------------------------------------------
    #  JEDEC_TYPE → primitive resolution (v0.8.1)
    # ------------------------------------------------------------------

    @staticmethod
    def _find_body_by_jedec_type(jedec_type: str, comp) -> str:
        """Find the most specific HDL primitive matching a JEDEC_TYPE.

        Uses the JEDEC_TYPE package size code (e.g. \"HSC0201-HDTA\" → \"0201\")
        to locate the matching primitive in the component's all_primitives list.

        Args:
            jedec_type: JEDEC package type from pstchip.dat.
            comp: Matched HDL ComponentDef with extra_data[\"all_primitives\"].

        Returns:
            Primitive part_name (e.g. \"CAPACITOR_0201\") or empty string.
        """
        import re as _re_j
        _size_re = _re_j.compile(r"(\d{4})")
        m = _size_re.search(jedec_type)
        if not m:
            return ""
        size_code = m.group(1)

        all_prims = comp.extra_data.get("all_primitives", [])
        for prim in all_prims:
            pn = prim.get("part_name", "")
            if size_code in pn:
                return pn
        return ""

    @staticmethod
    def _resolve_prop(props: dict[str, str], key: str) -> str:
        """Look up a property value case-insensitively.

        Args:
            props: Property dictionary.
            key: Property name.

        Returns:
            Property value or empty string.
        """
        if key in props:
            return props[key]
        key_lower: str = key.lower()
        for k, v in props.items():
            if k.lower() == key_lower:
                return v
        return ""

    @staticmethod
    def _is_power_net(net_name: str) -> bool:
        """Check if a net name is a power/ground net.

        Args:
            net_name: Net name string.

        Returns:
            True if this is a power or ground net.
        """
        upper: str = net_name.upper()
        power_prefixes: tuple[str, ...] = (
            "VCC", "VDD", "GND", "VSS", "AGND", "DGND",
            "PGND", "SGND", "POWER", "GROUND",
        )
        return any(upper.startswith(p) for p in power_prefixes)

    @staticmethod
    def _map_coords_to_dehdl(instances: list) -> dict[str, tuple[int, int]]:
        """Map CIS (DSN) raw coordinates to DEHDL C SIZE PAGE coordinates.

        CIS/DSN coordinates are typically small values (e.g. 0~256, 0~847)
        while DEHDL C SIZE PAGE has range (-10750, 0) × (0, 8275).
        This method scales and centres the CIS layout into the C page
        available area.

        Instances at exactly (0, 0) are treated as having no valid DSN
        coordinates and are excluded from both the bounding-box calculation
        and the output mapping.

        Args:
            instances: List of ComponentInstanceIR objects with
                       ``loc_x`` / ``loc_y`` attributes.

        Returns:
            Dict mapping ``instance.refdes`` → ``(dehdl_x, dehdl_y)``.
            Only instances with valid (non-zero) coordinates are included.
        """
        # ── Collect valid (non-zero) coordinates ────────────────────
        # v0.7.0: Aligned filter with generate_hdl_sch.py reference —
        # only include components where BOTH x and y are non-zero.
        positions: list[tuple[str, float, float]] = [
            (inst.refdes, float(inst.loc_x), float(inst.loc_y))
            for inst in instances
            if inst.loc_x and inst.loc_y
        ]
        if not positions:
            return {}

        xs: list[float] = [p[1] for p in positions]
        ys: list[float] = [p[2] for p in positions]
        min_x: float = min(xs)
        max_x: float = max(xs)
        min_y: float = min(ys)
        max_y: float = max(ys)

        cis_w: float = max(max_x - min_x, 1.0)
        cis_h: float = max(max_y - min_y, 1.0)
        cis_cx: float = (min_x + max_x) / 2.0
        cis_cy: float = (min_y + max_y) / 2.0

        # ── C SIZE PAGE available area (with margins) ──────────────
        page_x0: int = -10200
        page_x1: int = -550
        page_y0: int = 400
        page_y1: int = 7200
        page_cx: float = (page_x0 + page_x1) / 2.0
        page_cy: float = (page_y0 + page_y1) / 2.0
        page_w: int = page_x1 - page_x0
        page_h: int = page_y1 - page_y0

        scale: float = min(page_w / cis_w, page_h / cis_h) * 0.7

        result: dict[str, tuple[int, int]] = {}
        for refdes, cis_x, cis_y in positions:
            dx: float = cis_x - cis_cx
            dy: float = cis_y - cis_cy
            dehdl_x: int = int(page_cx + dx * scale)
            # Y-axis inversion: CIS Y-down → DEHDL Y-up
            dehdl_y: int = int(page_cy - dy * scale)
            result[refdes] = (dehdl_x, dehdl_y)

        logger.debug(
            "Coordinate mapping: %d instances → C SIZE PAGE, "
            "scale=%.4f, cis_range=(%.0f,%.0f)×(%.0f,%.0f)",
            len(result), scale, min_x, max_x, min_y, max_y,
        )
        return result


    @staticmethod
    def _grid_position(index: int) -> tuple[int, int]:
        """Calculate grid position for auto-layout.

        Args:
            index: Zero-based instance index.

        Returns:
            (x, y) coordinate pair.
        """
        col: int = index % _GRID_COLS
        row: int = index // _GRID_COLS
        x: int = _GRID_START_X + col * _GRID_STEP_X
        y: int = _GRID_START_Y - row * _GRID_STEP_Y
        return x, y

    # ------------------------------------------------------------------
    #  Symbol.css property offset resolution
    # ------------------------------------------------------------------

    def _get_prop_offsets(self, body_name: str) -> dict[str, tuple[int, int, int, int]]:
        """Read property offsets from symbol.css for a given body name.

        Parses the ``symbol.css`` file at
        ``<hdl_lib_path>/<body_name>/sym_1/symbol.css`` to extract
        (x, y, rotation, justification) tuples for each property.

        Results are cached in ``_prop_offset_cache``.

        Args:
            body_name: The HDL component body directory name.

        Returns:
            Dict mapping property name → (x, y, rot, just).
            Empty dict if symbol.css is not found or unparseable.
        """
        if body_name in self._prop_offset_cache:
            return self._prop_offset_cache[body_name]

        if not self._hdl_lib_path:
            self._prop_offset_cache[body_name] = {}
            return {}

        css_path: Path = self._hdl_lib_path / body_name.lower() / "sym_1" / "symbol.css"
        if not css_path.exists():
            # Also try with original case
            css_path = self._hdl_lib_path / body_name / "sym_1" / "symbol.css"

        if not css_path.exists():
            logger.debug("symbol.css not found for body '%s' at %s", body_name, css_path)
            self._prop_offset_cache[body_name] = {}
            return {}

        offsets: dict[str, tuple[int, int, int, int]] = {}
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or not line.startswith("P "):
                        continue

                    # Parse P "KEY" "VALUE" x y [rot flags just ...]
                    parts = line.split('"')
                    if len(parts) < 5:
                        continue

                    prop_name: str = parts[1]
                    coords_str: str = parts[4].strip()
                    coords: list[str] = coords_str.split()
                    if len(coords) < 2:
                        continue

                    try:
                        px: int = int(float(coords[0]))
                        py: int = int(float(coords[1]))
                    except (ValueError, IndexError):
                        continue

                    tokens: list[str] = line.strip().split()
                    rot: int = 0
                    just: int = 1
                    # Reference format: P "KEY" "VAL" x y r0 r1 r2 r3 just r4 ...
                    # Token layout: [0]=P, [1]="KEY", [2]="VAL", [3]=x, [4]=y,
                    #               [5..n]=flags
                    if len(tokens) >= 10:
                        try:
                            just = int(tokens[8])
                        except (ValueError, IndexError):
                            just = 1

                    offsets[prop_name] = (px, py, rot, just)

        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Failed to read symbol.css %s: %s", css_path, exc)

        self._prop_offset_cache[body_name] = offsets
        logger.debug(
            "Loaded %d property offsets from %s for body '%s'",
            len(offsets), css_path, body_name,
        )
        return offsets

    # ═══════════════════════════════════════════════════════════════════
    #  Phase XI P0-C: connectivity-model CSA (LASTPIN/WIRE/DOT/SIG_NAME)
    #
    #  system_design.md Part B.  Body coordinates come from CoordTransform
    #  (shared with csv); pin coordinates = body + symbol.css C offset;
    #  WIRE endpoints coincide with pin coordinates (Cadence connection
    #  rule).  One SIG_NAME per net; DOT at every >=2-segment junction.
    # ═══════════════════════════════════════════════════════════════════

    def write_all_with_conn(
        self,
        conn: "DesignConnectivity",
        mgr: OutputManager,
    ) -> list[Path]:
        """Generate .csa files for all pages from the shared connectivity model.

        Phase XIV D5: 若 ``aesthetic.report`` 开启，全部页面生成后统一写出
        ``aesthetic_report.txt``（D1 文本 / D2 重叠 / 网格统计）。

        Args:
            conn: DesignConnectivity built by ConnectivityModelBuilder.
            mgr: Pre-configured OutputManager.

        Returns:
            List of generated .csa file paths.
        """
        # Phase XVI T2: skip_orphan 预计算孤立 IOPORT 网名（DesignConnectivity
        # 模型；raw PageIR 直测会 100% 误报）。
        if self._routing_cfg.ioport.skip_orphan:
            from .ioport_audit import IOPortAuditor
            self._orphan_ioport_names = IOPortAuditor.orphan_ioport_names(
                conn, self._routing_cfg.ioport.manual_names,
            )
        files: list[Path] = []
        for page_conn in conn.pages:
            content = self._build_csa_content_conn(conn, page_conn)
            files.append(mgr.write_csa_page(page_conn.page_num, content))
            if self._aesthetic_report is not None:
                off_labels, off_wires = self._count_off_grid(content)
                self._aesthetic_report.add_grid_stats(
                    off_labels, off_wires,
                )
        # Phase XVI T2: 审计收尾（网名一致性 + 孤立）+ 报告写出。
        if self._ioport_auditor is not None:
            if not self._ioport_audit_called:
                self._ioport_auditor.mark_wires_skipped()
            self._ioport_auditor.finalize(conn)
            self._ioport_auditor.write(mgr.output_root)
        # Phase XV P0-F: persist generated placeholder symbols into the
        # output HDL library (cds.lib DEFINE hdl_lib ./hdl_lib) so Cadence
        # can render the FORCEADD cells.
        if self._placeholder_lib is not None:
            placeholder_root = mgr.output_root / "hdl_lib"
            if placeholder_root.exists() or placeholder_root.parent.exists():
                try:
                    files.extend(
                        self._placeholder_lib.write_to_hdl_lib(placeholder_root)
                    )
                except Exception as exc:
                    logger.warning(
                        "placeholder lib write failed (%s): %s",
                        placeholder_root, exc,
                    )
        # Phase XVII M1: persist generated mock icons into output/temp_lib/
        # （独立目录，不污染 hdl_lib；用户 D9：temp_lib 不提交 git）。
        if self._mock_lib is not None and self._mock_lib.enabled:
            temp_lib_root = mgr.output_root / self._mock_lib.lib_name
            try:
                files.extend(self._mock_lib.write_to_temp_lib(temp_lib_root))
            except Exception as exc:
                logger.warning(
                    "mock icon lib write failed (%s): %s",
                    temp_lib_root, exc,
                )
        # Phase XVII M6: 引脚连接审计（只读诊断，基于 DesignConnectivity）。
        if self._routing_cfg.pin_audit.enabled:
            try:
                from .pin_connect_audit import PinConnectAuditor
                auditor = PinConnectAuditor(
                    enabled=True,
                    report_hanging=self._routing_cfg.pin_audit.report_hanging,
                )
                audit_result = auditor.audit(conn)
                report_path = auditor.write(audit_result, mgr.output_root)
                if report_path is not None:
                    files.append(report_path)
            except Exception as exc:
                logger.warning("pin audit failed: %s", exc)
        if self._aesthetic_report is not None:
            self._aesthetic_report.project_name = getattr(
                conn, "cell_name", "",
            ) or ""
            self._aesthetic_report.write(mgr.output_root)
        return files

    @staticmethod
    def _count_off_grid(content: str) -> tuple[int, int]:
        """统计 CSA 内容中偏离 25 网格的标签坐标与 WIRE 坐标。

        Args:
            content: .csa 页面内容。

        Returns:
            (off_grid_labels, off_grid_wires)。
        """
        import re as _re

        off_labels = 0
        for _m in _re.finditer(r"^(DISPLAY|FORCEPROP)[^\n]*\((-?\d+) (-?\d+)\);", content, _re.M):
            x, y = int(_m.group(2)), int(_m.group(3))
            if x % 25 or y % 25:
                off_labels += 1
        off_wires = 0
        for _m in _re.finditer(r"WIRE 16 -1 \((-?\d+) (-?\d+)\)\((-?\d+) (-?\d+)\);", content):
            vals = [int(_m.group(i)) for i in range(1, 5)]
            if any(v % 25 for v in vals):
                off_wires += 1
        return off_labels, off_wires

    def _build_csa_content_conn(self, conn: "DesignConnectivity", page_conn) -> str:
        """Build a complete .csa MACRO_DRAWING page from connectivity model.

        Phase XIII T2 structure (04p4 evidence): each component's
        FORCEADD block is immediately followed by that component's own
        LASTPIN pins ($PN / SIG_NAME).  Cadence 16.6 binds a LASTPIN to
        the most recent FORCEADD component; emitting all LASTPINs at the
        file end (after the IOPORT blocks) made them attach to the last
        IOPORT symbol and get deleted (SPCOCN-543/541).  WIRE/DOT/SIG_NAME
        stay at the file end (04p4 page15 L11643+).
        """
        from .coord_transform import CoordTransform

        lines: list[str] = []
        a = lines.append

        a("FILE_TYPE = MACRO_DRAWING;")
        a("SET COLOR_WIRE YELLOW;")
        a("SET COLOR_PROP ORANGE;")
        a("SET COLOR_DOT WHITE;")
        a("SET COLOR_ARC YELLOW;")
        a("SET COLOR_BODY GREEN;")
        a("SET COLOR_NOTE PURPLE;")
        a("SET PROP_DISPLAY VALUE;")
        a(f"SET PAGE_NUMBER P{page_conn.page_num};")

        # ── C SIZE PAGE border block (required by Cadence DEHDL) ────
        lines.extend(self._csa_page_frame_block(page_conn.page_name))

        # ── Body coordinates (CoordTransform, shared with csv) ──────
        coord_map = CoordTransform.map_page_instances(page_conn.instances)
        body_coords: dict[str, tuple[int, int]] = {}
        for irec in page_conn.instances:
            if irec.refdes in coord_map:
                body_coords[irec.refdes] = coord_map[irec.refdes]
            elif irec.is_power_symbol:
                body_coords[irec.refdes] = CoordTransform.power_symbol_position(
                    irec.page_local_k
                )
            else:
                body_coords[irec.refdes] = CoordTransform.grid_position(
                    irec.page_local_k - 1
                )

        # ── Pass 1: pin geometry (data only, no output) ─────────────
        # body (grid-snapped) + symbol.css offset → pin_coords; the same
        # pin_coords feed BOTH the LASTPIN labels and the WIRE endpoints,
        # so they stay exactly coincident (Cadence's only connection rule).
        # Phase XVII M8: chip_config placement 覆盖写回 body 坐标偏移。
        for _ref, _off in self._placement_offsets.items():
            if _ref in body_coords:
                body_coords[_ref] = (
                    body_coords[_ref][0] + _off[0],
                    body_coords[_ref][1] + _off[1],
                )

        # ── Phase XX 补丁 2：OverlapResolver 接线（被动/connector 微调）──
        # OverlapResolver 自 Phase XVII 已实现但**从未接线**（死代码）；
        # 用户 08-13 复测 p16/p17/p21：J/T 元件互相重叠、与电容叠一起，
        # "没有避让措施"。接线：passive（C/R/L/D/FB/LED）+ connector
        # （J/T/JP/CN/IC）为可动件、芯片/电源/端口为固定件，微调 ≤
        # ``placement.max_passive_move``（默认 50，芯片本体不动 D10）。
        # **必须在 _compute_pin_geometry 之前**：body 位移后 pin_coords/
        # LASTPIN/WIRE 用新 body 重算（否则 LASTPIN miss / 543 回归）。
        if getattr(self._routing_cfg.overlap, "resolve", False):
            try:
                _pre_map = self._collect_body_outlines_map(
                    conn, page_conn, body_coords)
                from .overlap_resolver import OverlapResolver
                _resolver = OverlapResolver(
                    margin=self._routing_cfg.overlap.avoid_margin,
                    grid=50,  # Cadence WIRE 端点 50 栅格（默认 25 会 off-grid）
                )
                _movables: dict[str, tuple[int, int, int, int]] = {}
                _fixed: list[tuple[int, int, int, int]] = []
                for _irec in page_conn.instances:
                    _rect = _pre_map.get(_irec.refdes)
                    if _rect is None:
                        continue
                    _pfx = self._ref_prefix(_irec.refdes)
                    if (_pfx in ("C", "R", "L", "D", "FB", "LED", "FERRITE",
                                 "Y", "X", "TP", "MH", "NH")
                            or _pfx in ("J", "T", "JP", "CN", "IC", "XS", "P")):
                        _movables[_irec.refdes] = _rect
                    else:
                        _fixed.append(_rect)
                if _movables:
                    _rres = _resolver.resolve_passives(
                        _movables, _fixed,
                        max_move=getattr(
                            self._routing_cfg.placement, "max_passive_move", 50),
                    )
                    for _ref, (_dx, _dy) in _rres.displacements.items():
                        _bx, _by = body_coords[_ref]
                        # Phase XXII D8/Q5：位移后 snap 50 网格（50 也是 25
                        # 网格）——兜底 body 原始坐标非 50 倍数场景，保证
                        # 位移后 pin/LASTPIN/WIRE 全部落在 50 栅格。
                        body_coords[_ref] = (
                            self._snap50(_bx + _dx), self._snap50(_by + _dy),
                        )
            except Exception as _exc:  # 解析失败不阻塞转换
                logger.warning("OverlapResolver 失败（降级继续）: %s", _exc)

        pin_coords, _pin_name_map, net_pin_map = self._compute_pin_geometry(
            conn, page_conn, body_coords
        )
        source_pins = self._choose_sig_name_sources(net_pin_map)

        # ── Phase XXIII P1-4: 被动元件符号方向随连线（rotate_passives）──
        # 生成符号后、布线前调用 orientation_planner.apply_passive_orientation
        # （默认关——默认行为等价；CLI --rotate-passives 开启）。旋转会
        # 改写 pin_coords / net_pin_map / _effective_views / outline_map，
        # 故必须在 pin_bodies 与 body_outlines 计算**之前**完成。
        outline_map = self._collect_body_outlines_map(conn, page_conn, body_coords)
        if self._routing_cfg.placement.rotate_passives:
            try:
                self._apply_passive_orientation(
                    conn, page_conn, body_coords, pin_coords, net_pin_map,
                    outline_map,
                )
            except Exception as _exc:  # 旋转失败不阻塞转换
                logger.warning("passive orientation failed: %s", _exc)

        # ── Routing + text layout (pre-computed so labels can offset) ─
        # Phase XIV D5: 布线器由工厂创建（依赖注入）；异常 → 回退 p0_lane。
        # Phase XV P1-G: pin → body-center hints 供 DetourRouter 决定
        # stub 引出方向（背离元件体）。
        pin_bodies: dict[tuple[int, int], tuple[int, int]] = {}
        for irec in page_conn.instances:
            bx, by = body_coords[irec.refdes]
            for pre in irec.pins:
                key = f"{irec.refdes}.{pre.pin_number}"
                coord = pin_coords.get(key)
                if coord is not None:
                    pin_bodies[coord] = (bx, by)
        body_outlines = list(outline_map.values())

        # ── Phase XXII D4: 并联扩展到所有信号（P1-5，Q4 仅接线）────
        # 路由前对非 GND 同信号引脚簇（间距 ≤ ``wire_simplify.
        # parallel_short_dist``）做 hub 短接计划（plan_parallel_short），
        # 构造**路由专用** route_map：簇内引脚替换为合成 hub 引脚
        # ``PARALLEL_HUB_<net>_<k>``（只进 route_map，不进 net_pin_map /
        # LASTPIN / source_pins）；路由后短接段并入对应网 —— 每簇
        # WIRE 段数 = 簇内引脚数（hub 短接）+ 1（引出）。端点 = 引脚
        # 坐标不变（坐标唯一原则）。
        _route_map: dict[str, list[dict]] = dict(net_pin_map)
        _short_wires_by_net: dict[str, list] = {}
        if self._routing_cfg.wire_simplify.parallel_short:
            try:
                from .wire_simplifier import plan_parallel_short

                _pdist = int(getattr(
                    self._routing_cfg.wire_simplify, "parallel_short_dist", 500,
                ) or 500)
                _gnd_display = self._gnd_net_display(net_pin_map)
                # 已占用坐标：全部真实引脚 + 后续分配的 hub（跨网 hub 不得
                # 重合 —— 否则两网 hub 引出段共线 → DEHDL 短路）。
                _used_hub: set[tuple[int, int]] = {
                    tuple(c) for c in pin_coords.values()
                }
                for _nd, _pins in list(_route_map.items()):
                    if _nd == _gnd_display:
                        continue  # GND 簇已由 gnd_cluster_planner 处理
                    _coords = [
                        (int(p["coord"][0]), int(p["coord"][1]))
                        for p in _pins
                        if not str(p.get("refdes", "")).startswith("IOPORT_")
                    ]
                    if len(_coords) < 2:
                        continue
                    _clusters, _ = plan_parallel_short(
                        _coords, max_dist=_pdist,
                        stub_lead=int(
                            getattr(self._routing_cfg, "stub_lead", 100) or 100
                        ),
                        outlines=body_outlines,
                    )
                    if not _clusters:
                        continue
                    # 逐簇处理：hub 坐标唯一（+50 递增直到空闲，仍 25 网格）。
                    from .gnd_cluster_planner import route_cluster_parallel
                    _short: list = []
                    _hub_for_pin: dict[tuple[int, int], tuple[int, int]] = {}
                    for _hub, _members in _clusters:
                        _hub2 = _hub
                        while _hub2 in _used_hub:
                            _hub2 = (_hub2[0] + 50, _hub2[1])
                        _used_hub.add(_hub2)
                        for _mp in _members:
                            _hub_for_pin[_mp] = _hub2
                        # 用最终 hub 重算该簇短接段（端点=引脚坐标不变）。
                        _short.extend(route_cluster_parallel(
                            _members, hub=_hub2, outlines=body_outlines,
                            stub_lead=int(
                                getattr(self._routing_cfg, "stub_lead", 100)
                                or 100
                            ),
                        ))
                    _short_wires_by_net[_nd] = list(_short)
                    _new_pins: list[dict] = []
                    for _p in _pins:
                        _c = (int(_p["coord"][0]), int(_p["coord"][1]))
                        _h = _hub_for_pin.get(_c)
                        if _h is not None:
                            _new_pins.append({
                                "refdes": f"PARALLEL_HUB_{_nd}_{len(_new_pins)}",
                                "pin": "H", "coord": _h,
                                "is_power_symbol": False,
                            })
                        else:
                            _new_pins.append(_p)
                    _route_map[_nd] = _new_pins
            except Exception as _exc:  # 并联规划失败不阻塞转换
                logger.warning("parallel_short planning failed: %s", _exc)

        routed_nets = self._route_nets(
            _route_map, body_outlines, conn, page_conn, pin_bodies=pin_bodies,
        )

        # ── Phase XXII D4: 短接段并入对应网（端点 = 引脚坐标不变）──
        # 路由后把簇内短接段并入 routed.wires + 重算 dots + 去重
        # （与 _gnd_cluster_wires 合并同区）。
        if _short_wires_by_net:
            from .wire_layout import RoutedNet, WireLayoutEngine, WireSegment

            for _nd, _short in _short_wires_by_net.items():
                if not _short:
                    continue
                _rn = routed_nets.get(_nd)
                if _rn is None:
                    _rn = RoutedNet(net_name=_nd, pins=[], wires=[])
                    routed_nets[_nd] = _rn
                _existing = list(_rn.wires)
                # 重建 wires（先清空，避免旧列表 + 追加导致整网翻倍）。
                _rn.wires = []
                _seen: set[tuple] = set()
                for _w in _existing + [WireSegment(*s) for s in _short]:
                    if (_w.x1, _w.y1) == (_w.x2, _w.y2):
                        continue
                    _key = ((_w.x1, _w.y1), (_w.x2, _w.y2))
                    _rkey = ((_w.x2, _w.y2), (_w.x1, _w.y1))
                    if _key in _seen or _rkey in _seen:
                        continue
                    _seen.add(_key)
                    _rn.wires.append(_w)
                _rn.dots = WireLayoutEngine().compute_dots(_rn.wires)

        # Phase XXI I（用户 Cadence 16.6 实测 P19"电线穿芯片/元件"）：
        # P0 trunk 已避让 outline（Phase XIII T4），但 stub 直线段对框内
        # 引脚（真实库元件）可能穿过元件体 —— 记录到 aesthetic_report
        # [WIRE_THROUGH_BODY]（完整绕障由 detour 布线器承担，p0 不阻塞）。
        # Phase XXII D2：真实库引脚在 outline 内，P→E 引出段必然穿过自己
        # 的 outline —— 正常电气引出豁免（不计入 violations）；穿**其他**
        # 元件 / 电源符号挂轨的段分类记录（self-pin / power_symbol reason）。
        if (self._aesthetic_report is not None
                and getattr(self._routing_cfg.report, "aesthetic", True)):
            try:
                from .wire_layout import WireLayoutEngine
                # Phase XXIII R-2：读取布线器 trunk_blocked 标记（trunk
                # 无解回退直穿）——violations 分项统计 reason=trunk_blocked。
                _trunk_blocked: set[str] = set()
                _trunk_line: dict = {}
                if getattr(self, "_last_router", None) is not None:
                    _trunk_blocked = set(
                        getattr(self._last_router, "_trunk_blocked_nets", set())
                        or set()
                    )
                    _trunk_line = dict(
                        getattr(self._last_router, "_trunk_line", {}) or {}
                    )
                for _net_display, _routed in routed_nets.items():
                    _cross = WireLayoutEngine.wires_through_bodies(
                        _routed.wires, body_outlines,
                    )
                    for _seg, _body in _cross:
                        _exempt, _reason = self._wire_through_body_exempt(
                            _seg, _body, outline_map, pin_coords,
                            net_display=_net_display,
                        )
                        # trunk 无解回退直穿（密集页不可避免）：非豁免穿体
                        # 且段落在该网 trunk 线上 → reason=trunk_blocked。
                        if (not _exempt and _net_display in _trunk_blocked):
                            _tinfo = _trunk_line.get(_net_display)
                            if _tinfo is not None and self._seg_on_trunk(
                                _seg, _tinfo,
                            ):
                                _reason = "trunk_blocked"
                        self._aesthetic_report.add_wire_through_body(
                            page_conn.page_num, _net_display, _seg, _body,
                            exempt=_exempt, reason=_reason,
                        )
            except Exception as _exc:  # 记录失败不阻塞转换
                logger.warning("wire-through-body report failed: %s", _exc)

        # Phase XVII M4: wire_simplify 后处理（SKiDL cleanup_wires 移植；
        # 默认关，开启后化简 WIRE/DOT：共线合并/悬空 stub 修剪/jog 化简/
        # 仅 T/X 真交点 DOT）。
        _break_labels: list[tuple[tuple[int, int], str]] = []
        if self._routing_cfg.wire_simplify.enabled:
            try:
                from .wire_simplifier import simplify_wires
                wscfg = self._routing_cfg.wire_simplify
                for net_display, routed in list(routed_nets.items()):
                    segs = [
                        (w.x1, w.y1, w.x2, w.y2) for w in routed.wires
                    ]
                    pins = [tuple(p["coord"]) for p in (net_pin_map.get(
                        net_display, []) or []) if isinstance(p, dict)]
                    if not segs:
                        continue
                    res = simplify_wires(
                        segs, pins, dot_merge=wscfg.dot_merge,
                        max_wire_len=wscfg.max_wire_len,
                        obstacles=body_outlines,
                        break_long=bool(getattr(wscfg, "break_long", False)),
                        net_display=net_display,
                    )
                    routed.wires = [type(routed.wires[0])(*s) for s in res.wires] \
                        if routed.wires else []
                    routed.dots = res.junctions
                    # R8: 超长断口 → 网络名标签（SIG_NAME，远程连接语义）。
                    if wscfg.break_long:
                        _break_labels.extend(res.net_labels)
            except Exception as exc:
                logger.warning(
                    "wire_simplify failed (%s) → keep original wires", exc,
                )

        # Phase XVIII R6: GND 簇内并联短接段注入（hub 短接 + 1 条引出）。
        # 聚类计划（_plan_and_inject_gnd_symbols）在 parallel_short 时把
        # GND 组改为"仅符号引脚"（单引脚网 → 路由器跳过），此处把预计算
        # 的簇内 WIRE 段挂回对应组 —— 端点 = 引脚坐标不变（坐标唯一原则）。
        _cluster_wires = getattr(self, "_gnd_cluster_wires", {}) or {}
        _page_cluster = _cluster_wires.get(page_conn.page_num, {}) or {}
        if _page_cluster:
            from .wire_layout import RoutedNet, WireLayoutEngine, WireSegment

            for _gkey, _segs in _page_cluster.items():
                _segs = list(_segs or [])
                if not _segs:
                    continue
                _ws = [WireSegment(*s) for s in _segs]
                _rn = routed_nets.get(_gkey)
                if _rn is None:
                    _rn = RoutedNet(net_name=_gkey, pins=[], wires=_ws)
                    routed_nets[_gkey] = _rn
                else:
                    _rn.wires = list(_rn.wires) + _ws
                _rn.dots = WireLayoutEngine().compute_dots(_rn.wires)

        # Phase XVI T2: IOPORT 接线核对（B.1.1）—— 基于 DesignConnectivity
        # 模型（stage 后、pin_connections 已注入）+ 页级 routed_nets。
        if self._ioport_auditor is not None:
            self._ioport_audit_called = True
            self._ioport_auditor.audit_page(
                page_conn, net_pin_map, routed_nets,
                ioport_list=list(self._page_ioports(page_conn)),
            )

        # Phase XIV D1: 文本去冲突 —— 只动标签坐标，绝不碰 LASTPIN/WIRE。
        label_offsets: dict[str, tuple[int, int]] = {}
        label_orient: dict[str, int] = {}
        if self._routing_cfg.text_layout.enabled:
            optimizer = self._get_text_optimizer()
            _off_count = len(getattr(page_conn, "off_pages", []) or [])
            _ioport_positions = [
                self._ioport_position_cfg(i) for i in range(_off_count)
            ]
            result = optimizer.optimize(
                page_conn, body_coords, pin_coords, routed_nets, net_pin_map,
                ioport_positions=_ioport_positions,
            )
            label_offsets = result.offsets
            label_orient = result.label_orient  # Phase XXII D7
            if self._aesthetic_report is not None:
                self._aesthetic_report.add_text_stats(
                    result.collisions_before, result.collisions_after,
                    result.unresolved,
                )
                self._aesthetic_report.add_align_stats(
                    result.net_align, result.port_align,
                    result.diff_ok, result.diff_total,
                )
            logger.debug(
                "text_layout page %d: collisions %d → %d, offsets=%d",
                page_conn.page_num, result.collisions_before,
                result.collisions_after, len(result.offsets),
            )

        # ── Pass 2: FORCEADD + inline LASTPIN per instance ──────────
        # Every non-power instance block carries its own LASTPIN pins so
        # Cadence binds them to the right component (Q1/SPCOCN-543 fix).
        # Power symbols already carry their LASTPIN SIG_NAME inside
        # _emit_power_symbol_block (skipped here → one SIG_NAME per net).
        for irec in page_conn.instances:
            x, y = body_coords[irec.refdes]
            # Phase XV P0-F: placeholder body name replaces a mismatched
            # fallback; the placeholder's outline is used for the body rect.
            body_name, placeholder = self._effective_body(conn, irec)
            lastpin_lines: list[str] = []
            if not irec.is_power_symbol:
                lastpin_lines = self._lastpins_for_instance(
                    conn, page_conn, irec, pin_coords, source_pins,
                    body_coord=(x, y),
                )
            lines.extend(self._emit_conn_instance_block(
                conn, irec, body_name, x, y, lastpin_lines=lastpin_lines,
                label_offsets=label_offsets, label_orient=label_orient,
                placeholder=placeholder,
            ))

        # ── Phase XV P1-D: synthetic per-chip GND symbols ────────────
        # Planned inside _compute_pin_geometry (net_pin_map already
        # contains their pins so routing reaches them); here we emit their
        # FORCEADD power-symbol blocks right after the component instances.
        for _idx, _sym in enumerate(
            self._page_gnd_symbols.get(page_conn.page_num, []) or []
        ):
            _sym_irec = type(
                "SyntheticPowerSymbol", (), {
                    "power_nets": [_sym["net"]],
                    "is_power_symbol": True,
                    "page_local_k": 3000 + _idx,
                    "section": 1,
                    "properties": {},
                },
            )()
            lines.extend(self._emit_power_symbol_block(
                conn, _sym_irec, "GND_POWER", _sym["x"], _sym["y"],
            ))

        # ── Phase XI P0-C5: cross-page IOPORT symbols ───────────────
        # Self-contained blocks (their own level-1 LASTPIN) placed after
        # all component instances — no subsequent LASTPIN emission exists,
        # so they cannot steal any component's pins.
        # Phase XVI T2: ``_page_ioports`` 提供 effective idx（skip_orphan
        # 跳过孤立 connector 后 idx 连续），与 Pass 1 入网一致。
        # Phase XVII M5 (用户 D2): ``ioport.use_net_name=true`` 时不生成
        # IOPORT 符号（跨页连接由同名网络名 SIG_NAME 表达）。
        _use_net_name = bool(self._routing_cfg.ioport.use_net_name)
        if not _use_net_name:
            for _idx, _op in self._page_ioports(page_conn):
                lines.extend(self._emit_ioport_block(
                    conn, page_conn, _op, _idx,
                    label_offsets=label_offsets,
                ))

        # ── WIRE section (topology synthesis; body-aware lanes) ─────
        wire_lines: list[str] = []
        dot_lines: list[str] = []
        for _net_display, routed in routed_nets.items():
            for w in routed.wires:
                wire_lines.append(f"WIRE 16 -1 ({w.x1} {w.y1})({w.x2} {w.y2});")
            for d in routed.dots:
                dot_lines.append(f"DOT 1 ({d[0]} {d[1]});")

        if wire_lines:
            lines.append("")
            lines.extend(wire_lines)

        # ── SIG_NAME for nets without a source pin label ────────────
        # Phase XVII M5: use_net_name 时跨页网（本页无 source-pin 标签）
        # 补线上 SIG_NAME —— 网络名远程连接（用户 D2）。
        # Phase XXII D3（Q3 单一调用点）：主接线点改为
        # ``net_name_endpoints`` —— 跨页网 WIRE **悬空端**补 SIG_NAME；
        # 非跨页补全仍由下方泛化 has_label 循环承担（去重：同网不双标签）。
        # ``net_name_labels`` 保留（向后兼容）但本分支不再调用。
        _extra_sig_names: list[tuple[tuple[int, int], str]] = []
        if _use_net_name:
            try:
                from .net_name_connect import (
                    cross_page_bare_names, net_name_endpoints,
                )
                _cross = cross_page_bare_names(conn)
                _wire_segment_map = {
                    _nd: [(w.x1, w.y1, w.x2, w.y2) for w in _routed.wires]
                    for _nd, _routed in routed_nets.items()
                }
                _extra_sig_names = net_name_endpoints(
                    net_pin_map, _wire_segment_map, _cross, True,
                )
            except Exception as exc:
                logger.warning("net_name_connect failed: %s", exc)
        _extra_nets = {_net for _, _net in _extra_sig_names}
        for net_display, pins in net_pin_map.items():
            if net_display in _extra_nets:
                continue  # 去重：该网已有悬空端标签，避免同网双标签
            has_label = any(
                (p["refdes"], p["pin"]) in self._key_pairs(source_pins)
                for p in pins
            )
            if has_label:
                continue
            if pins:
                coord = pins[0]["coord"]
                # R3⑤: UN$ 网名策略（rename/omit）只改 CSA 显示名。
                _display = self._un_policy_display(net_display)
                if not _display:
                    continue
                lines.extend(self._sig_name_on_wire(
                    coord, _display, label_offsets=label_offsets,
                ))
        for coord, net_display in _extra_sig_names:
            _display = self._un_policy_display(net_display)
            if not _display:
                continue
            lines.extend(self._sig_name_on_wire(
                coord, _display, label_offsets=label_offsets,
            ))
        # R8: 超长断线断口标签（远程连接由同名网络名表达）。
        for coord, net_display in _break_labels:
            _display = self._un_policy_display(net_display)
            if not _display:
                continue
            lines.extend(self._sig_name_on_wire(
                coord, _display, label_offsets=label_offsets,
            ))

        # ── DOT section ─────────────────────────────────────────────
        if dot_lines:
            lines.append("")
            lines.extend(dot_lines)

        # ── Phase XIV D2: overlap detection (report only) ───────────
        if (self._routing_cfg.overlap.check
                and self._aesthetic_report is not None):
            from .overlap_detector import OverlapDetector
            detector = OverlapDetector(
                min_area=self._routing_cfg.overlap.min_area,
            )
            detector.detect_and_report(
                page_conn, body_coords, self._aesthetic_report,
                outlines_by_refdes=outline_map,
            )

        lines.append("QUIT")
        return "\n".join(lines) + "\n"

    def _route_nets(
        self,
        net_pin_map: dict[str, list],
        body_outlines: list[tuple[int, int, int, int]],
        conn: "DesignConnectivity",
        page_conn,
        pin_bodies: dict[tuple[int, int], tuple[int, int]] | None = None,
    ) -> dict:
        """Route page nets via the configured router (D5, with fallback).

        Phase XIV D5 回退策略：路由异常 → logger.warning → 用 p0_lane
        重试（``fallback_to_p0``）。csa_writer 不 import 具体布线器类，
        只依赖 ``router_base.create_router`` 抽象层。

        Phase XV P1-G: ``pin_bodies``（引脚坐标 → 元件体中心）透传给
        DetourRouter，用于 stub 引出段方向。

        Args:
            net_pin_map: 网显示名 → 引脚列表。
            body_outlines: 元件轮廓矩形。
            conn: DesignConnectivity（EDIFWireRouter 需要 design 上下文）。
            page_conn: PageConnectivity。
            pin_bodies: 引脚绝对坐标 → 体中心映射（可选）。

        Returns:
            ``{net_display: RoutedNet}``。
        """
        from .router_base import ROUTER_REGISTRY, create_router

        mode = self._routing_cfg.mode
        try:
            router = self._router or create_router(mode, self._routing_cfg)
            # Phase XXIII R-2: 保存布线器实例供 wire-through-body 报告
            # 读取 trunk_blocked 标记（trunk 无解回退直穿）。
            self._last_router = router
            return router.route_nets(
                net_pin_map, body_outlines,
                design=getattr(conn, "design", None), page=page_conn,
                pin_bodies=pin_bodies or {},
            )
        except Exception as exc:
            if not self._routing_cfg.fallback_to_p0:
                raise
            logger.warning(
                "router %s failed (%s) → fallback p0_lane", mode, exc,
            )
            self._last_router = ROUTER_REGISTRY["p0_lane"](self._routing_cfg)
            return self._last_router.route_nets(
                net_pin_map, body_outlines,
            )

    def _get_text_optimizer(self):
        """Return the injected TextLayoutOptimizer or a lazy default."""
        if self._text_optimizer is None:
            from .text_layout import TextLayoutOptimizer
            self._text_optimizer = TextLayoutOptimizer(self._routing_cfg.text_layout)
        return self._text_optimizer

    def _compute_pin_geometry(
        self,
        conn: "DesignConnectivity",
        page_conn,
        body_coords: dict[str, tuple[int, int]],
    ) -> tuple[dict, dict, dict]:
        """Pass 1: compute pin coordinates / net-pin map (no output).

        Returns:
            ``(pin_coords, pin_name_map, net_pin_map)`` where
            ``pin_coords["<refdes>.<pin_number>"]`` is the absolute
            (body + rotated css offset) coordinate shared by LASTPIN and
            WIRE endpoints.  Cross-page IOPORT pins are appended to their
            page net's net_pin_map so routing covers them (04p4 evidence:
            WIRE (-4425 -1400)(-3950 -1400) reaches an IOPORT pin).
        """
        from .coord_transform import closest_rotation_for_mirror, rotate_point

        pin_coords: dict[str, tuple[int, int]] = {}   # "refdes.pin" -> (x,y)
        pin_name_map: dict[str, str] = {}             # "refdes.pin" -> name
        net_pin_map: dict[str, list[dict]] = {}       # net display -> pins
        # Phase XXII D8: 每页清空引脚偏移单源（避免跨页串扰）。
        self._pin_offset_map = {}
        # Phase XXII D5: 每页清空 IOPORT 聚类槽位（edge_layout 重算）。
        self._ioport_cluster_order = {}
        # Phase XIII Round 2 (QA short-circuit): every absolute pin
        # coordinate must be unique across the page — two DIFFERENT nets
        # sharing a pin coordinate makes both nets' wires meet at that
        # point → DEHDL short.  Fallback columns of nearby bodies can
        # collide, so the second (and later) pin is nudged to the next
        # free 25-grid position (LASTPIN and WIRE share the nudged coord).
        used_pin_coords: set[tuple[int, int]] = set()
        for irec in page_conn.instances:
            body_name = irec.cell_name or self._cell_label(conn, irec.cell_id)
            section = irec.section
            if irec.is_power_symbol:
                for net_name in irec.power_nets:
                    # power symbol pin at symbol.css offset
                    # (GND +50 / VCC_CIRCLE -50; R3c GND_POWER golden (50,100))
                    # Phase XVIII R3c: 与 _emit_power_symbol_block LASTPIN
                    # 同源（坐标唯一原则）—— WIRE 端点与 LASTPIN 精确重合。
                    _off = self._power_pin_offset(body_name)
                    px, py = _off[0], _off[1]
                    # Phase XVI T1 (A.5 末): 电源符号 mirror≠0 时引脚偏移
                    # 仅镜像（不旋转，保持电源符号现有"不旋转"行为；单引脚 +
                    # SIG_NAME 连接，电气中性）；不记 _mirror_rline（电源块
                    # 不发射 R 行）。
                    _pmirror = int(getattr(irec, "mirror", 0) or 0)
                    # SPCOCN-543 修复（08-13）：plumbing 电源符号（GND_POWER/
                    # VCC_CIRCLE）**忽略 mirror** —— 图形垂直对称，且 Cadence
                    # 对 plumbing 符号的 mirror 渲染不可靠（实测 p18 GND
                    # LASTPIN=body+(0,-50) 未命中符号引脚 (0,50) → 删 SIG_NAME）。
                    if _pmirror and not self._is_plumbing_power(body_name):
                        px, py = rotate_point(px, py, 0, _pmirror)
                    bx, by = body_coords[irec.refdes]
                    _raw = (bx + px, by + py)
                    pcoord = self._unique_pin_coord(_raw, used_pin_coords)
                    if pcoord != _raw:
                        self._nudged_pin_keys.add(f"{irec.refdes}.1")
                    used_pin_coords.add(pcoord)
                    key = f"{irec.refdes}.1"
                    self._pin_offset_map[key] = (px, py)  # D8 单源
                    pin_coords[key] = pcoord
                    # resolve the page net display name so the power pin is
                    # grouped with regular pins on the same net (wire
                    # routing + one SIG_NAME per net rule); the LASTPIN
                    # SIG_NAME itself comes from the FORCEADD block
                    net_display = self._power_net_display(page_conn, net_name)
                    net_pin_map.setdefault(net_display, []).append({
                        "refdes": irec.refdes, "pin": "1",
                        "coord": pcoord, "is_power_symbol": True,
                    })
                continue
            # Phase XV P0-F: placeholder symbol replaces a missing/mismatched
            # fallback (e.g. U6 → CH347).  Its offsets come from the
            # placeholder library (same perimeter distribution as the
            # fallback), so LASTPIN/WIRE stay coincident.
            placeholder = self._placeholder_for_irec(irec, body_name, section)
            rot = int(getattr(irec, "rotation", 0) or 0)
            mirror = int(getattr(irec, "mirror", 0) or 0)
            rot_dehdl = _dehdl_rotation(rot)
            if placeholder is not None:
                offsets = placeholder.offsets
                body_name = placeholder.cell_name
                eff_section, eff_rot_dehdl = section, rot_dehdl
            else:
                # Phase XVIII R3 (Q2 方案 A): 有效视图（sym_2 切换）——
                # 坐标唯一原则：pin_coords/net_pin_map/LASTPIN/WIRE 全部
                # 由"体坐标 + 所选视图 css 偏移"派生，禁止部分沿用 sym_1。
                eff_section, eff_rot_dehdl, offsets = self._effective_view(
                    irec, body_name, section,
                )
            # Pass 2（FORCEADD/LASTPIN 发射）读取同源视图。
            self._effective_views[irec.refdes] = (eff_section, eff_rot_dehdl)
            if placeholder is not None:
                fallback = placeholder.offsets
            else:
                fallback = self._fallback_pin_offsets(
                    body_name, section, len(irec.pins)
                )
            normalize_mirror = bool(
                self._routing_cfg.mirror.normalize and mirror
            )
            if normalize_mirror:
                offsets_list = [
                    self._resolve_pin_offset(
                        irec, body_name, section, placeholder, offsets,
                        fallback, pre, pin_idx,
                    )
                    for pin_idx, pre in enumerate(irec.pins)
                ]
                _theta = closest_rotation_for_mirror(offsets_list, rot, mirror)
                _rline = _dehdl_rotation(_theta)
                self._mirror_rline[irec.refdes] = _rline
                _approx = self._mirror_is_approx(
                    offsets_list, rot, mirror, _theta,
                )
                _orient = (
                    f"{'MX' if mirror == 1 else 'MY'}"
                    f"{'R' + str(rot) if rot else ''}"
                )
                if (self._routing_cfg.mirror.report
                        and self._aesthetic_report is not None):
                    from .aesthetic_report import MirrorEntry
                    self._aesthetic_report.add_mirror(MirrorEntry(
                        page=page_conn.page_name, refdes=irec.refdes,
                        orient=_orient, rline=_rline, approx=_approx,
                    ))
            for pin_idx, pre in enumerate(irec.pins):
                key = f"{irec.refdes}.{pre.pin_number}"
                bx, by = body_coords[irec.refdes]
                off = self._resolve_pin_offset(
                    irec, body_name, section, placeholder, offsets,
                    fallback, pre, pin_idx,
                )
                if normalize_mirror:
                    # EDIF 精确镜像（镜像在前、旋转在后）
                    ox, oy = rotate_point(off[0], off[1], rot, mirror)
                    off = (ox, oy)
                elif eff_rot_dehdl:
                    # 有效视图旋转（sym_2 时 eff_rot_dehdl=0 → 不旋转）。
                    ox, oy = rotate_point(off[0], off[1], eff_rot_dehdl)
                    off = (ox, oy)
                # Phase XXII D8: key 前置（微移判断之前）—— 微移引脚自身
                # 正确记入 _nudged_pin_keys（旧 bug：记录的是上一引脚键）。
                # 同时记录实际使用的 resolved offset（LASTPIN expected 单源）。
                self._pin_offset_map[key] = (off[0], off[1])
                _raw = (bx + off[0], by + off[1])
                pcoord = self._unique_pin_coord(_raw, used_pin_coords)
                if pcoord != _raw:
                    self._nudged_pin_keys.add(key)
                used_pin_coords.add(pcoord)
                pin_coords[key] = pcoord
                pin_name_map[key] = pre.pin_name
                net_display = self._net_display_for_pin(conn, page_conn, pre.net_id)
                # Phase XI P2-2: NC pins carry no net — they must not be
                # grouped into a net (no SIG_NAME, no WIRE).  The LASTPIN
                # $PN is still emitted so the pin exists on the schematic.
                # Phase XVII M8: chip_config hanging 引脚 —— 保留 LASTPIN
                # （pin_coords 已设），但不加入 net_pin_map → 不生成 WIRE
                # （用户 R9：悬空引脚直接悬空，待 Allegro 布线）。
                if (self._hanging_pins.get(str(irec.refdes).upper(), set())
                        and str(pre.pin_number).upper() in
                        self._hanging_pins.get(str(irec.refdes).upper(), set())):
                    continue
                if net_display and net_display.strip().upper() != "NC":
                    net_pin_map.setdefault(net_display, []).append({
                        "refdes": irec.refdes, "pin": pre.pin_number,
                        "coord": pcoord, "is_power_symbol": False,
                    })

        # ── Phase XV P1-D: GND symbol distribution (per-chip groups) ──
        # User decision 1: every chip gets a GND symbol nearby; the page's
        # GND pins are re-grouped per chip so trunks stay local (the net
        # name — SIG_NAME GND\g — keeps everything electrically connected).
        if self._routing_cfg.gnd_distribution.enabled:
            gnd_plan = self._plan_and_inject_gnd_symbols(
                conn, page_conn, body_coords, pin_coords, net_pin_map,
            )
            self._page_gnd_symbols[page_conn.page_num] = gnd_plan

        # ── Phase XXIII P1-3: GND 密度补点（distribute_density）────
        # 布线前调用 gnd_cluster_planner.ensure_gnd_symbols：页面 1/4
        # 分块，每块 ≥3 个 GND 引脚且距最近 GND 符号 >1500 时在块中心
        # 补 GND_SYM_B{block}（默认关——默认行为等价；--gnd-distribute
        # 同时开启）。
        if self._routing_cfg.gnd_distribution.distribute_density:
            try:
                self._ensure_gnd_density(
                    conn, page_conn, body_coords, pin_coords, net_pin_map,
                )
            except Exception as _exc:  # 密度补点失败不阻塞转换
                logger.warning("GND density fill failed: %s", _exc)

        # ── Cross-page IOPORT pins join their page nets ─────────────
        # Phase XIII T2: the IOPORT pin coordinate (body + css C -50 0 "A")
        # is appended to the matching net so the trunk/stub routing reaches
        # the IOPORT symbol — eliminating the isolated IO block corner.
        # Phase XVI T2: ``_page_ioports`` 提供 effective idx（skip_orphan
        # 跳过孤立 connector），与 Pass 2 发射一致。
        # Phase XXII D5: edge_layout 开启时按"同网页内引脚 y 均值"重排
        # IOPORT 槽位（确定性、无重叠）；Pass 2 发射经 _ioport_position_cfg
        # 同源读取。
        self._build_ioport_cluster_order(page_conn, net_pin_map)
        for idx, _op in self._page_ioports(page_conn):
            ioport_coord = self._ioport_pin_coord(idx)
            net_name = str(_op.get("net_name", "") or _op.get("name", ""))
            net_display = self._power_net_display(page_conn, net_name)
            if net_display:
                net_pin_map.setdefault(net_display, []).append({
                    "refdes": f"IOPORT_{idx}", "pin": "A",
                    "coord": ioport_coord, "is_power_symbol": False,
                })
        return pin_coords, pin_name_map, net_pin_map

    def _resolve_pin_offset(
        self,
        irec,
        body_name: str,
        section: int,
        placeholder,
        offsets: dict,
        fallback: dict,
        pre,
        pin_idx: int,
    ) -> tuple[int, int]:
        """Resolve a pin's css offset with all fallbacks applied.

        Extracted from the Pass-1 pin loop (Phase XVI T1) so the mirror
        fit (``closest_rotation_for_mirror``) can pre-compute every pin
        offset without duplicating the resolution chain.

        Args:
            irec: InstanceRecord。
            body_name: HDL cell name（placeholder 时已替换）。
            section: Symbol view number。
            placeholder: PlaceholderSymbol 或 None。
            offsets: symbol.css C-command 偏移（或 placeholder offsets）。
            fallback: 启发式回退偏移表。
            pre: PinRecord。
            pin_idx: 引脚在实例中的位置（0-based）。

        Returns:
            ``(x, y)`` css 相对偏移。
        """
        off = None
        if placeholder is not None:
            off = placeholder.offset_for(pre.pin_number, pre.pin_name)
        else:
            off = offsets.get(pre.pin_name) or offsets.get(pre.pin_number)
        if off is None:
            # Phase XI 收尾: multi-pin ICs (e.g. CH347/U6G) put FUNCTIONAL
            # names in symbol.css C commands (RST#, TXD1) while pstxnet uses
            # numeric pin numbers.  The chips.prt map (number → functional
            # name) bridges the two so pin offsets resolve instead of
            # collapsing to (0,0).
            _num_name = self._get_pin_name_map(body_name)
            if _num_name:
                _fname = _num_name.get(str(pre.pin_number).upper())
                if _fname is None:
                    _fname = _num_name.get(str(pre.pin_number))
                if _fname:
                    off = offsets.get(_fname)
        if off is None:
            # Phase XIII T3: fallback keyed by functional pin name, then
            # numeric pin number, then the pin's POSITION in the instance.
            off = (fallback.get(pre.pin_name)
                   or fallback.get(str(pre.pin_number))
                   or fallback.get(str(pin_idx + 1))
                   or (0, 0))
        return off

    @staticmethod
    def _mirror_is_approx(
        offsets_list: list,
        rot: int,
        mirror: int,
        theta: int,
    ) -> bool:
        """True when the closest rotation does NOT exactly reproduce the
        mirror truth for every pin（approx 需人工复核）。

        Args:
            offsets_list: css 偏移列表。
            rot/mirror: EDIF rotation / mirror（镜像真值输入）。
            theta: closest_rotation_for_mirror 返回的 EDIF 角度。

        Returns:
            True = 方向近似（镜像无法用纯旋转表达）；False = 精确。
        """
        from .coord_transform import rotate_point

        for px, py in offsets_list:
            if rotate_point(px, py, rot, mirror) != rotate_point(px, py, theta):
                return True
        return False

    # ------------------------------------------------------------------
    #  Phase XV P1-D: GND symbol distribution
    # ------------------------------------------------------------------

    @staticmethod
    def _gnd_net_display(net_pin_map: dict[str, list]) -> str:
        """Return the page GND net display name (e.g. ``GND\\g``).

        Args:
            net_pin_map: Net display name → pin list (current page).

        Returns:
            The GND net display key, or ``"GND\\g"`` when not found.
        """
        for key in net_pin_map:
            bare = str(key).replace("\\g", "").lower()
            if bare in ("gnd", "gnd_power", "dgnd", "agnd", "pgnd",
                        "gnd_earth", "gnd_signal", "gnd_chassis"):
                return str(key)
        return "GND\\g"

    @staticmethod
    def _is_gnd_display(key: str) -> bool:
        """True when a net display key belongs to the GND power net.

        Phase XXIII P1-3：识别页面上全部 GND 网组键（``GND\\g`` 页面组
        与 ``GND\\g@<refdes>`` 聚类组），供密度补点收集引脚/已有符号。

        Args:
            key: Net display name (e.g. ``GND\\g`` / ``GND\\g@U1``).

        Returns:
            True for GND-family display keys.
        """
        bare = str(key).replace("\\g", "").lower().split("@", 1)[0].strip()
        return bare in (
            "gnd", "gnd_power", "dgnd", "agnd", "pgnd",
            "gnd_earth", "gnd_signal", "gnd_chassis",
        )

    def _ensure_gnd_density(
        self,
        conn: "DesignConnectivity",
        page_conn,
        body_coords: dict[str, tuple[int, int]],
        pin_coords: dict[str, tuple[int, int]],
        net_pin_map: dict[str, list],
    ) -> None:
        """Phase XXIII P1-3：GND 密度补点（``ensure_gnd_symbols`` 接线）。

        对每页 GND 网引脚做 1/4 分块，每块 ≥3 个 GND 引脚且距最近已有
        GND 符号 >1500 时在块中心补 ``GND_SYM_B{block}`` 符号并挂回页面
        GND 组（``is_power_symbol=True``），使布线覆盖新符号。电气不变
        （同一 GND\\g 网名连接）。

        Args:
            conn: DesignConnectivity。
            page_conn: PageConnectivity。
            body_coords: refdes → body (x, y)。
            pin_coords: ``refdes.pin`` → absolute (x, y)（就地追加）。
            net_pin_map: Net display name → pin list（就地追加）。
        """
        from . import gnd_cluster_planner

        cfg = self._routing_cfg.gnd_distribution
        gnd_display = self._gnd_net_display(net_pin_map)
        gnd_keys = [k for k in net_pin_map if self._is_gnd_display(k)]
        gnd_pins: list[tuple[int, int]] = []
        existing: list[tuple[int, int]] = []
        for k in gnd_keys:
            for p in net_pin_map[k]:
                if p.get("is_power_symbol"):
                    existing.append((int(p["coord"][0]), int(p["coord"][1])))
                elif not str(p.get("refdes", "")).startswith("IOPORT_"):
                    gnd_pins.append((int(p["coord"][0]), int(p["coord"][1])))
        if len(gnd_pins) < 3:
            return
        outlines = list(
            self._collect_body_outlines_map(conn, page_conn, body_coords).values()
        )
        pin_points: set[tuple[int, int]] = {
            (int(c[0]), int(c[1])) for c in pin_coords.values()
        }
        avoid_margin = int(
            getattr(self._routing_cfg.overlap, "avoid_margin", 50) or 50
        )
        page_clearance = int(
            getattr(self._routing_cfg, "edge_clearance", 100) or 100
        )
        _pin_off = self._power_pin_offset("GND_POWER")
        symbols = gnd_cluster_planner.ensure_gnd_symbols(
            gnd_pins, existing, outlines, pin_points=pin_points,
            margin=avoid_margin, pin_offset=_pin_off,
            edge_clearance=page_clearance,
        )
        if not symbols:
            return
        used_pin: set[tuple[int, int]] = set(existing)
        for s in symbols:
            spx, spy = s["pin_coord"]
            spx, spy = self._gnd_pin_coord(
                (spx, spy), used_pin, pin_points, margin=50,
            )
            used_pin.add((spx, spy))
            pin_points.add((spx, spy))
            s["pin_coord"] = (spx, spy)
            sym_refdes = s["refdes"]
            pin_coords[f"{sym_refdes}.1"] = (spx, spy)
            net_pin_map.setdefault(gnd_display, []).append({
                "refdes": sym_refdes, "pin": "1",
                "coord": (spx, spy), "is_power_symbol": True,
            })
        logger.info(
            "GND density page %d: +%d symbol(s) (pins=%d)",
            page_conn.page_num, len(symbols), len(gnd_pins),
        )

    def _plan_and_inject_gnd_symbols(
        self,
        conn: "DesignConnectivity",
        page_conn,
        body_coords: dict[str, tuple[int, int]],
        pin_coords: dict[str, tuple[int, int]],
        net_pin_map: dict[str, list],
    ) -> list[dict]:
        """Plan per-chip GND symbols and re-group the GND net (P1-D).

        User decision 1: every chip (pin_count > 1) gets a GND symbol
        near its GND pin; scattered GND pins beyond ``distance_threshold``
        get distance-filled symbols.  The page's GND ``net_pin_map`` entry
        is split into per-chip group keys (``GND\\g@<refdes>``) so trunk
        routing stays LOCAL — the shared SIG_NAME ``GND\\g`` keeps every
        group electrically connected (power-net-by-name rule).

        Phase XVII P0-3 (问题 #4/#7) + Phase XVIII R6: GND 符号不再落到
        芯片图标上/挨引脚 —— ``place_gnd_symbol``（gnd_cluster_planner）
        同时避让元件 outline（margin=avoid_margin 50）与引脚禁区
        （pin_avoid_radius 50）与页边冗余区（edge_clearance 100）。

        Args:
            conn: DesignConnectivity。
            page_conn: PageConnectivity。
            body_coords: refdes → body (x, y)。
            pin_coords: ``refdes.pin`` → absolute (x, y)。
            net_pin_map: Net display name → pin list (mutated in place).

        Returns:
            List of synthetic GND symbol dicts:
            ``{"refdes", "x", "y", "net", "pin_coord"}``.
        """
        from . import gnd_cluster_planner

        cfg = self._routing_cfg.gnd_distribution
        gnd_display = self._gnd_net_display(net_pin_map)
        gnd_pins = list(net_pin_map.get(gnd_display, []) or [])
        if not gnd_pins:
            return []

        inst_by_refdes: dict[str, object] = {
            getattr(i, "refdes", ""): i for i in page_conn.instances
        }
        # 1. Chips (multi-pin, non-power) owning GND pins.
        chip_gnd_pins: dict[str, list[dict]] = {}
        for p in gnd_pins:
            if p.get("is_power_symbol") or str(p.get("refdes", "")).startswith("IOPORT_"):
                continue
            irec = inst_by_refdes.get(str(p.get("refdes", "")))
            if irec is not None and len(getattr(irec, "pins", []) or []) > 1:
                chip_gnd_pins.setdefault(str(p["refdes"]), []).append(p)

        # Phase XVII P0-3: 避让元件 outline（膨胀 margin=25）与全部引脚坐标。
        outlines = list(
            self._collect_body_outlines_map(conn, page_conn, body_coords).values()
        )
        pin_points: set[tuple[int, int]] = {
            (int(c[0]), int(c[1])) for c in pin_coords.values()
        }

        symbols: list[dict] = []
        used_pin: set[tuple[int, int]] = set()
        used_body: set[tuple[int, int]] = set()
        regrouped: dict[str, list[dict]] = {}
        assigned_keys: set[tuple[str, str]] = set()

        # ── Phase XVII R3：GND 聚类合并（用户问题 4"就近共用"）────────
        # 距离 ≤ cluster_radius 的芯片 GND 引脚聚为同一簇，簇内共享
        # 1 个 GND 符号（默认 2000 可配，用户 D4；0 = 关闭聚类回退
        # 每芯片 1 个）。贪心最近邻：从最近的引脚对开始合并，簇中心
        # = 簇内引脚坐标质心。
        cluster_radius = int(getattr(cfg, "cluster_radius", 2000) or 0)
        chip_gnd_items = sorted(
            chip_gnd_pins.items(),
            key=lambda kv: tuple(kv[1][0]["coord"]) if kv[1] else (0, 0),
        )
        if cluster_radius > 0 and len(chip_gnd_items) > 1:
            clusters: list[list[str]] = []
            for refdes, pins in chip_gnd_items:
                coord = tuple(pins[0]["coord"])
                placed = False
                for cl in clusters:
                    ctr_x = sum(
                        int(chip_gnd_pins[r][0]["coord"][0]) for r in cl
                    ) / len(cl)
                    ctr_y = sum(
                        int(chip_gnd_pins[r][0]["coord"][1]) for r in cl
                    ) / len(cl)
                    if abs(coord[0] - ctr_x) + abs(coord[1] - ctr_y) <= cluster_radius:
                        cl.append(refdes)
                        placed = True
                        break
                if not placed:
                    clusters.append([refdes])
        else:
            clusters = [[r] for r, _p in chip_gnd_items]

        for cluster in clusters:
            cluster_pins: list[dict] = []
            for refdes in cluster:
                cluster_pins.extend(chip_gnd_pins[refdes])
            cluster_coords = [
                (int(p["coord"][0]), int(p["coord"][1])) for p in cluster_pins
            ]
            # Phase XVIII R6: GND 符号放置改调 gnd_cluster_planner.place_gnd_symbol
            # —— margin=avoid_margin(50) + 引脚禁区 + edge_clearance(100)，
            # 不落元件 outline、不贴页边。
            avoid_margin = int(
                getattr(self._routing_cfg.overlap, "avoid_margin", 50) or 50
            )
            page_clearance = int(
                getattr(self._routing_cfg, "edge_clearance", 100) or 100
            )
            _pin_off = self._power_pin_offset("GND_POWER")
            # R6 簇内并联：先算 hub（route_cluster_parallel），hub 覆盖全部
            # 簇内引脚（parallel_short + parallel_short_dist 判定）才短接。
            parallel = bool(getattr(cfg, "parallel_short", False))
            parallel_dist = int(getattr(cfg, "parallel_short_dist", 500) or 500)
            hub_rec = None
            if parallel:
                _hubs = gnd_cluster_planner.route_cluster_parallel(
                    [(gnd_display, c) for c in cluster_coords],
                    max_dist=parallel_dist,
                )
                if _hubs and _hubs[0].pin_count == len(cluster_coords):
                    hub_rec = _hubs[0]
            cand = hub_rec.hub if hub_rec is not None else cluster_coords[0]
            sx, sy = gnd_cluster_planner.place_gnd_symbol(
                cluster_coords, outlines, margin=avoid_margin,
                pin_points=pin_points, pin_offset=_pin_off,
                edge_clearance=page_clearance,
            )
            used_body.add((sx, sy))
            cluster_id = "_".join(cluster) if len(cluster) > 1 else cluster[0]
            sym_refdes = f"GND_{cluster_id}"
            spx, spy = self._gnd_pin_coord(
                (sx + int(_pin_off[0]), sy + int(_pin_off[1])),
                used_pin, pin_points, margin=50,
            )
            used_pin.add((spx, spy))
            pin_points.add((spx, spy))
            symbols.append({
                "refdes": sym_refdes, "x": sx, "y": sy,
                "net": "GND", "pin_coord": (spx, spy),
            })
            pin_coords[f"{sym_refdes}.1"] = (spx, spy)
            group_key = f"{gnd_display}@{cluster_id}"
            if hub_rec is not None:
                # 簇内引脚先并联 hub 短接，再 1 条引出到 GND 符号。
                cluster_wires = gnd_cluster_planner.hub_short_wires(
                    hub_rec, outlines,
                    stub_lead=int(getattr(cfg, "near_chip_offset", 100) or 100),
                )
                # Phase XXIII P1-3（distribute_density）：outlet→符号段
                # 受阻时 90° 折线绕行（最多 2 次）——hub_to_symbol_wire
                # 内部检查穿体；默认关时 outlines=() 零回归直连。
                symbol_wire = gnd_cluster_planner.hub_to_symbol_wire(
                    hub_rec.hub, (spx, spy),
                    outlines=outlines if bool(
                        getattr(cfg, "distribute_density", False)
                    ) else (),
                )
                self._gnd_cluster_wires.setdefault(
                    page_conn.page_num, {},
                )[group_key] = list(cluster_wires) + list(symbol_wire)
                # 组内只剩符号引脚（单引脚网，路由器跳过）——簇内 WIRE 段
                # 在路由后注入（_build_csa_content_conn）。
                regrouped[group_key] = [{
                    "refdes": sym_refdes, "pin": "1",
                    "coord": (spx, spy), "is_power_symbol": True,
                }]
            else:
                regrouped[group_key] = list(cluster_pins) + [{
                    "refdes": sym_refdes, "pin": "1",
                    "coord": (spx, spy), "is_power_symbol": True,
                }]
            for p in cluster_pins:
                assigned_keys.add((str(p["refdes"]), str(p["pin"])))

        # 2. Remaining GND pins (page group) + distance-based fill.
        remaining = [
            p for p in gnd_pins
            if (str(p.get("refdes", "")), str(p.get("pin", ""))) not in assigned_keys
        ]
        if remaining:
            regrouped[gnd_display] = list(remaining)
            fill_symbols, fill_pins = self._fill_gnd_symbols(
                remaining, symbols, used_pin, used_body, pin_coords, cfg,
                outlines=outlines, pin_points=pin_points,
            )
            symbols.extend(fill_symbols)
            regrouped[gnd_display].extend(fill_pins)

        net_pin_map.pop(gnd_display, None)
        net_pin_map.update(regrouped)
        if symbols:
            logger.info(
                "GND distribution page %d: %d chip symbol(s), %d GND pins "
                "→ %d group(s)",
                page_conn.page_num, len(symbols), len(gnd_pins), len(regrouped),
            )
        return symbols

    def _fill_gnd_symbols(
        self,
        remaining_pins: list[dict],
        existing_symbols: list[dict],
        used_pin: set[tuple[int, int]],
        used_body: set[tuple[int, int]],
        pin_coords: dict[str, tuple[int, int]],
        cfg,
        outlines: list[tuple[int, int, int, int]] | None = None,
        pin_points: set[tuple[int, int]] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Distance-threshold fill: add GND symbols for scattered pins.

        Every non-power GND pin farther than ``distance_threshold`` from
        the nearest GND symbol gets a new symbol placed near it (upward
        offset), so no area of the page is left without a local ground.

        Phase XVII P0-3: 与 ``_plan_and_inject_gnd_symbols`` 同样避让
        元件 outline 与引脚坐标。

        Args:
            remaining_pins: GND pins not owned by a chip group.
            existing_symbols: Already-planned GND symbols (chip + fill).
            used_pin/used_body: Occupied coordinates (avoid overlap).
            pin_coords: ``refdes.pin`` → absolute (x, y) (mutated).
            cfg: GndDistributionCfg.
            outlines: 元件 outline 矩形（避让，可选）。
            pin_points: 已占用引脚坐标（避让，可选）。

        Returns:
            ``(fill_symbols, fill_pins)`` — new symbol dicts and their
            pin entries to append to the page group.
        """
        threshold = int(getattr(cfg, "distance_threshold", 2000) or 2000)
        outlines = list(outlines or [])
        pin_points = set(pin_points or {})
        from . import gnd_cluster_planner

        avoid_margin = int(
            getattr(self._routing_cfg.overlap, "avoid_margin", 50) or 50
        )
        page_clearance = int(
            getattr(self._routing_cfg, "edge_clearance", 100) or 100
        )
        _pin_off = self._power_pin_offset("GND_POWER")
        fill_symbols: list[dict] = []
        fill_pins: list[dict] = []
        for p in remaining_pins:
            if p.get("is_power_symbol"):
                continue
            coord = tuple(p["coord"])
            near = any(
                self._dist(coord, s["pin_coord"]) <= threshold
                for s in existing_symbols + fill_symbols
            )
            if near:
                continue
            refdes = str(p.get("refdes", "")) or "X"
            sx, sy = gnd_cluster_planner.place_gnd_symbol(
                coord, outlines, margin=avoid_margin,
                pin_points=pin_points, pin_offset=_pin_off,
                edge_clearance=page_clearance,
            )
            used_body.add((sx, sy))
            sym_refdes = f"GND_P{refdes}"
            spx, spy = self._gnd_pin_coord(
                (sx + int(_pin_off[0]), sy + int(_pin_off[1])),
                used_pin, pin_points, margin=50,
            )
            used_pin.add((spx, spy))
            pin_points.add((spx, spy))
            fill_symbols.append({
                "refdes": sym_refdes, "x": sx, "y": sy,
                "net": "GND", "pin_coord": (spx, spy),
            })
            fill_pins.append({
                "refdes": sym_refdes, "pin": "1",
                "coord": (spx, spy), "is_power_symbol": True,
            })
            pin_coords[f"{sym_refdes}.1"] = (spx, spy)
        return fill_symbols, fill_pins

    @staticmethod
    def _gnd_pin_coord(
        cand: tuple[int, int],
        used_pin: set[tuple[int, int]],
        pin_points: set[tuple[int, int]] | None = None,
        margin: int = 50,
    ) -> tuple[int, int]:
        """Unique GND pin coordinate avoiding other pins by ``margin``.

        Phase XVII P0-3: GND 引脚不落在其他引脚坐标上（≥ ``margin`` 距离）。

        Args:
            cand: Candidate pin coordinate (on-grid).
            used_pin: Already-assigned GND pin coordinates.
            pin_points: All occupied pin coordinates (avoid).
            margin: Minimum distance to other pins.

        Returns:
            A unique on-grid coordinate (added to ``used_pin`` by caller).
        """
        nx, ny = int(cand[0]), int(cand[1])
        pin_points = set(pin_points or [])
        while (nx, ny) in used_pin or any(
            CSAWriter._dist((nx, ny), pp) < margin for pp in pin_points
        ):
            nx += 25
        return nx, ny

    @staticmethod
    def _gnd_rect_clear(
        x: int, y: int,
        outlines: list[tuple[int, int, int, int]],
        margin: int = 50,
    ) -> bool:
        """True when the GND body rect at (x, y) avoids every outline.

        GND_POWER body = ``-50,0,50,-50`` → abs rect
        ``(x-50, y-50, x+50, y)`` inflated by ``margin`` must not
        intersect any component outline.

        Phase XVIII R5：默认 margin 25→50（``overlap.avoid_margin``）。
        GND 符号放置主路径已改调 ``gnd_cluster_planner.place_gnd_symbol``；
        本函数保留为静态几何工具（调用方显式传 margin）。

        Args:
            x/y: GND symbol body center.
            outlines: 元件 outline 矩形（绝对坐标）。
            margin: 避让边距。

        Returns:
            True when no overlap.
        """
        x0, y0, x1, y1 = x - 50 - margin, y - 50 - margin, x + 50 + margin, y + margin
        for o in outlines:
            ox0, oy0, ox1, oy1 = o
            if (x0 < ox1 and x1 > ox0 and y0 < oy1 and y1 > oy0):
                return False
        return True

    @staticmethod
    def _dist(a: tuple[int, int], b: tuple[int, int]) -> float:
        """Euclidean distance between two points."""
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def _lastpins_for_instance(
        self,
        conn: "DesignConnectivity",
        page_conn,
        irec,
        pin_coords: dict[str, tuple[int, int]],
        source_pins: set[str],
        body_coord: "Optional[tuple[int, int]]" = None,
    ) -> list[str]:
        """Inline LASTPIN ($PN / SIG_NAME) lines for one instance.

        Emitted immediately after the instance's FORCEADD block so Cadence
        16.6 binds the pins to this component (Q1/SPCOCN-543 fix).

        Phase XVII P0-1 (SPCOCN-543 修复，方案 A-D):
        * 方案 B —— 坐标命中校验：LASTPIN 前校验引脚坐标是否命中
          symbol.css 引脚（``_pin_offset_resolves``）；未命中（fallback
          启发式坐标）不发射 LASTPIN（或标 NC），避免 Cadence 删除
          SPN/$PN/SIG_NAME。
        * 方案 C —— 旋转实例（rotation≠0 且非 mirror）的元件级 SIG_NAME
          改放 WIRE 上（``_sig_name_on_wire``），引脚只留 $PN；
          ``R 行 + 元件级 SIG_NAME LASTPIN`` 组合无 04p4 先例。
        * 方案 D —— 引脚数不匹配实例（实例引脚数 > symbol 引脚数）：
          跳过 LASTPIN 发射，由 M1 mock 图标（temp_lib）接管渲染。

        Phase XVIII R3 增补：
        * 有效视图同源（Q2）：sym_2 切换后 css_offsets 用 eff_section，
          方案 C 判定用 eff_rot_dehdl（sym_2 时 = 0 → SIG_NAME 回引脚，
          golden CAPACITOR..2 先例）；
        * 坐标命中强校验（``_lastpin_coord_hit``）：body + rotate_point
          (offset, eff_rot, mirror) 不一致 → skip + warning + 报告
          [LASTPIN_MISS]；
        * UN$ 网名策略（``_un_policy_display``，rename 稳定名/omit 省略）。

        Args:
            conn: DesignConnectivity。
            page_conn: PageConnectivity。
            irec: InstanceRecord。
            pin_coords: Pass 1 计算好的 ``refdes.pin → (x, y)``。
            source_pins: ``refdes.pin`` 集合（携带 SIG_NAME 的来源引脚）。
            body_coord: 实例体坐标 (x, y)（可选；用于坐标命中强校验）。

        Returns:
            CSA LASTPIN 行清单。
        """
        lines: list[str] = []
        body_name = irec.cell_name or self._cell_label(conn, irec.cell_id)
        section = irec.section
        placeholder = self._placeholder_for_irec(irec, body_name, section)
        rot = int(getattr(irec, "rotation", 0) or 0)
        mirror = int(getattr(irec, "mirror", 0) or 0)
        # R3: 有效视图（sym_2 切换后 section/旋转同源，坐标唯一原则）。
        eff_section, eff_rot_dehdl = self._effective_views.get(
            irec.refdes, (section, _dehdl_rotation(rot)),
        )
        normalize_mirror = bool(
            self._routing_cfg.mirror.normalize and mirror
        )

        def _emit_pin(pre, coord: tuple[int, int]) -> None:
            """单个引脚 LASTPIN 发射（$PN + 可选 SIG_NAME）。"""
            net_display = self._un_policy_display(
                self._net_display_for_pin(conn, page_conn, pre.net_id),
            )
            key = f"{irec.refdes}.{pre.pin_number}"
            if key in source_pins:
                if eff_rot_dehdl and not mirror:
                    # 方案 C: 旋转实例 SIG_NAME 改放 WIRE 上（sym_2 时
                    # eff_rot=0 → 回引脚，golden CAPACITOR..2 先例）。
                    lines.extend(self._lastpin_pn(coord, pre.pin_number))
                    if net_display:
                        lines.extend(self._sig_name_on_wire(coord, net_display))
                else:
                    if net_display:
                        lines.extend(self._sig_name_at_pin(coord, net_display))
                    else:
                        # omit 策略：UN$ 网名省略 SIG_NAME，只留 $PN。
                        lines.extend(self._lastpin_pn(coord, pre.pin_number))
            else:
                lines.extend(self._lastpin_pn(coord, pre.pin_number))

        if placeholder is None:
            # Concrete symbol: validate pin offsets against symbol.css
            # （视图同源：css_offsets 用 eff_section —— sym_2 切换后
            # 坐标唯一原则，禁止部分沿用 sym_1）。
            css_offsets = self._get_css_pin_offsets(body_name, eff_section)
            pinmap = self._get_pin_name_map(body_name)
            # 方案 D: instance pins > symbol pins → mismatch → skip ALL.
            if css_offsets and len(irec.pins) > len(css_offsets):
                logger.info(
                    "LASTPIN skip %s: %d pins vs symbol %d pins "
                    "(pin-count mismatch → M1 mock icon)",
                    irec.refdes, len(irec.pins), len(css_offsets),
                )
                return []
            for pre in irec.pins:
                key = f"{irec.refdes}.{pre.pin_number}"
                coord = pin_coords.get(key)
                if coord is None:
                    continue
                # 方案 B: fallback 启发式坐标未命中 css 引脚 → 不发射。
                if css_offsets and not self._pin_offset_resolves(
                    pre, css_offsets, pinmap,
                ):
                    logger.debug(
                        "LASTPIN skip %s.%s: offset not on symbol.css pin",
                        irec.refdes, pre.pin_number,
                    )
                    continue
                # R3d: 坐标数学校验（旋转分支一致性）—— 未命中 skip。
                # 被 _unique_pin_coord 微移的引脚跳过（坐标与 css 偏移
                # 严格不等是碰撞避免的合法结果）。
                if (css_offsets and body_coord is not None
                        and key not in self._nudged_pin_keys):
                    # Phase XXII D8: expected 用 _pin_offset_map 同源链
                    # （Pass 1 实际使用的 resolved offset，含 chips.prt
                    # 名桥/fallback）——不再简化 css 查找造成假 miss。
                    # 非微移引脚 coord == body + mapped 天然命中；个别
                    # 仍不命中（真实库符号 offset 非 25 网格等）→ 证据化
                    # 豁免（Q5 方案 b 兜底）。
                    mapped = self._pin_offset_map.get(key)
                    if mapped is not None:
                        expected = (
                            body_coord[0] + mapped[0],
                            body_coord[1] + mapped[1],
                        )
                        if tuple(coord) != expected:
                            logger.warning(
                                "LASTPIN miss %s.%s: coord %s vs "
                                "expected %s (same-source)",
                                irec.refdes, pre.pin_number, coord, expected,
                            )
                            if self._aesthetic_report is not None:
                                self._aesthetic_report.add_lastpin_miss(
                                    page=getattr(page_conn, "page_name", ""),
                                    refdes=irec.refdes, pin=pre.pin_number,
                                    coord=coord, expected=expected,
                                    exempt=True,
                                    reason="同源偏移仍不命中（证据化豁免）",
                                )
                            continue
                    else:
                        off = css_offsets.get(pre.pin_name) or css_offsets.get(
                            pre.pin_number,
                        )
                        if off is not None:
                            hit_rot = rot if normalize_mirror else eff_rot_dehdl
                            if not self._lastpin_coord_hit(
                                coord, body_coord, off, hit_rot, mirror,
                            ):
                                logger.warning(
                                    "LASTPIN miss %s.%s: coord %s vs "
                                    "body %s + rotate(%s,%s,%s)",
                                    irec.refdes, pre.pin_number, coord,
                                    body_coord, off, hit_rot, mirror,
                                )
                                if self._aesthetic_report is not None:
                                    self._aesthetic_report.add_lastpin_miss(
                                        page=getattr(page_conn, "page_name", ""),
                                        refdes=irec.refdes, pin=pre.pin_number,
                                        coord=coord, expected=(
                                            body_coord[0] + rotate_point(
                                                off[0], off[1], hit_rot, mirror,
                                            )[0],
                                            body_coord[1] + rotate_point(
                                                off[0], off[1], hit_rot, mirror,
                                            )[1],
                                        ),
                                    )
                                continue
                _emit_pin(pre, coord)
            return lines

        # Placeholder symbol: offsets are by construction on the generated
        # symbol.css pins — no hit validation needed (方案 D 由 M1 接管，
        # 此处 placeholder 自身引脚数匹配）。
        for pre in irec.pins:
            key = f"{irec.refdes}.{pre.pin_number}"
            coord = pin_coords.get(key)
            if coord is None:
                continue
            _emit_pin(pre, coord)
        return lines

    # ------------------------------------------------------------------
    #  CSA building blocks
    # ------------------------------------------------------------------

    @staticmethod
    def _cell_label(conn, cell_id: str) -> str:
        if not cell_id:
            return "unknown"
        for cell in conn.cells:
            if cell.cell_id == cell_id:
                return cell.cell_name
        return "unknown"

    def _emit_conn_instance_block(
        self, conn, irec, body_name: str, x: int, y: int,
        lastpin_lines: Optional[list[str]] = None,
        label_offsets: Optional[dict[str, tuple[int, int]]] = None,
        label_orient: Optional[dict[str, int]] = None,
        placeholder: object | None = None,
    ) -> list[str]:
        """Emit FORCEADD + standard properties for one model instance.

        Phase XIII Round 2 (QA): the block order follows 04p4 page15 —
        ``FORCEADD`` → optional ``R n`` rotation line → ``(x y);`` →
        LASTPIN pins → VALUE → PATH → outline → CDS_LIB → PART_NAME →
        LOCATION → section props.  The rotation line MUST come BEFORE the
        body coordinate (04p4 INPORT ``R 2`` evidence) or Cadence ignores
        it and renders the component un-rotated while LASTPIN coordinates
        are rotated (Q2 "差一点").

        Phase XIV D1: ``label_offsets``（text_layout 解算结果）只影响
        VALUE / $LOCATION 标签坐标 —— LASTPIN/WIRE 坐标绝对不动。

        Phase XV P0-F: ``placeholder``（PlaceholderSymbol 或 None）——
        非 None 时 body_name 已是占位 cell，outline 取占位符号矩形，
        并追加 ``PLACEHOLDER 1`` 属性标注"这是占位符号"。

        Args:
            conn: Design connectivity model.
            irec: Instance record.
            body_name: HDL cell name.
            x/y: Absolute body coordinate.
            lastpin_lines: This instance's inline LASTPIN ($PN / SIG_NAME)
                lines, emitted right after the placement coordinate
                (04p4 AT88SC0104C evidence — pins before VALUE).
            label_offsets: text key → (dx, dy) 标签偏移表（可选）。
            label_orient: text key → dehdl 旋转角（Phase XXII D7，可选）。
                仅 ``text_layout.enabled`` 时由调用方传入；VALUE/$LOCATION
                属性块按该角输出 R 行（0 不输出）。disabled 时保持现状。
            placeholder: PlaceholderSymbol 实例（可选，P0-F）。
        """
        # Phase XI P0-遗留#2: power symbols use the dedicated FORCEADD block
        # (04p4 page9.csa L219-250) — LASTPIN SIG_NAME + HDL_POWER + SIZE +
        # outline + CDS_LIB + BODY_TYPE PLUMBING + PATH; no VALUE/LOCATION.
        if irec.is_power_symbol:
            return self._emit_power_symbol_block(conn, irec, body_name, x, y)

        from .coord_transform import rotate_point
        offsets = label_offsets or {}
        lines: list[str] = []
        a = lines.append
        section = irec.section
        refdes = irec.refdes
        props = irec.properties or {}
        value = irec.value or self._resolve_prop(props, "VALUE") or refdes

        # Phase XVIII R3 (Q2 方案 A): 有效视图（sym_2 切换）——
        # FORCEADD 用 eff_section（``CAPACITOR..2``），R 行用 eff_rot
        # （sym_2 时 = 0 → 不写 R 行，golden page9 L354 先例）。
        _eff = self._effective_views.get(
            irec.refdes,
            self._effective_view(irec, body_name, section)[:2],
        )
        _eff_section, _eff_rot = _eff
        a(f"FORCEADD {body_name.upper()}..{_eff_section}")

        # Phase XIII T1/T2: emit the DEHDL rotation line BEFORE the body
        # coordinate so Cadence renders the component rotated (04p4
        # page15 INPORT `R 2` sits between FORCEADD and the coordinate).
        # rotation 90/180/270 → R 1/2/3 (DEHDL convention); 0 → no line.
        # mirror is deliberately NOT emitted (conservative policy, T2):
        # no MY/MX line is written — Phase XVI T1 用等效 R 行近似渲染方向
        # （Pass 1 的 closest_rotation_for_mirror 结果）。
        _rot = int(getattr(irec, "rotation", 0) or 0)
        _mirror = int(getattr(irec, "mirror", 0) or 0)
        # Phase XV P0-E: EDIF rotation → DEHDL R-line convention (90↔270
        # swap fixes the L20/L14 180°-flip confirmed in Cadence 16.6).
        # Phase XVI T1: mirror 实例的 R 行从 Pass 1 计算的 _mirror_rline 读取。
        if self._routing_cfg.mirror.normalize and _mirror:
            _rot_dehdl = self._mirror_rline.get(
                irec.refdes, _dehdl_rotation(_rot),
            )
        else:
            _rot_dehdl = _eff_rot
        if _rot_dehdl == 90:
            a("R 1")
        elif _rot_dehdl == 180:
            a("R 2")
        elif _rot_dehdl == 270:
            a("R 3")

        a(f"({x} {y});")

        # Phase XV P0-F: 占位符号标注（用户要求"明确标注是占位符号"）。
        # Phase XVII P0-2 (SPCOCN-542 修复): PLACEHOLDER 是 symbol.css
        # 已声明的 P 属性（placeholder_lib._symbol_css 补 P 声明），块格式
        # 按 04p4 黄金属性块（FORCEPROP + R 1 + J 1 + DISPLAY）——
        # 去掉 PAINT ORANGE + DISPLAY INVISIBLE（该组合让 Cadence 当
        # "默认属性"删除 SPCOCN-542 并提示 SPCOCN-545）。
        # Phase XVII M1: mock 模拟图标不发射 PLACEHOLDER（MOCK_TEXT 标注
        # 已在 symbol.css 内画好）。
        if placeholder is not None and getattr(
            placeholder, "kind", "placeholder"
        ) == "placeholder":
            a("FORCEPROP 1 LAST PLACEHOLDER 1")
            a("R 1")
            a("J 1")
            a(f"({x} {y});")
            a(f"DISPLAY {_SCALE_VALUE} ({x} {y});")

        # Phase XIII T2: inline LASTPIN right after placement (04p4
        # AT88SC0104C: $PN pins before VALUE).  Binding is to the most
        # recent FORCEADD — this component — so the pins cannot be stolen
        # by a later IOPORT block (Q1/SPCOCN-543/541).
        if lastpin_lines:
            lines.extend(lastpin_lines)

        # Phase XXI B（用户 P5"MOCK 标识做成标签方式比较大个、可改颜色"）：
        # mock 模拟图标除 symbol.css 内 T 指令文本（字号 59→89）外，再注入
        # **实例属性标签** ``FORCEPROP 1 LAST MOCK_TEXT MOCK`` + J 1 +
        # 元件上方坐标 + DISPLAY 1.5（≥1.5 放大）+ **PAINT PINK**（04p4
        # 已有 PINK 40 次先例，最接近红色）。MOCK_TEXT 已在 mock symbol.css
        # P 声明（Phase XXI A），FORCEPROP 注入不会触发 SPCOCN-542/545。
        # 坐标 = body + rotate(0, outline顶部+60)：标签在图标上方、不与
        # $LOCATION/VALUE 冲突（含旋转）。
        if (placeholder is not None
                and getattr(placeholder, "kind", "placeholder") == "mock"
                and self._mock_lib is not None
                and self._mock_lib.annotate):
            lines.extend(self._mock_text_label_lines(
                placeholder, x, y, _rot_dehdl,
            ))

        # VALUE (Phase XIV D1: 应用 text_layout 偏移)
        # Phase XVII P0-4 (问题 #10/#13): 标签偏移随旋转 —— 基准偏移
        # (-5,-50) 应用 rotate_point（与引脚同源），DEHDL R 行同步。
        # Phase XXII D7: text_layout.enabled 时 VALUE 标签方向随元件 R 行
        # （label_orient；0 = 不输出 R 行）；disabled 保持现状 `R 1`。
        _v_off = offsets.get(f"{refdes}.VALUE", (0, 0))
        _vbase = rotate_point(-5, -50, _rot_dehdl)
        vx, vy = x + _vbase[0] + _v_off[0], y + _vbase[1] + _v_off[1]
        a(f"FORCEPROP 1 LAST VALUE {value}")
        if not self._routing_cfg.text_layout.enabled:
            a("R 1")
        else:
            _v_orient = int((label_orient or {}).get(f"{refdes}.VALUE", 0) or 0)
            if _v_orient:
                a(f"R {_LABEL_R_LINE.get(_v_orient, 1)}")
            # orient == 0 → 不输出 R 行（0 碰撞不劣化）
        a("J 1")
        a(f"({vx} {vy});")
        a(f"DISPLAY {_SCALE_VALUE} ({vx} {vy});")
        a(f"PAINT {_PAINT_ORANGE} ({vx} {vy});")

        # PATH (invisible)
        a(f"FORCEPROP 1 LAST PATH I{irec.page_local_k}")
        a("J 0")
        a(f"({x} {y});")
        a(f"DISPLAY {_SCALE_TRANSITION} ({x} {y});")
        a(f"PAINT {_PAINT_ORANGE} ({x} {y});")
        a(f"DISPLAY INVISIBLE ({x} {y});")

        # CDS_LMAN_SYM_OUTLINE
        # Phase XIII T3: unmatched multi-pin ICs (no symbol.css pin
        # offsets) get a placeholder rectangle sized from the pin-count
        # perimeter layout, so Cadence renders a body instead of relying
        # on a mismatched fallback symbol.
        outline = self._resolve_prop(props, "CDS_LMAN_SYM_OUTLINE")
        # Phase XV P0-F: placeholder symbols use their own outline so the
        # rendered body encloses every generated pin.
        if placeholder is not None:
            outline = placeholder.outline
        if not outline and len(irec.pins) > 1 and not self._get_css_pin_offsets(
            body_name, section
        ):
            outline = self._placeholder_outline(len(irec.pins))
        if not outline:
            outline = "-50,0,50,-25"
        a(f"FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE {outline}")
        a("J 0")
        a(f"({x} {y});")
        a(f"DISPLAY {_SCALE_OUTLINE} ({x} {y});")
        a(f"PAINT {_PAINT_GREEN} ({x} {y});")
        a(f"DISPLAY INVISIBLE ({x} {y});")

        # CDS_LIB
        # Phase XVII M1 (QA P1-2 修复): mock 模拟图标的 cell 写在独立
        # output/temp_lib/（不污染 hdl_lib），其 CSA 块 CDS_LIB 必须指向
        # temp_lib —— 否则 Cadence 在 hdl_lib 找不到 U6_PH.SYM.1.1 →
        # SPCOCN-515 库缺失（M1 端到端断裂）。cds.lib 侧由
        # OutputManager 补 ``DEFINE temp_lib ./temp_lib``。
        _cds_lib = self._hdl_lib_name
        if (placeholder is not None
                and getattr(placeholder, "kind", "placeholder") == "mock"
                and self._mock_lib is not None):
            _cds_lib = self._mock_lib.lib_name or self._hdl_lib_name
        a(f"FORCEPROP 2 LAST CDS_LIB {_cds_lib}")
        a("J 0")
        a(f"({x} {y});")
        a(f"PAINT {_PAINT_ORANGE} ({x} {y});")
        a(f"DISPLAY INVISIBLE ({x} {y});")

        # PART_NAME
        part_name = self._resolve_prop(props, "PART_NAME") or body_name.upper()
        a(f"FORCEPROP 1 LAST PART_NAME {part_name}")
        a("J 0")
        a(f"({x} {y});")
        a(f"DISPLAY {_SCALE_TRANSITION} ({x} {y});")
        a(f"PAINT {_PAINT_ORANGE} ({x} {y});")
        a(f"DISPLAY INVISIBLE ({x} {y});")

        # DESCRIPTION / PACKAGE_TYPE / SN_NUM / JEDEC_TYPE (optional)
        # Phase XVIII R4: 数据源改为 CrossRef CSV（refdes → CrossRefEntry，
        # 优先）+ irec.properties（回退）；缺失字段跳过，禁止 "?" 注入。
        lines.extend(self._inject_crossref_props(irec, props, x, y))

        # LOCATION / $LOCATION — $LOCATION is the standard DEHDL attribute
        # name for single- and multi-section parts alike (P1-3; reference
        # engineering 8367/04p4: CAPACITOR $LOCATION×46 vs LOCATION×0).
        # Phase XIV D1: 应用 text_layout 偏移。
        # Phase XVII P0-4 (问题 #10/#13): $LOCATION 基准偏移 (-5,+220)
        # 应用 rotate_point（与引脚同源），DEHDL R 行同步。
        # Phase XXII D7: $LOCATION 标签方向随元件 R 行（同 VALUE）。
        _l_off = offsets.get(f"{refdes}.LOCATION", (0, 0))
        _lbase = rotate_point(-5, 220, _rot_dehdl)
        loc_x, loc_y = x + _lbase[0] + _l_off[0], y + _lbase[1] + _l_off[1]
        a(f"FORCEPROP 1 LAST $LOCATION {refdes}")
        if not self._routing_cfg.text_layout.enabled:
            a("R 1")
        else:
            _l_orient = int((label_orient or {}).get(f"{refdes}.LOCATION", 0) or 0)
            if _l_orient:
                a(f"R {_LABEL_R_LINE.get(_l_orient, 1)}")
            # orient == 0 → 不输出 R 行
        a("J 1")
        a(f"({loc_x} {loc_y});")
        a(f"DISPLAY {_SCALE_VALUE} ({loc_x} {loc_y});")
        a(f"PAINT {_PAINT_GREEN} ({loc_x} {loc_y});")

        # CDS_LOCATION
        a(f"FORCEPROP 2 LAST CDS_LOCATION {refdes}")
        a("J 0")
        a(f"({loc_x} {loc_y + 55});")
        a(f"DISPLAY {_SCALE_TRANSITION} ({loc_x} {loc_y + 55});")
        a(f"PAINT {_PAINT_ORANGE} ({loc_x} {loc_y + 55});")
        a(f"DISPLAY INVISIBLE ({loc_x} {loc_y + 55});")

        # $SEC / CDS_SEC
        a(f"FORCEPROP 2 LAST $SEC {section}")
        a("J 0")
        a(f"({loc_x} {loc_y + 55});")
        a(f"DISPLAY {_SCALE_SEC} ({loc_x} {loc_y + 55});")
        a(f"PAINT {_PAINT_MONO} ({loc_x} {loc_y + 55});")
        a(f"DISPLAY INVISIBLE ({loc_x} {loc_y + 55});")
        a(f"FORCEPROP 2 LAST CDS_SEC {section}")
        a("J 0")
        a(f"({loc_x} {loc_y + 55});")
        a(f"DISPLAY {_SCALE_TRANSITION} ({loc_x} {loc_y + 55});")
        a(f"PAINT {_PAINT_ORANGE} ({loc_x} {loc_y + 55});")
        a(f"DISPLAY INVISIBLE ({loc_x} {loc_y + 55});")

        return lines

    def _mock_text_label_lines(
        self,
        placeholder: object,
        x: int,
        y: int,
        rot_dehdl: int,
    ) -> list[str]:
        """Emit the MOCK_TEXT visible attribute label for a mock component.

        Phase XXI B（用户 P5）：Cadence 16.6 实测 mock T 指令文本仍绿且
        小（c11=4 颜色字段不可靠）→ 用户建议"做成标签的方式比较大个
        显示、可改颜色"。标签 = CSA 实例属性（``FORCEPROP 1 LAST
        MOCK_TEXT MOCK``），格式对齐 04p4 黄金属性块（HDL_POWER/SIZE
        先例：FORCEPROP + J 1 + 坐标 + DISPLAY + PAINT）；颜色用
        **PINK**（04p4 全库 40 次先例，Cadence 渲染为红粉系）；DISPLAY
        1.5（≥1.5 放大，远大于 VALUE 0.85）。

        坐标 = body + rotate(0, outline顶部+60)：标签画在图标上方，不与
        $LOCATION（body+220 附近）冲突；含旋转（R 行同步）。

        Args:
            placeholder: MockSymbol（kind == "mock"）。
            x/y: Absolute body coordinate.
            rot_dehdl: Effective DEHDL rotation angle (0/90/180/270).

        Returns:
            CSA label lines（FORCEPROP…PAINT PINK）。
        """
        from .coord_transform import rotate_point

        outline = str(getattr(placeholder, "outline", "") or "")
        top_edge = 200
        try:
            _o = [float(v) for v in outline.split(",")]
            if len(_o) >= 4:
                top_edge = int(max(_o[1], _o[3]))
        except (TypeError, ValueError):
            top_edge = 200
        _mbase = rotate_point(0, top_edge + 60, int(rot_dehdl or 0))
        mx, my = x + _mbase[0], y + _mbase[1]
        lines: list[str] = []
        a = lines.append
        a("FORCEPROP 1 LAST MOCK_TEXT MOCK")
        a("J 1")
        a(f"({mx} {my});")
        a(f"DISPLAY {_SCALE_MOCK_TEXT} ({mx} {my});")
        a(f"PAINT {_PAINT_PINK} ({mx} {my});")
        return lines

    def _emit_power_symbol_block(
        self, conn, irec, body_name: str, x: int, y: int,
    ) -> list[str]:
        """Emit a power symbol FORCEADD block (04p4/8367 evidence).

        Matches the real DEHDL power-symbol macro::

            FORCEADD VCC_CIRCLE..1
            (-2125 9750);
            FORCEPROP 3 LASTPIN (-2125 9700) SIG_NAME DC12V\\g
            J 0
            (-2115 9710);
            DISPLAY 0.659574 (-2115 9710);
            PAINT MONO (-2115 9710);
            DISPLAY INVISIBLE (-2115 9710);
            FORCEPROP 1 LAST HDL_POWER DC12V
            ...
            FORCEPROP 1 LAST PATH I101

        Phase XVII P0-1 复盘（QA P1-1）：``PAINT MONO + DISPLAY INVISIBLE``
        是 04p4 golden page9.csa 中 SIG_NAME LASTPIN 块的标准写法（见
        L12 GND_POWER / L365 CAPACITOR SIG_NAME）—— 电源符号**无需豁免**，
        ``_sig_name_at_pin`` 已恢复同一格式（完全对齐 golden）。SPCOCN-543
        真实根因为坐标未命中（方案 B/C/D 处理），与 PAINT 无关。

        The LASTPIN coordinate = FORCEADD coordinate + symbol.css pin offset
        (GND (0,+50), VCC_CIRCLE (0,-50)); property label positions come
        from symbol.css when available (hdl_lib_path), otherwise template
        defaults.  Exactly one SIG_NAME per net is guaranteed because the
        later LASTPIN pass skips power symbols.

        Phase XVIII R3c（golden page9 L10-17 对齐）：
        * GND_POWER LASTPIN offset = ``gnd_distribution.gnd_power_lastpin_offset``
          （默认 ``[50, 100]``；值 ``"css"`` 回退 symbol.css 引脚 (0,50)）；
          mirror≠0 仍经 ``rotate_point(offset, 0, mirror)``。
        * SIG_NAME 值 = ``_gnd_power_sig_name`` → ``GND_POWER\\g``
          （symbol.css ``P "HDL_POWER"`` 值），不再用 page 网名 ``GND\\g``。
        """
        lines: list[str] = []
        a = lines.append

        net = (irec.power_nets[0] if irec.power_nets else "GND").rstrip("\\g")
        body_lower = (body_name or "").lower()
        is_vcc = body_lower == "vcc_circle"
        is_gnd = body_lower in ("gnd_power", "gnd")
        outline = "-75,75,75,-75" if is_vcc else "-50,0,50,-50"
        # symbol.css C-command pin offset: GND (0,+50), VCC (0,-50).
        # Phase XVI T1 (A.5 末): 电源符号 mirror≠0 时引脚偏移仅镜像——
        # Pass 1 的 pin_coords/net_pin_map（WIRE 源）已镜像；此处必须与
        # 之一致，否则 LASTPIN（未镜像）与 WIRE 端点（镜像）不重合 → 断线。
        # Phase XVIII R3c: GND_POWER 偏移 = golden (50,100)（_power_pin_offset
        # 与 Pass 1 同源，坐标唯一原则）。
        from .coord_transform import rotate_point
        _pmirror = int(getattr(irec, "mirror", 0) or 0)
        _off = self._power_pin_offset(body_name)
        # SPCOCN-543：plumbing 电源符号忽略 mirror（见 Pass1 同源注释）。
        if _pmirror and not self._is_plumbing_power(body_name):
            _off = rotate_point(_off[0], _off[1], 0, _pmirror)
        px, py = x + _off[0], y + _off[1]

        # property label offsets from symbol.css (fallback to template)
        prop_offsets = self._get_prop_offsets(body_name)

        def _pos(key: str, dx: int, dy: int) -> tuple[int, int]:
            off = prop_offsets.get(key)
            if off:
                return (x + int(off[0]), y + int(off[1]))
            return (x + dx, y + dy)

        hx, hy = _pos("HDL_POWER", 0, 54)
        sx, sy = _pos("SIZE", -147, 0)
        ox, oy = _pos("CDS_LMAN_SYM_OUTLINE", 0, 0)
        bx, by = _pos("BODY_TYPE", 0, -100)
        tx, ty = _pos("PATH", 0, 0)

        a(f"FORCEADD {body_name.upper()}..1")
        a(f"({x} {y});")
        # LASTPIN SIG_NAME (pin offset from symbol.css / R3c golden 偏移)
        # R3c: SIG_NAME 值 = _gnd_power_sig_name（GND_POWER\g，golden 对齐）。
        _sig = self._gnd_power_sig_name(body_name, net)
        a(f"FORCEPROP 3 LASTPIN ({px} {py}) SIG_NAME {_sig}")
        a("J 0")
        a(f"({px + 10} {py + 10});")
        a(f"DISPLAY {_SCALE_SIG_NAME} ({px + 10} {py + 10});")
        a(f"PAINT {_PAINT_MONO} ({px + 10} {py + 10});")
        a(f"DISPLAY INVISIBLE ({px + 10} {py + 10});")
        # HDL_POWER (power net name, no \g)
        a(f"FORCEPROP 1 LAST HDL_POWER {net}")
        a("J 1")
        a(f"({hx} {hy});")
        a(f"DISPLAY {_SCALE_VALUE} ({hx} {hy});")
        a(f"PAINT {_PAINT_GREEN} ({hx} {hy});")
        if is_vcc:
            # SIZE only on VCC_CIRCLE (symbol.css "1B")
            a("FORCEPROP 1 LAST SIZE 1B")
            a("J 1")
            a(f"({sx} {sy});")
            a(f"DISPLAY {_SCALE_VALUE} ({sx} {sy});")
            a(f"PAINT {_PAINT_GREEN} ({sx} {sy});")
            a(f"DISPLAY INVISIBLE ({sx} {sy});")
        a(f"FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE {outline}")
        a("J 0")
        a(f"({ox} {oy});")
        a(f"DISPLAY {_SCALE_OUTLINE} ({ox} {oy});")
        a(f"PAINT {_PAINT_GREEN} ({ox} {oy});")
        a(f"DISPLAY INVISIBLE ({ox} {oy});")
        a(f"FORCEPROP 2 LAST CDS_LIB {self._hdl_lib_name}")
        a("J 0")
        a(f"({x} {y});")
        a(f"DISPLAY INVISIBLE ({x} {y});")
        a("FORCEPROP 1 LAST BODY_TYPE PLUMBING")
        a("J 0")
        a(f"({bx} {by});")
        a(f"DISPLAY {_SCALE_VALUE} ({bx} {by});")
        a(f"PAINT {_PAINT_GREEN} ({bx} {by});")
        a(f"DISPLAY INVISIBLE ({bx} {by});")
        a(f"FORCEPROP 1 LAST PATH I{irec.page_local_k}")
        a("J 0")
        a(f"({tx} {ty});")
        a(f"DISPLAY {_SCALE_TRANSITION} ({tx} {ty});")
        a(f"PAINT {_PAINT_ORANGE} ({tx} {ty});")
        a(f"DISPLAY INVISIBLE ({tx} {ty});")
        return lines

    @staticmethod
    def _unique_pin_coord(
        coord: tuple[int, int],
        used: set[tuple[int, int]],
    ) -> tuple[int, int]:
        """Return ``coord`` if free, else the next free 25-grid position.

        Phase XIII Round 2 (QA short-circuit): two DIFFERENT nets must not
        share an absolute pin coordinate — fallback columns of nearby
        bodies can collide, and a shared coordinate makes both nets' wires
        meet at the same point → DEHDL short.  The nudge walks +25 in x
        (remaining on the 25 grid) until the coordinate is unused.

        Args:
            coord: Candidate absolute pin coordinate (must be on-grid).
            used: Set of already-assigned absolute pin coordinates.

        Returns:
            A unique on-grid coordinate (added to ``used`` by the caller).
        """
        nx, ny = coord
        while (nx, ny) in used:
            nx += 25
        return (nx, ny)

    @staticmethod
    def _snap50(value: float) -> int:
        """Snap a coordinate to the 50-unit grid (mock pin/body 位移栅格)。

        Phase XXII D8/Q5：OverlapResolver 位移应用后 body 坐标 snap 50
        （50 也是 25 网格；WIRE 端点仍满足 25 网格约束）。
        """
        return int(round(float(value) / 50.0) * 50)

    @staticmethod
    def _ioport_position(index: int) -> tuple[int, int]:
        """Place an IOPORT symbol near the page's top-right edge.

        Phase XI P0-C5 layout: right-edge column (100-unit pitch, 8 per
        row) then a second row 300 below.  Coordinates are on the 25-unit
        grid (-600, 7300, 100, 300 are all multiples of 25).
        """
        x = -600 - (index % 8) * 100
        y = 7300 - (index // 8) * 300
        return x, y

    def _build_ioport_cluster_order(
        self, page_conn, net_pin_map: dict[str, list],
    ) -> None:
        """Phase XXII D5: edge_layout 开启时按"同网页内引脚 y 均值"重排
        IOPORT 槽位（确定性、无重叠）。

        对每个 effective IOPORT，求其网在本页的非 IOPORT 引脚 y 均值
        （排除 ``IOPORT_`` 自身引脚），按 y 降序（顶→下）分配槽位
        ordinal；同锚点按 off_page 原始顺序决胜（确定性）。结果存
        ``self._ioport_cluster_order: dict[int, int]``（effective_idx →
        ordinal），``_ioport_position_cfg`` 读取 —— Pass 1 入网 / Pass 2
        发射 / text_layout ioport_positions 全部经该函数同源一致。

        Args:
            page_conn: PageConnectivity。
            net_pin_map: 页网显示名 → 引脚列表（实例引脚已注入）。
        """
        self._ioport_cluster_order = {}
        if not self._routing_cfg.ioport.edge_layout:
            return
        anchors: list[tuple[int, int, float]] = []  # (idx, order, anchor_y)
        for idx, op in self._page_ioports(page_conn):
            net_name = str(op.get("net_name", "") or op.get("name", ""))
            net_display = self._power_net_display(page_conn, net_name)
            pins = net_pin_map.get(net_display, []) or []
            real = [
                p for p in pins
                if not str(p.get("refdes", "")).startswith("IOPORT_")
            ]
            if real:
                anchor_y = sum(
                    int(p["coord"][1]) for p in real
                ) / len(real)
            else:
                # 无实例引脚 → 保持原等距公式顺序（原 index 决胜）。
                anchor_y = (7200 - self._routing_cfg.ioport.edge_margin) \
                    - idx * self._routing_cfg.ioport.edge_step
            anchors.append((idx, idx, anchor_y))
        # 确定性排序：y 降序（顶→下）；同锚点按原 index 升序。
        anchors.sort(key=lambda t: (-t[2], t[1]))
        for ordinal, (_idx, _order, _y) in enumerate(anchors):
            self._ioport_cluster_order[_idx] = ordinal

    def _ioport_position_cfg(self, index: int) -> tuple[int, int]:
        """IOPORT 位置（Phase XIV T8 / Phase XV P1-C 跨页网视觉优化）。

        优先级（Phase XV P1-C，用户决策 2）：
        1. ``ioport.edge_layout`` 开启：跨页口沿页面右缘**等间距分布对齐**
           （x 固定右侧缘，y 从页顶边距向下每 ``edge_step`` 递减）——
           替代默认的右上角 8 个一行/300 换行布局，消除重叠；
        2. ``cross_page_opt``（Phase XIV 旧开关）：右侧缘 x 统一、y 每
           端口 100 等间距；
        3. 默认：右上角 8 个一行。

        WIRE 端点由 ``_ioport_pin_coord`` 同源计算 → 连接保持。

        Args:
            index: IOPORT 序号。

        Returns:
            (x, y) 在 C-paper 坐标空间。
        """
        if self._routing_cfg.ioport.edge_layout:
            i_cfg = self._routing_cfg.ioport
            # C 纸可用区域顶边 ~7200；从顶边向下等间距排布。
            # Phase XXII D5: 聚类槽位（按同网页内引脚 y 均值降序）——
            # ``_ioport_cluster_order`` 含 index 时用 ordinal 定位。
            ordinal = self._ioport_cluster_order.get(index)
            if ordinal is not None:
                y = (7200 - i_cfg.edge_margin) - ordinal * i_cfg.edge_step
            else:
                y = (7200 - i_cfg.edge_margin) - index * i_cfg.edge_step
            return (i_cfg.edge_x, y)
        if self._routing_cfg.cross_page_opt:
            return (-600, 7300 - index * 100)
        return self._ioport_position(index)

    def _ioport_pin_coord(self, index: int) -> tuple[int, int]:
        """Absolute pin-A coordinate of an IOPORT symbol.

        ``body + symbol.css C -50 0 "A"`` — the same coordinate used by
        the block's LASTPIN, so a WIRE routed to this pin lands exactly
        on the rendered port (04p4 evidence: WIRE reaches (-3950 -1400)
        = body (-3900 -1400) + (-50, 0)).
        """
        x, y = self._ioport_position_cfg(index)
        off = self._get_css_pin_offsets("IOPORT", 1).get("A", (-50, 0))
        return (x + off[0], y + off[1])

    def _page_ioports(self, page_conn):
        """Yield ``(effective_idx, op)`` for IOPORTs to emit.

        Phase XVI T2: 空名 off_page 与孤立 connector（``skip_orphan``）
        均跳过；effective idx 保证 Pass 1 入网与 Pass 2 发射使用相同
        序号（``IOPORT_{idx}`` refdes 与 ``_ioport_pin_coord(idx)`` 一致）。

        Args:
            page_conn: PageConnectivity。

        Yields:
            ``(effective_idx, off_page_dict)``。
        """
        eff = 0
        for op in getattr(page_conn, "off_pages", []) or []:
            op_name = str(op.get("name", "") or "")
            if not op_name:
                continue
            net_name = str(op.get("net_name", "") or op_name)
            if net_name in self._orphan_ioport_names:
                continue
            yield eff, op
            eff += 1

    def _emit_ioport_block(
        self,
        conn,
        page_conn,
        off_page: dict,
        index: int,
        label_offsets: Optional[dict[str, tuple[int, int]]] = None,
    ) -> list[str]:
        """Emit a cross-page IOPORT symbol block (Phase XI P0-C5).

        Phase XIII T2: template aligned to 04p4 page15.csa L228-254 —
        ``FORCEPROP 1 LASTPIN`` (level 1, not level 3), pin coordinate
        ``body + (-50, 0)`` (css ``C -50 0 "A"``), HDL_PORT label at
        ``body + (325, -125)``, uniform DISPLAY 0.872340, PATH/VHDL_PORT
        PAINT PINK (HDL_PORT unpainted), no CDS_LMAN_SYM_OUTLINE, CDS_LIB
        at the body with its own DISPLAY INVISIBLE.

        Phase XIV D1: ``label_offsets`` 只影响 HDL_PORT 标签显示坐标
        （不碰 ``(px py)`` LASTPIN 引脚坐标 —— 电气连接不变）。
        """
        lines: list[str] = []
        a = lines.append

        x, y = self._ioport_position_cfg(index)
        off_page_name = str(off_page.get("name", "") or f"OFFPAGE_{index}")
        net_name = str(off_page.get("net_name", "") or off_page_name)

        body = "IOPORT"
        # Pin A offset from css C command (04p4: -50 0); fallback (-50, 0).
        css_offsets = self._get_css_pin_offsets(body, 1)
        _pin_off = css_offsets.get("A", (-50, 0))
        px, py = x + _pin_off[0], y + _pin_off[1]
        # Label offsets: HDL_PORT/VHDL_PORT are X commands (not P), so
        # they come from _get_x_label_offsets with 04p4 fallbacks.
        # Phase XIV D1: PORT 标签偏移（只动标签坐标，不碰 LASTPIN 引脚坐标）。
        _port_off = (label_offsets or {}).get(f"PORT.{off_page_name}.HDL_PORT", (0, 0))
        x_offsets = self._get_x_label_offsets(body, 1)
        _hdl = x_offsets.get("HDL_PORT", (325, -125))
        hx, hy = x + _hdl[0] + _port_off[0], y + _hdl[1] + _port_off[1]
        _vhdl = x_offsets.get("VHDL_PORT", (-35, -70))
        vx, vy = x + _vhdl[0], y + _vhdl[1]
        # PATH (css P "PATH" 0 50) / OFFPAGE (css P "OFFPAGE" 25 100).
        tx, ty = x, y + 50
        ox, oy = x + 25, y + 100

        a(f"FORCEADD {body}..1")
        a(f"({x} {y});")
        a(f"FORCEPROP 1 LAST PATH I{2000 + index}")
        a("J 0")
        a(f"({tx} {ty});")
        a(f"DISPLAY {_SCALE_IOPORT} ({tx} {ty});")
        a(f"PAINT {_PAINT_PINK} ({tx} {ty});")
        a(f"DISPLAY INVISIBLE ({tx} {ty});")
        a("FORCEPROP 1 LAST OFFPAGE TRUE")
        a("J 0")
        a(f"({ox} {oy});")
        a(f"DISPLAY INVISIBLE ({ox} {oy});")
        # HDL_PORT LASTPIN (level 1, no PAINT — 04p4 evidence)
        a(f"FORCEPROP 1 LASTPIN ({px} {py}) HDL_PORT INOUT")
        a("J 0")
        a(f"({hx} {hy});")
        a(f"DISPLAY {_SCALE_IOPORT} ({hx} {hy});")
        a(f"DISPLAY INVISIBLE ({hx} {hy});")
        # VHDL_PORT LASTPIN (level 1, PAINT PINK)
        a(f"FORCEPROP 1 LASTPIN ({px} {py}) VHDL_PORT INOUT")
        a("J 0")
        a(f"({vx} {vy});")
        a(f"DISPLAY {_SCALE_IOPORT} ({vx} {vy});")
        a(f"PAINT {_PAINT_PINK} ({vx} {vy});")
        a(f"DISPLAY INVISIBLE ({vx} {vy});")
        a(f"FORCEPROP 2 LAST CDS_LIB {self._hdl_lib_name}")
        a("J 0")
        a(f"({x} {y});")
        a(f"DISPLAY INVISIBLE ({x} {y});")
        return lines

    @staticmethod
    def _csa_page_frame_block(page_name: str) -> list[str]:
        """Emit the C SIZE PAGE frame FORCEADD block."""
        lines = [
            "FORCEADD C SIZE PAGE..1",
            "(-250 0);",
            "FORCEPROP 1 LAST COMMENT_BODY TRUE",
            "J 0",
            "(1750 225);",
            "DISPLAY 0.872340 (1750 225);",
            "PAINT GREEN (1750 225);",
            "DISPLAY INVISIBLE (1750 225);",
            "FORCEPROP 1 LAST CDS_LMAN_SYM_OUTLINE -10750,8275,0,0",
            "J 0",
            "(-250 0);",
            "DISPLAY 0.468085 (-250 0);",
            "PAINT GREEN (-250 0);",
            "DISPLAY INVISIBLE (-250 0);",
            "FORCEPROP 2 LAST CDS_LIB hdl_lib",
            "J 0",
            "(-250 0);",
            "DISPLAY INVISIBLE (-250 0);",
            f"FORCEPROP 0 LAST EDIT PAGE NAME {page_name}",
            "J 0",
            "(-250 0);",
            "DISPLAY INVISIBLE (-250 0);",
        ]
        return lines

    @staticmethod
    def _lastpin_pn(coord: tuple[int, int], pin_number: str) -> list[str]:
        """Emit a LASTPIN $PN label — 04p4-aligned format (Phase XV P0-A).

        Cadence 16.6 deletes the ``$PN``/``SPN``/``SIG_NAME`` pin properties
        (SPCOCN-543) when the LASTPIN attribute block contains a ``PAINT``
        line or uses ``J 2``.  The reference engineering 04p4 page9
        (CAPACITOR ``$PN 2`` block) uses exactly::

            FORCEPROP 2 LASTPIN (x y) $PN <n>
            R 1
            J 0
            (x-10 y+10);
            DISPLAY 0.808511 (x-10 y+10);

        — no PAINT line, ``R 1`` label direction, ``J 0`` justification.

        Args:
            coord: Absolute pin coordinate (on the 25-unit grid).
            pin_number: DEHDL pin number / name string.

        Returns:
            CSA LASTPIN ``$PN`` lines (5 lines, no PAINT).
        """
        x, y = coord
        return [
            f"FORCEPROP 2 LASTPIN ({x} {y}) $PN {pin_number}",
            "R 1",
            "J 0",
            f"({x - 10} {y + 10});",
            f"DISPLAY {_SCALE_PN} ({x - 10} {y + 10});",
        ]

    @staticmethod
    def _sig_name_at_pin(
        coord: tuple[int, int], net_display: str, power: bool = False,
    ) -> list[str]:
        """Emit a SIG_NAME label at a pin (B.1.2 signal/power pin).

        Phase XVII P0-1 复盘（QA P1-1，2026-08-12 实读 04p4 golden）：
        ``docs_for_reference/previous_switch_programme/.../04p4/sch_1/page9.csa``
        中 **SIG_NAME LASTPIN 块（FORCEPROP 2 元件引脚 与 FORCEPROP 3
        电源符号）均带 ``PAINT MONO + DISPLAY INVISIBLE``**（见 page9
        L365 附近 CAPACITOR SIG_NAME / L12 GND_POWER SIG_NAME）。问题
        清单"page9 L365 golden 无 PAINT"系误读（无 PAINT 的是 L63-71
        的 ``$PN`` 块）。SPCOCN-543 的真实根因是 **① 坐标未命中
        symbol.css 引脚 / ③ 旋转组合** —— 由 ``_lastpins_for_instance``
        的方案 B（坐标命中校验）/ C（旋转 SIG_NAME 改放 WIRE）/ D（引脚
        数不匹配跳过）处理，与 PAINT 无关。本函数恢复 PAINT 以完全对齐
        golden（电源符号不再需要豁免，二者格式一致）。
        """
        x, y = coord
        prefix = "3" if power else "2"
        return [
            f"FORCEPROP {prefix} LASTPIN ({x} {y}) SIG_NAME {net_display}",
            "J 0",
            f"({x + 10} {y + 10});",
            f"DISPLAY {_SCALE_SIG_NAME} ({x + 10} {y + 10});",
            f"PAINT {_PAINT_MONO} ({x + 10} {y + 10});",
            f"DISPLAY INVISIBLE ({x + 10} {y + 10});",
        ]

    @staticmethod
    def _sig_name_on_wire(
        coord: tuple[int, int], net_display: str,
        label_offsets: Optional[dict[str, tuple[int, int]]] = None,
    ) -> list[str]:
        """Emit a SIG_NAME label on a wire (B.1.2 explicit named net).

        Phase XIV D1: ``label_offsets``（text_layout 解算结果）只影响
        本独立 FORCEPROP 标签坐标 —— 无 LASTPIN，不参与电气。
        """
        _off = (label_offsets or {}).get(f"{net_display}.SIG_NAME", (0, 0))
        x, y = coord[0] + _off[0], coord[1] + _off[1]
        return [
            f"FORCEPROP 2 LAST SIG_NAME {net_display}",
            "J 0",
            f"({x} {y});",
            f"DISPLAY {_SCALE_TRANSITION} ({x} {y});",
            f"PAINT {_PAINT_ORANGE} ({x} {y});",
        ]

    @staticmethod
    def _choose_sig_name_sources(net_pin_map: dict[str, list[dict]]) -> set[str]:
        """Choose one source pin per net for its SIG_NAME label.

        Returns:
            Set of ``refdes.pin`` keys whose LASTPIN carries SIG_NAME
            instead of $PN.
        """
        sources: set[str] = set()
        for pins in net_pin_map.values():
            if not pins:
                continue
            # Phase XIII T2: IOPORT pins are cross-page connector ports —
            # their own FORCEADD block already carries HDL_PORT/VHDL_PORT
            # labels, so prefer a real component pin for the SIG_NAME label
            # (the net name must stay visible at a device).
            real = [
                p for p in pins
                if not str(p.get("refdes", "")).startswith("IOPORT_")
            ]
            candidates = real or pins
            power_pins = [p for p in candidates if p.get("is_power_symbol")]
            chosen = power_pins[0] if power_pins else candidates[0]
            sources.add(f"{chosen['refdes']}.{chosen['pin']}")
        return sources

    @staticmethod
    def _key_pairs(sources: set[str]) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        for key in sources:
            parts = key.rsplit(".", 1)
            if len(parts) == 2:
                pairs.add((parts[0], parts[1]))
        return pairs

    def _net_display_for_pin(self, conn, page_conn, net_id: str) -> str:
        """Return the page net display name for a design-level net id."""
        for pnr in page_conn.nets:
            if pnr.pin_net_id == net_id:
                return pnr.display_name
        for pnr in page_conn.nets:
            if pnr.net_id == net_id:
                return pnr.display_name
        return ""

    def _power_net_display(self, page_conn, net_name: str) -> str:
        """Page net display name for a power symbol's net.

        Phase XI P0-遗留#2: resolves the page net record so a power pin is
        grouped with regular pins on the same net (e.g. ``GND`` →
        ``GND\\g``) — this is what keeps wire routing and the one-SIG_NAME-
        per-net rule consistent.  Falls back to the raw name when the net is
        absent from the page.

        Phase XVI T2: ``ioport.manual_names`` 人工网名覆盖在此解析层生效
        （仅影响 IOPORT/电源网 → 页网解析；不改 con/xcon/csv 全局网名）。
        """
        from ..net_utils import con_name
        manual = self._routing_cfg.ioport.manual_names or {}
        if net_name in manual:
            net_name = manual[net_name]
        bare = con_name(net_name)
        pnr = page_conn.net_by_bare.get(bare)
        if pnr is not None:
            return pnr.display_name
        return net_name

    # ------------------------------------------------------------------
    #  Pin offsets from symbol.css (C commands) + fallback heuristics
    # ------------------------------------------------------------------

    def _get_x_label_offsets(
        self, body_name: str, section: int
    ) -> dict[str, tuple[int, int]]:
        """Read X-command label offsets (HDL_PORT / VHDL_PORT) from symbol.css.

        Port symbols (IOPORT/INPORT/OUTPORT) declare their property labels
        with ``X "LABEL" "VALUE" x y`` commands, which SymbolCssPinParser
        (C commands only) does not capture.  Returns label name → (x, y)
        relative offset; empty when the css is unavailable.

        Args:
            body_name: HDL cell name (e.g. "IOPORT").
            section: Symbol view number.

        Returns:
            Dict ``{"HDL_PORT": (x, y), ...}``.
        """
        cache_key = f"xlabel:{body_name}:{section}"
        if cache_key in self._prop_offset_cache:
            return self._prop_offset_cache[cache_key]  # type: ignore[return-value]
        if not self._hdl_lib_path:
            self._prop_offset_cache[cache_key] = {}
            return {}
        css_path = (
            self._hdl_lib_path / body_name.lower() / f"sym_{section}" / "symbol.css"
        )
        if not css_path.exists():
            css_path = self._hdl_lib_path / body_name / f"sym_{section}" / "symbol.css"
        if not css_path.exists():
            self._prop_offset_cache[cache_key] = {}
            return {}
        import re as _re
        _xre = _re.compile(
            r'^\s*X\s+"([^"]+)"\s+"[^"]*"\s+(-?[\d.]+)\s+(-?[\d.]+)'
        )
        result: dict[str, tuple[int, int]] = {}
        try:
            _text = css_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            self._prop_offset_cache[cache_key] = {}
            return {}
        for _line in _text.splitlines():
            _m = _xre.match(_line)
            if _m:
                result[_m.group(1)] = (
                    int(float(_m.group(2))), int(float(_m.group(3))),
                )
        self._prop_offset_cache[cache_key] = result
        return result

    @staticmethod
    def _placeholder_outline(pin_count: int) -> str:
        """Placeholder CDS_LMAN_SYM_OUTLINE for unmatched multi-pin ICs.

        Phase XIII T3: sizes the rectangle from ``_fallback_pin_offsets``
        perimeter layout (left column x=-150, right column x=+150, 100-unit
        pin pitch), so Cadence renders a body whose geometry matches where
        the fallback pins are placed.

        Args:
            pin_count: Number of connected pins on the instance.

        Returns:
            ``"x1,y1,x2,y2"`` outline string.
        """
        n = max(int(pin_count), 1)
        if n <= 12:
            half = (n + 1) // 2
            bottom = min(150 - (half - 1) * 100, -150)
            return f"-150,150,150,{bottom}"
        cols = 4
        per_col = (n + cols - 1) // cols
        pitch = 50 if per_col <= 12 else 25
        bottom = 150 - (per_col - 1) * pitch
        return f"-200,150,200,{bottom}"

    @staticmethod
    def _wire_through_body_exempt(
        seg: tuple[int, int, int, int],
        body: tuple[int, int, int, int],
        outline_map: dict,
        pin_coords: dict,
        net_display: str = "",
    ) -> tuple[bool, str]:
        """D2 自身引脚引出 / 电源符号挂轨豁免判定（Phase XXII QA）。

        真实库引脚在 outline 内，P→E 引出段必然穿过自己的 outline ——
        这是正常电气引出，不应计为违规。豁免条件①：穿体段的一个端点 ∈
        该 body 所属实例的引脚坐标集合（pin→body 反查 outline_map）。
        豁免条件②：**电源网**（GND/VCC/12V0 等 ``\\g`` 后缀）挂轨穿**小体**
        （≤250，多为电源符号）属正常电气 —— 证据化豁免 reason=power_symbol。

        Args:
            seg: 穿体线段 (x1,y1,x2,y2)。
            body: 被穿过的元件轮廓 (x0,y0,x1,y1)。
            outline_map: ``{refdes: (x0,y0,x1,y1)}`` 元件轮廓表。
            pin_coords: ``refdes.pin → (x,y)`` 引脚坐标表（单源）。
            net_display: 网络显示名（电源网 ``GND\\g`` 等判定 power_symbol）。

        Returns:
            ``(exempt, reason)`` —— exempt=True 时 reason∈
            {self-pin, power_symbol}；False 时 reason=""（真违规）。
        """
        owner: str | None = None
        for _rd, _rect in outline_map.items():
            if tuple(_rect) == tuple(body):
                owner = str(_rd)
                break
        if owner is None:
            return False, ""
        owns = {
            tuple(c) for k, c in pin_coords.items()
            if str(k).rsplit(".", 1)[0] == owner
        }
        if (tuple(seg[:2]) in owns) or (tuple(seg[2:]) in owns):
            return True, "self-pin"
        # 电源符号挂轨：电源网挂轨穿小体（电源符号 GND/VCC 等）属正常电气。
        # 小体判定 ≤250（电源符号 outline 通常 ≤200）；必须同时是电源网
        # （\\g 后缀 或 GND/VCC 前缀），防止误豁免真实小元件。
        _w = abs(body[2] - body[0])
        _h = abs(body[3] - body[1])
        _net_l = str(net_display).lower().replace("\\g", "")
        _is_power = (
            _net_l.endswith("\\g") or "gnd" in _net_l or _net_l.startswith("vcc")
            or _net_l.startswith("12v") or _net_l.startswith("3v")
            or _net_l.startswith("5v") or _net_l.startswith("1v")
            or _net_l.startswith("0v")
        )
        if _w <= 250 and _h <= 250 and _is_power:
            return True, "power_symbol"
        return False, ""

    @staticmethod
    def _seg_on_trunk(
        seg: tuple[int, int, int, int],
        trunk_info: tuple[int, bool],
    ) -> bool:
        """True when a wire segment lies ON the net's trunk line.

        Phase XXIII R-2（T3.2）：``route_nets`` 记录的 trunk 线信息
        ``(trunk, vertical)`` —— vertical=True 表示水平 trunk（y 固定），
        False 表示垂直 trunk（x 固定）。穿体段若落在 trunk 线上，报告用
        ``reason=trunk_blocked`` 归类（密集页无解回退）。

        Args:
            seg: 穿体线段 (x1,y1,x2,y2)。
            trunk_info: ``(trunk, vertical)``（wire_layout 记录）。

        Returns:
            True when the segment coincides with the trunk line.
        """
        trunk, vertical = trunk_info
        x1, y1, x2, y2 = seg
        if vertical:  # horizontal trunk（y 固定）
            return y1 == y2 == int(trunk)
        return x1 == x2 == int(trunk)

    def _collect_body_outlines(
        self,
        conn: "DesignConnectivity",
        page_conn,
        body_coords: dict[str, tuple[int, int]],
    ) -> list[tuple[int, int, int, int]]:
        """Expand each instance's body outline into a rectangle list.

        Returns absolute ``(min_x, min_y, max_x, max_y)`` rectangles used
        by WireLayoutEngine to keep trunks away from component bodies
        (Phase XIII T4: previously body_outlines were never passed, so
        trunks cut straight through symbols).

        Args:
            conn: Design connectivity model.
            page_conn: Page connectivity model.
            body_coords: refdes → absolute body (x, y).

        Returns:
            List of normalized body rectangles.
        """
        return list(
            self._collect_body_outlines_map(conn, page_conn, body_coords).values()
        )

    def _apply_passive_orientation(
        self,
        conn: "DesignConnectivity",
        page_conn,
        body_coords: dict[str, tuple[int, int]],
        pin_coords: dict[str, tuple[int, int]],
        net_pin_map: dict[str, list],
        outline_map: dict[str, tuple[int, int, int, int]],
    ) -> None:
        """Phase XXIII P1-4：被动元件符号方向随连线（``rotate_passives``）。

        对 prefix ∈ {R, L, FB, FERRI, BEAD} 且恰 2 引脚的实例，取两个
        引脚绝对坐标（pin_coords 单源）判定连线主轴：
          * Δx > Δy（水平）→ 目标 rotation 0/180（outline 不 swap）；
          * Δy > Δx（垂直）→ 目标 rotation 90/270（outline 宽↔高 swap）。
        目标与当前有效旋转不同时，按增量旋转重算该实例引脚偏移
        （``coord_transform.rotate_point`` 旋转链复用），并同步：
          * ``pin_coords`` / ``net_pin_map``（WIRE 端点 = LASTPIN 同源）；
          * ``self._pin_offset_map``（Pass 2 坐标命中校验 expected 单源）；
          * ``self._effective_views``（Pass 2 R 行 / SIG_NAME 位置同源）；
          * ``outline_map``（布线避让用绝对矩形 = body + swap 后轮廓）。

        默认关（``placement.rotate_passives=False``）——调用方在开关开启
        时才调用本方法；任何异常由调用方捕获降级。

        Args:
            conn: DesignConnectivity。
            page_conn: PageConnectivity。
            body_coords: refdes → body (x, y)。
            pin_coords: ``refdes.pin`` → absolute (x, y)（就地改写）。
            net_pin_map: Net display name → pin list（就地改写 coord）。
            outline_map: ``{refdes: (x0,y0,x1,y1)}`` 元件轮廓（就地改写）。
        """
        from . import orientation_planner
        from .coord_transform import rotate_point

        for irec in page_conn.instances:
            refdes = str(irec.refdes)
            if irec.is_power_symbol or not orientation_planner.is_passive_refdes(refdes):
                continue
            pins = list(getattr(irec, "pins", []) or [])
            if len(pins) != 2:
                continue
            keys = [f"{refdes}.{pre.pin_number}" for pre in pins]
            coords = [pin_coords.get(k) for k in keys]
            if any(c is None for c in coords):
                continue
            section = irec.section
            eff = self._effective_views.get(
                refdes,
                (section, _dehdl_rotation(int(getattr(irec, "rotation", 0) or 0))),
            )
            eff_section, eff_rot_dehdl = eff
            # EDIF rotation（DEHDL 90↔270 映射求逆）。
            if eff_rot_dehdl == 90:
                edif_cur = 270
            elif eff_rot_dehdl == 270:
                edif_cur = 90
            else:
                edif_cur = eff_rot_dehdl
            # outline（真实库 props 或 placeholder/mock 生成轮廓）。
            outline = None
            placeholder = self._placeholder_for_irec(irec, irec.cell_name or "", section)
            if placeholder is not None:
                outline = getattr(placeholder, "outline", "") or ""
            if not outline:
                outline = self._resolve_prop(
                    irec.properties or {}, "CDS_LMAN_SYM_OUTLINE",
                ) or ""
            new_rot, new_outline = orientation_planner.apply_passive_orientation(
                refdes, [tuple(c) for c in coords], outline, edif_cur,
            )
            if new_rot == edif_cur:
                continue
            new_rot_dehdl = _dehdl_rotation(new_rot)
            delta = (new_rot_dehdl - eff_rot_dehdl) % 360
            bx, by = body_coords[refdes]
            for key in keys:
                off = self._pin_offset_map.get(key)
                if off is None:
                    continue
                new_off = rotate_point(off[0], off[1], delta)
                self._pin_offset_map[key] = (new_off[0], new_off[1])
                pin_coords[key] = (bx + new_off[0], by + new_off[1])
            # net_pin_map 中该实例引脚的 coord 同步（WIRE 端点单源）。
            for _pins in net_pin_map.values():
                for _p in _pins:
                    if str(_p.get("refdes", "")) == refdes:
                        _k = f"{refdes}.{_p.get('pin', '')}"
                        _c = pin_coords.get(_k)
                        if _c is not None:
                            _p["coord"] = _c
            self._effective_views[refdes] = (eff_section, new_rot_dehdl)
            # outline swap：绝对矩形 = body + swap 后轮廓。
            if new_outline:
                try:
                    _x1, _y1, _x2, _y2 = (float(v) for v in new_outline.split(","))
                except ValueError:
                    _x1 = _y1 = _x2 = _y2 = 0.0
                outline_map[refdes] = (
                    bx + int(min(_x1, _x2)), by + int(min(_y1, _y2)),
                    bx + int(max(_x1, _x2)), by + int(max(_y1, _y2)),
                )
            logger.debug(
                "Passive orientation %s: %s°(EDIF %s) → %s°(DEHDL %s), "
                "outline %s",
                refdes, edif_cur, eff_rot_dehdl, new_rot, new_rot_dehdl,
                new_outline or "(unchanged)",
            )

    def _collect_body_outlines_map(
        self,
        conn: "DesignConnectivity",
        page_conn,
        body_coords: dict[str, tuple[int, int]],
    ) -> dict[str, tuple[int, int, int, int]]:
        """Expand each instance's body outline into a refdes-keyed map.

        Phase XIV D2: the SAME rectangles feed both the router (trunk
        avoidance) and the OverlapDetector (报告只报告不移动)，保证
        重叠检测与布线避让使用一致的轮廓几何。

        Args:
            conn: Design connectivity model.
            page_conn: Page connectivity model.
            body_coords: refdes → absolute body (x, y).

        Returns:
            ``{refdes: (min_x, min_y, max_x, max_y)}`` normalized rectangles.
        """
        outlines: dict[str, tuple[int, int, int, int]] = {}
        for irec in page_conn.instances:
            x, y = body_coords[irec.refdes]
            body_name = irec.cell_name or self._cell_label(conn, irec.cell_id)
            # Phase XV P0-F: placeholder outline must match the generated
            # symbol so trunk avoidance uses the true body geometry.
            placeholder = self._placeholder_for_irec(irec, body_name, irec.section)
            if irec.is_power_symbol:
                body_lower = (body_name or "").lower()
                outline = "-75,75,75,-75" if body_lower == "vcc_circle" else "-50,0,50,-50"
            else:
                props = irec.properties or {}
                outline = self._resolve_prop(props, "CDS_LMAN_SYM_OUTLINE")
                if placeholder is not None:
                    outline = placeholder.outline
                if not outline and len(irec.pins) > 1 and not self._get_css_pin_offsets(
                    body_name, irec.section
                ):
                    outline = self._placeholder_outline(len(irec.pins))
                if not outline:
                    outline = "-50,0,50,-25"
            try:
                x1, y1, x2, y2 = (float(v) for v in outline.split(","))
            except ValueError:
                continue
            outlines[irec.refdes] = (
                x + int(min(x1, x2)), y + int(min(y1, y2)),
                x + int(max(x1, x2)), y + int(max(y1, y2)),
            )
        return outlines

    def _get_css_pin_offsets(self, body_name: str, section: int) -> dict[str, tuple[int, int]]:
        """Read pin offsets (C commands) from symbol.css for a body.

        Returns:
            Dict mapping C-command text (pin name or number) → (x, y).
        """
        cache_key = f"{body_name}:{section}"
        if cache_key in self._prop_offset_cache:
            return self._prop_offset_cache[cache_key]  # type: ignore[return-value]
        if not self._hdl_lib_path:
            self._prop_offset_cache[cache_key] = {}
            return {}
        css_path = (
            self._hdl_lib_path / body_name.lower() / f"sym_{section}" / "symbol.css"
        )
        if not css_path.exists():
            css_path = self._hdl_lib_path / body_name / f"sym_{section}" / "symbol.css"
        if not css_path.exists():
            logger.debug("symbol.css not found for %s", css_path)
            self._prop_offset_cache[cache_key] = {}
            return {}
        from ..parser.symbol_css import SymbolCssPinParser
        try:
            offsets, _outline = SymbolCssPinParser().parse_file(css_path)
        except Exception as exc:
            logger.warning("symbol.css parse failed %s: %s", css_path, exc)
            offsets = {}
        self._prop_offset_cache[cache_key] = offsets
        return offsets

    def _get_pin_name_map(self, body_name: str) -> dict[str, str]:
        """Read chips.prt ``PIN_NUMBER → pin name`` map for a body.

        Multi-pin ICs (CH347/U6G...) declare FUNCTIONAL pin names in
        symbol.css C commands (RST#, TXD1) but the netlist supplies
        NUMERIC pin numbers (1..20).  chips.prt maps ``'RST#':
        PIN_NUMBER='(1)'`` — this helper reads that mapping so pin
        offsets can be resolved by numeric pin number.

        Returns:
            ``{pin_number: pin_name}`` (both uppercased and raw keys).
        """
        if not self._hdl_lib_path:
            return {}
        cache_key = f"pinmap:{body_name}"
        if cache_key in self._prop_offset_cache:
            return self._prop_offset_cache[cache_key]  # type: ignore[return-value]
        import re as _re
        result: dict[str, str] = {}
        for _sub in ("chips", "entity"):
            _prt = self._hdl_lib_path / body_name.lower() / _sub / "chips.prt"
            if not _prt.exists():
                _prt = self._hdl_lib_path / body_name / _sub / "chips.prt"
            if not _prt.exists():
                continue
            try:
                _text = _prt.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            _cur_name = ""
            for _line in _text.splitlines():
                _m = _re.match(r"^\s*'([^']+)'\s*:\s*$", _line)
                if _m:
                    _cur_name = _m.group(1)
                    continue
                _mn = _re.match(
                    r"^\s*PIN_NUMBER\s*=\s*'?\s*\(\s*([^)]+?)\s*\)\s*'?\s*;",
                    _line, _re.IGNORECASE,
                )
                if _mn is None:
                    # 'PIN_NUMBER='(1)'; — quote directly before paren
                    _mn = _re.match(
                        r"^\s*PIN_NUMBER\s*=\s*'\(\s*([^)]+?)\s*\)'?\s*;",
                        _line, _re.IGNORECASE,
                    )
                if _mn and _cur_name:
                    _num = _mn.group(1).strip()
                    result[str(_num).upper()] = _cur_name
                    result[str(_num)] = _cur_name
            if result:
                break
        self._prop_offset_cache[cache_key] = result
        return result

    @staticmethod
    def _fallback_pin_offsets(
        body_name: str, section: int, pin_count: int,
    ) -> dict[str, tuple[int, int]]:
        """Heuristic pin offsets when symbol.css is missing (B.2 fallback).

        Args:
            body_name: HDL cell name (lowercase; may be a raw library_id
                like ``c1`` when matching is unavailable).
            section: Symbol view number.
            pin_count: Number of connected pins on the instance.

        Returns:
            Dict pin_name/number → (x, y) relative offset.
        """
        b = body_name.lower().rstrip("0123456789_")
        # 2-pin passives (also match raw refdes prefixes C/R/L/D/LED/FB)
        if b in ("capacitor", "resistor", "inductor", "diode", "led", "bead", "fb"):
            if section >= 2:
                return {"1": (-75, 0), "2": (75, 0)}
            return {"1": (0, -75), "2": (0, 50)}
        if b in ("c", "r", "l", "d", "fb"):
            if section >= 2:
                return {"1": (-75, 0), "2": (75, 0)}
            return {"1": (0, -75), "2": (0, 50)}
        if b in ("gnd_power", "gnd"):
            return {"1": (0, 50), "GND": (0, 50)}
        if b in ("vcc_circle", "vcc"):
            return {"1": (0, -50), "G<SIZE-1..0> \\B": (0, -50)}
        if b == "mark":
            return {"1": (0, 0)}
        # multi-pin IC: distribute within a bounded box so large unmatched
        # chips (e.g. SOCs that fell back from their real symbol to a small
        # matched cell) keep every pin on the C SIZE PAGE instead of
        # extending thousands of units off-page.
        n = max(pin_count, 1)
        offsets: dict[str, tuple[int, int]] = {}
        if n <= 12:
            # Small chips (Phase XI behavior): two perimeter columns at
            # ±150 with 100-unit pitch (left column top→bottom, then the
            # right column bottom→top).
            half = (n + 1) // 2
            for i in range(1, n + 1):
                if i <= half:
                    offsets[str(i)] = (-150, 150 - (i - 1) * 100)
                else:
                    j = i - half
                    offsets[str(i)] = (150, -150 + (j - 1) * 100)
            return offsets
        # Large chips: four columns (x = -200/-100/+100/+200), pitch 50
        # (≤48 pins) or 25 (grid minimum), top-aligned — the extent stays
        # within ±(150..-375) so pins remain inside the page.
        cols = 4
        per_col = (n + cols - 1) // cols
        pitch = 50 if per_col <= 12 else 25
        col_x = (-200, -100, 100, 200)
        for i in range(1, n + 1):
            col = (i - 1) // per_col
            row = (i - 1) % per_col
            offsets[str(i)] = (col_x[col], 150 - row * pitch)
        return offsets



