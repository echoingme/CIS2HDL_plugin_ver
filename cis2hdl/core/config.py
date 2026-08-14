"""Unified project configuration — single source of truth for ALL parameters.

All parameters that were previously hardcoded in parsers/writers/GUI are
now defined here and accessed via the global `Config` instance.

Usage:
    from cis2hdl.core.config import config
    page_width = config.page.default_width
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


# =============================================================================
#  Configuration dataclasses
# =============================================================================


@dataclass
class PageConfig:
    """Schematic page defaults — from DSN XSD and creferhdl."""

    default_width: int = 3520
    default_height: int = 2720

    # Layout grid
    grid_spacing: int = 16
    pin_to_pin: int = 0

    # Instance auto-layout (Phase I-A, replaced by DSN coordinates in Phase I-B)
    layout_start_x: int = 100
    layout_start_y: int = 100
    layout_step_x: int = 200
    layout_step_y: int = 200
    layout_margin: int = 200  # Right margin before row wrap

    # ═══ C 纸 (C SIZE PAGE) 布局参数 — CSA 模式专用 ═══
    # 来源: 参考库 generate_hdl_sch.py + page1.scr
    # C 纸坐标空间: -10750,8275,0,0 (Cadence C size page 17x11 inches)
    # 可用区域: X∈[-10200, -550], Y∈[400, 7200]
    c_page_start_x: int = -10500      # 网格起始 X (Appendix B: START_X)
    c_page_start_y: int = 7500        # 网格起始 Y (Appendix B: START_Y)
    c_page_step_x: int = 2000         # 网格列间距 (Appendix B: COMPONENT_SPACING_X)
    c_page_step_y: int = 1500         # 网格行间距 (Appendix B: COMPONENT_SPACING_Y)
    c_page_cols: int = 5              # 网格列数 (Appendix B: COLS)
    c_page_x0: int = -10200           # C 纸可用区域左边界 (Appendix B: C_PAGE_X0)
    c_page_x1: int = -550             # C 纸可用区域右边界 (Appendix B: C_PAGE_X1)
    c_page_y0: int = 400              # C 纸可用区域下边界 (Appendix B: C_PAGE_Y0)
    c_page_y1: int = 7200             # C 纸可用区域上边界 (Appendix B: C_PAGE_Y1)
    c_page_scale: float = 0.7         # 保形布局缩放因子 (Appendix B: SCALE_FACTOR)

    # DISPLAY 缩放因子 (来自 page1.scr, DEHDL 内部渲染参数)
    display_scale_value: float = 0.851064     # VALUE/$LOCATION 属性缩放
    display_scale_outline: float = 0.468085   # CDS_LMAN_SYM_OUTLINE 缩放
    display_scale_transition: float = 1.021277  # 隐藏属性前过渡缩放


@dataclass
class HdlConfig:
    """HDL project generation settings."""

    # Library name used in .cpm and cds.lib
    default_library_name: str = "worklib"

    # Device family attribute in .sch files
    device_family: str = "allegro"

    # Font settings
    fonts_enabled: bool = True

    # Cadence tool paths
    cadence_root: str = r"C:\Cadence\SPB_16.6"
    concept_hdl_exe: str = r"tools\fet\bin\concepthdl.exe"

    @property
    def concept_hdl_path(self) -> str:
        """Full path to concept HDL executable."""
        return f"{self.cadence_root}\\{self.concept_hdl_exe}"

    # Standard library path
    standard_lib_path: str = r"..\library\standard"

    # SOFTINCLUDE paths for cds.lib
    soft_include_paths: list[str] = field(default_factory=lambda: [
        r"$CHDL_LIB_INST_DIR/share/library/cds.lib",
        r"$CHDL_LIB_INST_DIR/share/library/ams_cds.lib",
    ])


@dataclass
class NetConfig:
    """Network classification and naming rules."""

    # ISCF ground network names (from ORCAD_SOURCE §11.3)
    ground_names: set[str] = field(default_factory=lambda: {
        "GND", "GND_EARTH", "GND_POWER",
        "VSS", "AGND", "DGND", "PGND", "SGND", "CGND",
    })

    # ISCF power net prefixes
    power_prefixes: tuple[str, ...] = (
        "VCC", "VDD", "PP", "PN",
        "VIN_", "VOUT_",
    )

    # Illegal filename/path characters to strip
    illegal_chars: str = "/<>#$()"

    # Bus detection patterns
    bus_patterns: list[str] = field(default_factory=lambda: ["[", "("])


@dataclass
class EdifConfig:
    """EDIF parser configuration."""

    # Default EDIF version expected
    expected_version: tuple[int, int, int] = (2, 0, 0)

    # MPN key names recognized in prefix properties
    mpn_keys: set[str] = field(default_factory=lambda: {
        "Part Number", "PART_NUMBER", "MPN", "Manufacturer PN",
    })

    # DNS markers to strip from values
    dns_markers: list[str] = field(default_factory=lambda: [
        "DNI", "DNM", "DNP", "DNS", "NC",
    ])

    # Cell types that represent schematic pages (not components)
    page_cell_types: set[str] = field(default_factory=lambda: {"SCHEMATIC", "PAGE"})

    # Default view name for cells
    default_view_name: str = "symbol"

    # ── EDIF → DSN attribute back-annotation ──────────────────────────
    # Property key names (in priority order) for extracting footprint
    # and value from EDIF instance properties during type mapping.
    footprint_property_keys: tuple[str, ...] = (
        "PKG_TYPE", "PCB Footprint", "Footprint",
    )
    value_property_keys: tuple[str, ...] = (
        "VALUE", "Value",
    )

    # Library ID prefixes recognised as valid (not garbage).
    # Any library_id starting with one of these is exempt from
    # garbage detection in _map_edif_types_to_dsn().
    valid_library_id_prefixes: tuple[str, ...] = (
        "CAP_", "RES_", "IND_", "CONN_", "DIODE_", "CRYSTAL_",
        "LED_", "TVS_", "ZENER_", "FUSE_", "SW_", "BAT_",
        "CAPACITOR", "RESISTOR", "INDUCTOR", "TRANSFORMER",
        "AMPLIFIER", "REGULATOR", "LDO", "DC_DC", "INTERFACE",
        "LOGIC_GATE", "MICROCONTROLLER", "N_MOS", "P_MOS",
        "NPN", "PNP", "JFET", "DIODE", "LED", "TVS", "ZENER",
        "CRYSTAL", "OSC", "RESONATOR", "CONNECTOR", "HEADER",
        "RJ45", "RJ11", "FERRI", "BEAD", "FB", "FUSE", "SWITCH",
        "BATTERY", "TEST_POINT", "HOLE", "MARK", "SCREW",
        "EEPROM", "FLASH", "DDR", "RTL", "BCM", "MTK", "QCA",
    )


@dataclass
class GuiConfig:
    """GUI appearance and behavior settings (from UI_DESIGN_SPEC v2.0)."""

    # Window dimensions
    window_min_width: int = 1200
    window_min_height: int = 800
    project_panel_width: int = 300
    log_panel_height: int = 180

    # Colors (RGB tuples from UI_DESIGN_SPEC §3)
    color_tea: tuple[int, int, int] = (243, 233, 224)
    color_white: tuple[int, int, int] = (255, 255, 255)
    color_cyan: tuple[int, int, int] = (121, 196, 189)
    color_red: tuple[int, int, int] = (213, 91, 66)
    color_gold: tuple[int, int, int] = (255, 178, 41)
    color_ice_blue: tuple[int, int, int] = (157, 181, 191)
    color_blue: tuple[int, int, int] = (85, 132, 204)
    color_dark_gray: tuple[int, int, int] = (39, 38, 36)
    color_light_gray: tuple[int, int, int] = (173, 173, 173)
    color_dark_tea: tuple[int, int, int] = (176, 174, 162)

    # Corner radii (only 3 allowed)
    radius_small: int = 2
    radius_medium: int = 4
    radius_large: int = 8

    # Font families
    ui_font: str = "Microsoft YaHei"
    mono_font: str = "Cascadia Code"


@dataclass
class AppConfig:
    """Application-level settings."""

    # Output directory defaults
    default_output_dir: str = "output"

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # File encoding
    output_encoding: str = "utf-8"
    input_encoding: str = "utf-8"

    # Supported file extensions
    cis_extensions: list[str] = field(default_factory=lambda: [".dsn", ".edf"])
    hdl_extensions: list[str] = field(default_factory=lambda: [".cpm", ".sch"])

    # Performance tuning
    max_workers: int = 4           # Max concurrent workers for I/O-bound operations
    benchmark: bool = False        # Enable performance timing report

    # ═══ Phase XI P0-B/P0-C/P0-D2 ═══
    # Disable DSN as a component/net source.  When True, a .dsn input with a
    # same-name .EDF sibling is parsed through EDIFParser (components/pages/
    # wires) while pstxnet.dat remains the authoritative pin→net injection.
    use_dsn_components: bool = False
    # Emit CSA WIRE/LASTPIN/DOT/SIG_NAME topology (P0-C).  Set False to keep
    # the legacy property-only CSA body.
    emit_csa_wires: bool = True


@dataclass
class HdlLibConfig:
    """HDL library scanning configuration."""

    # Root path of the HDL component library
    hdl_lib_path: str = ""

    # Whether to scan subdirectories recursively
    recursive_scan: bool = True

    # Directory names to exclude from scanning
    exclude_dirs: list[str] = field(default_factory=lambda: ["temp", ".git", "__pycache__"])

    # File encodings for HDL library files
    chips_prt_encoding: str = "utf-8"
    symbol_css_encoding: str = "utf-8"
    part_ptf_encoding: str = "utf-8"


@dataclass
class ComponentMatchingConfig:
    """Component matching configuration."""

    # Exact match threshold (>= this value = automatic match)
    exact_threshold: float = 0.95

    # Fuzzy match threshold (< exact, >= fuzzy = auto with warning)
    fuzzy_threshold: float = 0.75

    # Feature extraction threshold (< fuzzy, >= feature = manual review suggested)
    feature_threshold: float = 0.60

    # Fallback threshold (< feature, >= fallback = refdes prefix with body_fallback)
    fallback_threshold: float = 0.50

    # Below fallback_threshold = require manual confirmation


@dataclass
class OutputConfig:
    """Cadence DEHDL output directory structure configuration.

    Controls the layout of generated files to match the Cadence
    DEHDL Project Manager standard directory layout.

    Reference:
        Real Cadence DEHDL project: worklib/<cell>/sch_1/pageN.cpc
    """

    # ── Directory names ──────────────────────────────────────────────
    worklib_dir: str = "worklib"        # Working library directory (relative to output root)
    temp_dir: str = "temp"              # Temp directory referenced by .cpm
    view_name: str = "sch_1"            # Schematic view directory name (fixed Cadence convention)
    hdl_lib_dir: str = "hdl_lib"        # HDL component library directory name

    # ── Default names ────────────────────────────────────────────────
    cell_name: str = ""                 # Cell short name (derived from project_name)
    library_alias: str = "worklib_lib"  # Library alias used in cds.lib DEFINE

    # ── Cadence version ──────────────────────────────────────────────
    cpm_version: str = "16.6"           # Cadence SPB version for .cpm

    # ── Standard libraries referenced in .cpm library list ───────────
    standard_libraries: tuple[str, ...] = ("hdl_lib", "standard")

    # ── Subdirectory names under cell ────────────────────────────────
    cell_subdirs: tuple[str, ...] = (
        "cfg_package",
        "cfg_pic",
        "physical",
        "variant",
    )

    # ── Cell name derivation ─────────────────────────────────────────
    # Pattern to extract the primary numeric chip ID from a project name.
    # Matches leading non-digits followed by 3-6 digit chip number.
    # Example: "RTL8367RB-VC-DEMO" → "8367", "BCM56150K" → "56150"
    cell_name_pattern: str = r'[A-Za-z]+(\d{3,6})'

    @staticmethod
    def derive_cell_name(project_name: str) -> str:
        """Derive a short cell name from a full project name.

        Examples:
            RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0  →  8367
            BCM56150K-DEMO                          →  56150
            NoDigitsProject                         →  nodigitsproject

        Args:
            project_name: Full project name from DSN or user input.

        Returns:
            Short cell name suitable for Cadence worklib directory.
        """
        if not project_name:
            return "design"

        # Look for the primary chip ID: letters followed by 3-6 digits
        match = re.search(OutputConfig.cell_name_pattern, project_name)
        if match:
            # Return just the numeric chip ID portion
            return match.group(1)

        # Try a more generic digit search as fallback
        match = re.search(r'(\d{3,6})', project_name)
        if match:
            return match.group(1)

        # Fallback: use first 16 chars, lowercased, with underscores
        fallback = project_name.replace("-", "_").replace(".", "_")
        return fallback[:16].lower()


# =============================================================================
#  Global singleton
# =============================================================================


@dataclass
class TextLayoutCfg:
    """D1 文本/标签去冲突配置（Phase XIV）。"""

    enabled: bool = False
    align_net_names: bool = True
    align_ports: bool = True
    diff_pair_pn: bool = True
    char_width_factor: float = 0.65
    line_height_factor: float = 1.2
    padding: int = 12
    min_text_w: int = 75


@dataclass
class OverlapCfg:
    """D2 元件重叠检测配置（Phase XIV）+ Phase XVIII R5 避让参数。

    R5（用户 Q3）：统一碰撞 margin 25→50（``avoid_margin``）、芯片外侧
    冗余区（``edge_clearance``）、引脚附近避让半径（``pin_avoid_radius``）
    —— 全部可配（routing.yaml），默认值对应设计验收断言。
    """

    check: bool = False
    min_area: int = 625
    auto_placement: bool = False
    # Phase XX 补丁 2（08-13 用户 p16/p17/p21 反馈）：J/T 元件与电容
    # 互相重叠无避让——OverlapResolver 已实现但从未接线（死代码）。
    # ``resolve=true`` 时在 Pass 1 后对 passive + connector 微调
    # （max_passive_move 50，芯片本体不动）。
    resolve: bool = True
    avoid_margin: int = 50
    """R5/Q3：统一碰撞 margin（25→50；``detect_collisions`` 默认值）。"""
    edge_clearance: int = 100
    """R5/Q3：芯片外侧冗余区（电线/符号不贴元件边缘）。"""
    pin_avoid_radius: int = 50
    """R5/Q3：引脚附近避让半径（trunk/stub 不得进入引脚 50 单位）。"""


@dataclass
class PowerIcCfg:
    """D4 电源芯片匹配配置（Phase XIV）。"""

    enabled: bool = False
    config_file: str = "cis2hdl/config/power_ic.yaml"


@dataclass
class PlaceholderCfg:
    """P0-F 占位符号生成配置（Phase XV）。

    ``enabled`` 默认 **true** —— 用户明确要求后端默认生效（占位符号
    替代错误的 fallback 符号，如 U6 主芯片 fallback 到 CH347），
    属于"默认关"规则的例外。关闭后回退旧行为（fallback 符号）。
    """

    enabled: bool = True


@dataclass
class IoportCfg:
    """P1-C 跨页 IOPORT 边缘分布配置（Phase XV）+ Phase XVI 审计配置。

    页内网一律用 SIG_NAME 网络名（不生成 IOPORT）；真正跨页的网生成
    IOPORT 时沿页面边缘等间距对齐分布（替代右上角 8 个一行）。

    Phase XVI（system_design0811-phase16.md Part B）：``audit`` 开启
    IOPORT 三节核对（接线/网名/孤立），``skip_orphan`` 让孤立 connector
    不生成，``manual_names`` 提供人工网名覆盖（默认不合并）。
    """

    edge_layout: bool = False
    """跨页 IOPORT 沿左/右缘等间距分布（替代默认右上角 8 个一行）。"""
    edge_x: int = -600
    """IOPORT 列固定 x（C 纸空间，默认右侧缘）。"""
    edge_step: int = 100
    """IOPORT 沿 y 的等间距步长。"""
    edge_margin: int = 300
    """距页顶的起始边距（y 从 7200 递减）。"""
    audit: bool = False
    """IOPORT 一致性核对开关（默认关；CLI --ioport-audit / --aesthetic 开启）。"""
    skip_orphan: bool = False
    """孤立 connector 是否不生成（默认只报告不跳过）。"""
    manual_names: dict[str, str] = field(default_factory=dict)
    """人工网名覆盖 {raw_name: canonical_target}（默认空=不合并）。"""
    use_net_name: bool = False
    """M5 跨页网用网络名表达（用户 D2）：true 时 CSA + con 都改网络名，
    不生成 IOPORT 符号（xcon/cpm 同步评估）。默认关（保留 IOPORT）。"""
    net_label_on_end: bool = True
    """R7：网络名标签落到电线末端/悬空端（默认开）。"""
    un_name_policy: str = "rename"
    """R3⑤：UN$ 自动网名策略 —— ``rename``（默认，稳定可读名）|
    ``keep``（保留现状）| ``omit``（省略 SIG_NAME）。只改 CSA 显示名。"""


@dataclass
class MirrorCfg:
    """T1 镜像归一化配置（Phase XVI）。

    用户 Cadence 实测发现 L20 等 mirror 实例"翻转 180°"——Phase XIII
    保守策略不输出 M 行也不镜像引脚。``normalize=true`` 时 mirror 实例的
    引脚偏移按 EDIF 2.0.0 真值镜像（镜像在前、旋转在后），渲染方向用
    ``closest_rotation_for_mirror`` 的等效 R 行近似（默认开，正确性修复）。
    """

    normalize: bool = True
    """T1 总开关（默认开；CLI --no-mirror-normalize 关闭回退 Phase XIII）。"""
    report: bool = True
    """镜像清单进 aesthetic_report [MIRROR] 节（受 aesthetic.enabled 门控）。"""


@dataclass
class TempLibCfg:
    """M1 temp_lib 模拟图标生成配置（Phase XVII，用户 D3/D8/D11）。

    ``enabled=true`` 时 csa_writer 优先用 mock_icon_lib（替代 placeholder
    占位方块）为未匹配芯片/connector 生成"模拟图标"（symbol.css +
    chips.prt + entity），写入独立 ``output/temp_lib/``（不污染 hdl_lib）。
    ``enabled=false`` 回退 placeholder（逃生舱）。

    Phase XVIII R1/R2/R9：新增 mock 语法/字号/引脚/校验字段 ——
    ``pin_font_size``（C 指令字号 32→16）、``pin_text_size``（X PIN_TEXT
    字号）、``pin_line_len``（引脚 L 段向外长度，真实库 50）、
    ``mock_text_cmd``（MOCK_TEXT 指令 P→X）、``syntax_check``（R1 生成后
    语法校验）、``structure_check``（R2 master.tag/目录结构断言）。
    """

    enabled: bool = True
    """M1 总开关（默认开；false 回退 placeholder）。"""
    lib_name: str = "temp_lib"
    """输出库目录名（相对 output 根）。"""
    annotate: bool = True
    """图标内画"模拟图标"中英标注（字号 24）。"""
    mock_text: str = "MOCK/模拟图标"
    """标注文本（用户 D11：中英双标）。"""
    pin_font_size: int = 16
    """R9：C 指令引脚标签字号（32→16，用户"缩小一半"）。"""
    pin_text_size: int = 16
    """R9：X "PIN_TEXT" 可见引脚名字号。"""
    pin_line_len: int = 50
    """R9：引脚 L 段向外长度（真实库 ch347 golden = 50 单位）。"""
    mock_text_cmd: str = "T"  # Phase XIX: T 指令可见文本+红色（P 属性不渲染）
    """R9/Q11：MOCK_TEXT 文本指令（P→X；X 是真实库画文本先例）。"""
    mock_all: bool = True
    """Phase XX（用户 08-13 决策）：**所有多引脚芯片/connector 默认用模拟
    图标输出**（无论是否匹配到 hdl_lib 真实符号）。``false`` 恢复旧行为
    （仅匹配失败/错误匹配才 mock）。GUI 面板可切换。"""
    syntax_check: bool = True
    """R1：生成后全量 symbol.css 语法校验（默认开，修复类）。"""
    structure_check: bool = True
    """R2：master.tag 分目录 / entity 四文件结构断言（默认开，修复类）。"""


@dataclass
class WireSimplifyCfg:
    """M4 wire_simplifier 后处理配置（Phase XVII，SKiDL cleanup_wires 移植）。

    ``enabled=false`` 默认关（可回退）；开启后作为 wire_layout 后处理：
    共线合并 / 悬空 stub 修剪 / 3 段阶梯化简 / 仅 T/X 真交点加 DOT。
    """

    enabled: bool = False
    """M4 总开关（默认关；开启后简化 WIRE/DOT 输出）。"""
    dot_merge: int = 50
    """就近 DOT/端点合并距离阈值（单位）。"""
    max_wire_len: int = 5000
    """超长电线断开改用网络名的阈值（用户 D5，默认 5000）。"""
    break_long: bool = False
    """R8：超长段（>max_wire_len）断开，两端改网络名标签（v9_simplify 开启）。"""
    self_intersect_check: bool = True
    """R5：自身重叠（线头）检测报告（simplify_wires 接入）。"""
    parallel_short: bool = True
    """R8：同类同信号相近引脚先短接再引出（复用 gnd_cluster_planner）。"""
    parallel_short_dist: int = 500
    """Phase XXII D4：非 GND 同信号并联判定距离阈值（与 GND 同值 500）。"""


@dataclass
class PinAuditCfg:
    """M6 引脚连接审计配置（Phase XVII）。

    ``enabled=true`` 时逐引脚评估连接状态（已接/悬空/网名不匹配/引脚名
    不匹配），输出 [PIN_AUDIT]/[HANGING] 报告。数据源 = DesignConnectivity
    模型（数据源铁律），只读诊断，不影响 CSA 输出。
    """

    enabled: bool = True
    """M6 总开关（默认开；只读诊断）。"""
    report_hanging: bool = True
    """悬空引脚报告开关（[HANGING] 条目）。"""


@dataclass
class GndDistributionCfg:
    """P1-D GND 符号分布配置（Phase XV，用户决策 1）。

    每芯片一组 GND 符号 + 无芯片区域按距离阈值补放 + 密集区多放。
    电气不变（同一 GND 网，SIG_NAME 同名连接），只增加符号数量并分布
    到各芯片附近，减少长线汇聚。
    """

    enabled: bool = False
    """总开关（默认关；CLI --gnd-distribute 或 routing.yaml 开启）。"""
    distribute_density: bool = False
    """P1-3 GND 密度补点 + trunk 避让 + outlet 绕行总开关（默认关）。

    Phase XXIII：``True`` 时 csa_writer 布线前调用
    ``gnd_cluster_planner.ensure_gnd_symbols``（页面 1/4 分块，每块
    ≥3 个 GND 引脚且距最近 GND 符号 >1500 补 ``GND_SYM_{block}``），
    GND 网 trunk 避让 ``edge_clearance+50`` 额外余量，outlet→符号段
    受阻时 90° 绕行（最多 2 次）。默认关——默认行为等价铁律；CLI
    ``--gnd-distribute`` 同时开启本开关。"""
    near_chip_offset: int = 100
    """GND 符号相对芯片 GND 引脚的外引距离（50-100 单位）。"""
    distance_threshold: int = 2000
    """无芯片区域：元件到最近 GND 符号距离超过该阈值时补放。"""
    max_per_chip: int = 1
    """每芯片最多就近放置的 GND 符号数。"""
    dense_area_threshold: int = 8
    """密集区判定：页内单位网格内元件数 ≥ 该值时多放。"""
    cluster_radius: int = 2000
    """Phase XVII R3：GND 聚类合并半径（用户问题 4"就近共用"）。

    距离 ≤ ``cluster_radius`` 的芯片 GND 引脚聚为同一簇，簇内只放置
    1 个共享 GND 符号（默认 2000 单位可配，用户 D4）。``0`` = 关闭
    聚类（回退每芯片 1 个的旧行为）。"""
    parallel_short: bool = True
    """R6/R8：簇内引脚先并联（hub 短接）再统一引出（默认开可回退）。"""
    parallel_short_dist: int = 500
    """R6/R8：并联判定距离阈值（引脚间距 > 该值不强制并联）。"""
    gnd_power_lastpin_offset: list = field(
        default_factory=lambda: [0, 50])  # SPCOCN-543: 命中 gnd_power 符号引脚 (0,50)
    """R3：GND_POWER LASTPIN 相对偏移（golden page9 = body+(50,100)，
    可配；值 ``"css"`` 回退 symbol.css 引脚 (0,50)）。mirror≠0 仍经
    rotate_point(offset, 0, mirror)。"""


@dataclass
class AestheticCfg:
    """Phase XIV 总开关与报告配置。"""

    enabled: bool = False
    report: bool = True


@dataclass
class ReportCfg:
    """Phase XVI 报告输出配置（用户要求：默认转换也生成诊断报告）。

    默认转换（p0）同样在输出根目录生成 ``aesthetic_report.txt`` 与
    ``ioport_audit_report.txt``（只读诊断，不影响 CSA 输出内容）；
    ``always_write=true`` 时报告收集器无条件创建并写出。
    """

    always_write: bool = True
    """默认转换也输出诊断报告（CLI --no-report 关闭）。"""
    aesthetic: bool = True
    """默认写出 aesthetic_report.txt（[MIRROR]/[OVERLAP]/[GRID] 等）。"""
    ioport_audit: bool = True
    """默认写出 ioport_audit_report.txt（接线/网名/孤立三节）。"""


@dataclass
class PlaceholderCfg:
    """P0-F 占位符号生成配置（Phase XV）。

    ``enabled`` 默认 **true** —— 用户明确要求后端默认生效（占位符号
    替代错误的 fallback 符号，如 U6 主芯片 fallback 到 CH347），
    属于"默认关"规则的例外。关闭后回退旧行为（fallback 符号）。
    """

    enabled: bool = True


@dataclass
class AttributeCfg:
    """R4 元件库统一 hdl_lib + CSA 属性注入配置（Phase XVIII）。

    ``inject_crossref`` 控制 CSA 属性块注入 CrossRef CSV 四字段
    （DESCRIPTION / JEDEC_TYPE / PACKAGE_TYPE / SN_NUM，golden 格式）；
    ``rewrite_origin`` 控制 ORIGIN 引用改写为 hdl_lib（Q1，audit 门禁）。
    """

    inject_crossref: bool = True
    """R4：CSA 属性块注入 CrossRef 四字段（默认开，修复类）。"""
    rewrite_origin: bool = True
    """R4/Q1：ORIGIN 引用改写为 hdl_lib（默认开；audit_origin_refs 门禁）。"""


@dataclass
class MatchingCfg:
    """R4/Q1 + R10 匹配源过滤配置（Phase XVIII）。

    ``hdl_lib_only`` 要求候选符号只能来自 hdl_lib 扫描结果，标准库/系统库
    符号（含 ORIGIN）不入候选池；``connector_pin_check`` 要求 J* connector
    候选引脚数与实例一致（R10，T04 使用）。
    """

    hdl_lib_only: bool = True
    """R4/Q1：匹配只限 hdl_lib（默认开，修复类）。"""
    connector_pin_check: bool = True
    """R10：J* connector 引脚数校验（默认开，T04 使用）。"""


@dataclass
class PlacementCfg:
    """R11/Q12 元件级微调配置（Phase XVIII）。

    ``max_passive_move`` 是被动元件（C/R/L）小范围腾挪的上限
    （芯片本体不动 D10）。
    """

    max_passive_move: int = 200
    """R11/Q12：被动元件微调上限（Phase XXI G：100→200，J/T 散开）。"""
    rotate_passives: bool = False
    """P1-4 被动元件符号方向随连线（默认关——默认行为等价铁律）。

    Phase XXIII：``True`` 时 csa_writer 生成符号后、布线前调用
    ``orientation_planner.apply_passive_orientation`` —— prefix ∈
    {R, L, FB, FERRI, BEAD} 的二端实例按两引脚连线主轴（Δx>Δy →
    水平 rotation 0/180；Δy>Δx → 垂直 90/270）旋转，outline 尺寸
    swap（宽↔高）。CLI ``--rotate-passives`` 开启。"""


@dataclass
class NetNameCfg:
    """R3⑤ 网络名稳定化配置（Phase XVIII）。

    ``un_auto_rename`` 控制 UN$ 自动网名 → 稳定可读名（stabilize_un_name）。
    """

    un_auto_rename: bool = True
    """R3⑤：UN$ → 稳定可读名（stabilize_un_name，默认开）。"""


@dataclass
class RoutingConfig:
    """Phase XIV 布线/美观化配置（D5）。

    所有新功能默认关闭；``mode`` 选择布线器（p0 | detour | edif_reuse）。
    由 ``Config.load_from_file`` 从 ``cis2hdl/config/routing.yaml`` 加载，
    也可被 CLI 参数覆盖（__main__.py convert 分支）。
    """

    mode: str = "p0"
    lane_pitch: int = 50
    grid: int = 25
    detour_stubs: bool = True
    use_edif_wires: bool = False
    cross_page_opt: bool = False
    fallback_to_p0: bool = True
    # ── Phase XVII R2: 非均匀轨道 + 网布线顺序（SKiDL 思想 A/B） ──────
    nonuniform_tracks: bool = False
    """轨道优先模式（SKiDL ``create_routing_tracks`` 思想，默认关可回退）。

    True 时 ``_find_lane`` 优先在"元件 bbox 边坐标轨道"上找空闲车道
    （同列/同行元件自然共线对齐），未命中再回退现有均匀车道。
    CLI ``--nonuniform-tracks`` 开启。
    """
    net_order: str = "long_first"
    """网布线顺序（默认 ``long_first`` 保持现状；``short_first`` =
    SKiDL ``rank_net`` 短网先布 —— 短网先占车道不易被挤）。CLI
    ``--net-order short_first|long_first`` 覆盖。"""
    # ── Phase XV P1-G: stub 引出段（aesthetic/detour 模式） ─────────
    stub_lead: int = 100
    """stub 从引脚先外引的距离（默认 100，可配）。"""
    lead_differentiate: bool = True
    """相邻引脚（间距 ≤ 75）引出段错开（100/150/200 交替）。"""
    lead_diff_min_gap: int = 75
    """差异化触发的最小引脚间距。"""
    max_detour: int = 50
    """绕障余量（outline 外推距离，= _DETOUR_MARGIN）。"""
    edge_clearance: int = 100
    """R5：页面边缘冗余区 —— 电线不贴 C 纸页边（默认 100，可配）。"""
    three_stage_stub: bool = True
    """R5：三段式 stub（延伸→折线→调头）总开关（默认开，可关回退）。"""
    text_layout: TextLayoutCfg = field(default_factory=TextLayoutCfg)
    overlap: OverlapCfg = field(default_factory=OverlapCfg)
    manual_matches: str = ""
    export_unmatched: str = ""
    power_ic: PowerIcCfg = field(default_factory=PowerIcCfg)
    aesthetic: AestheticCfg = field(default_factory=AestheticCfg)
    report: ReportCfg = field(default_factory=ReportCfg)
    placeholder: PlaceholderCfg = field(default_factory=PlaceholderCfg)
    ioport: IoportCfg = field(default_factory=IoportCfg)
    mirror: MirrorCfg = field(default_factory=MirrorCfg)
    gnd_distribution: GndDistributionCfg = field(default_factory=GndDistributionCfg)
    temp_lib: TempLibCfg = field(default_factory=TempLibCfg)
    wire_simplify: WireSimplifyCfg = field(default_factory=WireSimplifyCfg)
    pin_audit: PinAuditCfg = field(default_factory=PinAuditCfg)
    # ── Phase XVIII R4/Q1 + R3⑤ ────────────────────────────────────
    attribute: AttributeCfg = field(default_factory=AttributeCfg)
    matching: MatchingCfg = field(default_factory=MatchingCfg)
    placement: PlacementCfg = field(default_factory=PlacementCfg)
    net_name: NetNameCfg = field(default_factory=NetNameCfg)
    chip_config: str = ""
    """统一人工配置 chip_config.yaml 路径（用户 D7；--manual-matches 别名）。"""

    @classmethod
    def from_dict(cls, data: dict) -> "RoutingConfig":
        """Build a RoutingConfig from a YAML dict, ignoring unknown keys.

        Args:
            data: The ``routing`` section (or whole file) dict.

        Returns:
            RoutingConfig with defaults for missing fields.
        """
        cfg = cls()
        for key, value in (data or {}).items():
            if key == "text_layout" and isinstance(value, dict):
                cfg.text_layout = replace(cfg.text_layout, **value)
            elif key == "overlap" and isinstance(value, dict):
                cfg.overlap = replace(cfg.overlap, **value)
            elif key == "power_ic" and isinstance(value, dict):
                cfg.power_ic = replace(cfg.power_ic, **value)
            elif key == "aesthetic" and isinstance(value, dict):
                cfg.aesthetic = replace(cfg.aesthetic, **value)
            elif key == "report" and isinstance(value, dict):
                cfg.report = replace(cfg.report, **value)
            elif key == "placeholder" and isinstance(value, dict):
                cfg.placeholder = replace(cfg.placeholder, **value)
            elif key == "ioport" and isinstance(value, dict):
                cfg.ioport = replace(cfg.ioport, **value)
            elif key == "mirror" and isinstance(value, dict):
                cfg.mirror = replace(cfg.mirror, **value)
            elif key == "gnd_distribution" and isinstance(value, dict):
                cfg.gnd_distribution = replace(cfg.gnd_distribution, **value)
            elif key == "temp_lib" and isinstance(value, dict):
                cfg.temp_lib = replace(cfg.temp_lib, **value)
            elif key == "wire_simplify" and isinstance(value, dict):
                cfg.wire_simplify = replace(cfg.wire_simplify, **value)
            elif key == "pin_audit" and isinstance(value, dict):
                cfg.pin_audit = replace(cfg.pin_audit, **value)
            elif key == "attribute" and isinstance(value, dict):
                cfg.attribute = replace(cfg.attribute, **value)
            elif key == "matching" and isinstance(value, dict):
                cfg.matching = replace(cfg.matching, **value)
            elif key == "placement" and isinstance(value, dict):
                cfg.placement = replace(cfg.placement, **value)
            elif key == "net_name" and isinstance(value, dict):
                cfg.net_name = replace(cfg.net_name, **value)
            elif hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg


class Config:
    """Global configuration singleton — one source of truth."""

    # Class-level singleton
    _instance: ClassVar[Config | None] = None

    def __init__(self) -> None:
        self.page = PageConfig()
        self.hdl = HdlConfig()
        self.net = NetConfig()
        self.edif = EdifConfig()
        self.gui = GuiConfig()
        self.app = AppConfig()
        self.hdl_lib = HdlLibConfig()
        self.matching = ComponentMatchingConfig()
        self.output = OutputConfig()
        self.routing = RoutingConfig()

    @classmethod
    def get(cls) -> Config:
        """Get or create the global Config singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reset(self) -> None:
        """Reset to defaults (useful for testing)."""
        self.__init__()

    def load_from_file(self, path: Path) -> None:
        """Load configuration overrides from a YAML file (Phase XIV).

        Phase XIV: ``cis2hdl/config/routing.yaml`` defines the routing /
        text-layout / overlap / power_ic / aesthetic switches.  Each
        section is applied to the matching dataclass via
        ``dataclasses.replace`` so defaults stay immutable.

        Args:
            path: Path to a YAML config file.

        Raises:
            FileNotFoundError: When ``path`` does not exist.
            ValueError: When the YAML content is not a mapping.
        """
        import yaml

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        data: Any = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config file {p} must contain a YAML mapping")

        # ── page section ────────────────────────────────────────────
        if isinstance(data.get("page"), dict):
            self.page = replace(self.page, **data["page"])

        # ── routing section (Phase XIV) ─────────────────────────────
        if isinstance(data.get("routing"), dict):
            self.routing = RoutingConfig.from_dict(data["routing"])

        # Phase XVII P2-1 (QA): routing.yaml 的**顶层子节**（text_layout /
        # overlap / power_ic / aesthetic / report / placeholder / ioport /
        # mirror / gnd_distribution / temp_lib / wire_simplify / pin_audit）
        # 此前被忽略 —— 与 ``routing:`` 下同构的节合并进 RoutingConfig。
        # 修复后 ``ioport.use_net_name`` 等全部可经 yaml 启用（否则 CLI
        # 无旗标、yaml 无效，用户无法开启 M5 网络名连接）。
        _top_sections = (
            "text_layout", "overlap", "power_ic", "aesthetic", "report",
            "placeholder", "ioport", "mirror", "gnd_distribution",
            "temp_lib", "wire_simplify", "pin_audit",
            "attribute", "matching", "placement", "net_name",
        )
        _merged = {
            key: value for key, value in (data.get("routing") or {}).items()
        }
        for key in _top_sections:
            if isinstance(data.get(key), dict) and key not in _merged:
                _merged[key] = data[key]
        if _merged:
            self.routing = RoutingConfig.from_dict(_merged)

        # ── top-level routing.yaml keys (manual_matches etc.) ───────
        for key in ("manual_matches", "export_unmatched", "chip_config"):
            if key in data and hasattr(self.routing, key):
                setattr(self.routing, key, data[key])

        logger.info("Config loaded from %s (routing.mode=%s)", p, self.routing.mode)

    def load_pipeline(self, path: Path) -> None:
        """S1 便捷入口：加载 pipeline.yaml 并写回 routing + app 段。

        等价桥：``pipeline.yaml → PipelineConfig → to_routing_config()``；
        engine 运行参数写回 app（max_workers/benchmark/output_dir）。

        Args:
            path: 指向 pipeline.yaml（或任意 PipelineConfig yaml）的路径。

        Raises:
            FileNotFoundError: 当 ``path`` 不存在。
            ValueError: 当 YAML 内容不是 mapping。
        """
        from .pipeline_config import PipelineConfig  # 延迟导入避免循环依赖

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        cfg = PipelineConfig.from_yaml(p)
        self.routing = cfg.to_routing_config()
        self.app.max_workers = cfg.engine.max_workers
        self.app.benchmark = cfg.engine.benchmark
        self.app.default_output_dir = cfg.engine.output_dir
        logger.info("Pipeline config loaded from %s (profile=%s)", p, cfg.profile)

    def save_to_file(self, path: Path) -> None:
        """Save current configuration to a JSON file (future)."""
        raise NotImplementedError("Config file saving not yet implemented")


# Module-level convenience accessor
config = Config.get()
