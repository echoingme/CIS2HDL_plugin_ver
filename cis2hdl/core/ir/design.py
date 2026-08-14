from __future__ import annotations

from enum import Enum
from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field

from ..db.component_db import ComponentDB
from .component import ComponentInstanceIR


class NetCategory(str, Enum):
    """ISCF 4-class network classification.

    Cadence internal exchange format (ISCF) classifies nets into:
        FLAT   — ordinary signal nets (BEGIN_NETS)
        GROUND — ground nets (BEGIN_GROUND)
        POWER  — power nets (BEGIN_POWER)
        BUS    — bus nets (BEGIN_BUSES)
    """

    FLAT = "FLAT"
    GROUND = "GROUND"
    POWER = "POWER"
    BUS = "BUS"


class NetConnection(BaseModel):
    """A single pin-to-net connection.

    Describes which pin of which component instance is connected to a net.
    """

    refdes: str
    pin_number: str


class NetIR(BaseModel):
    """Unified net definition using Cadence ISCF 4-class model."""

    name: str
    category: NetCategory = NetCategory.FLAT
    connections: list[NetConnection] = Field(default_factory=list)
    is_bus: bool = False
    bus_members: list[str] = Field(default_factory=list)
    # ── Phase XI P0-A1: wire geometry owned by this net ──────────────
    wires: list[WireSegment] = Field(default_factory=list)
    """Wire segments (EDIF figure WIRE polylines / DSN Wire) belonging to
    this net.  Populated by EDIFParser._parse_net (Phase XI P0-A1)."""

    @property
    def connection_signature(self) -> frozenset[str]:
        """返回网络连接的标准化签名（frozenset of "refdes.pin"）。

        用于跨来源网络拓扑比对——两个来源的 net 名称可能不同，
        但连接同一组器件/引脚时签名相同。
        """
        return frozenset(
            f"{conn.refdes}.{conn.pin_number}"
            for conn in self.connections
        )


class WireSegment(BaseModel):
    """A wire segment with coordinates.

    Supports both single-segment (DSN Wire §7.6, ``start_x/y`` + ``end_x/y``)
    and polyline (EDIF ``figure WIRE (path (pointList (pt x y) ...))``,
    ``points``) representations.  ``net_name`` carries the owning net when
    known (from DSN Net Name Table or EDIF net context); otherwise it is
    empty and the connection is established by coordinate overlap in the
    CSA/connectivity layer.

    Note: the historical docstring "EDIF does not contain coordinates" was
    incorrect — EDIF 2 0 0 ``(figure WIRE (path (pointList ...)))`` does
    contain full polyline coordinates (verified on HG5015-BE36_V10.EDF:
    2516 wire figures / 4257 points).  See Phase XI P0-A1.
    """

    start_x: int = 0
    start_y: int = 0
    end_x: int = 0
    end_y: int = 0
    net_name: str = ""
    # ── v1.2.0 (Phase XI P0-A1): polyline support ──────────────────
    points: list[tuple[int, int]] = Field(default_factory=list)
    """Full polyline vertex list from EDIF figure WIRE (ordered).  When
    non-empty, it is authoritative over start/end (which mirror the first
    and last points for backward compatibility)."""
    page_id: str = ""
    """Owning page id (e.g. '1.5'); used to route wires to the correct
    CSA page during generation."""

    def __init__(self, **data: object) -> None:
        if data.get("points"):
            pts = list(data["points"])  # type: ignore[arg-type]
            data["start_x"] = pts[0][0]
            data["start_y"] = pts[0][1]
            data["end_x"] = pts[-1][0]
            data["end_y"] = pts[-1][1]
        super().__init__(**data)


class PageIR(BaseModel):
    """A single schematic page (or hierarchical sheet)."""

    page_id: str = "1.1"
    page_name: str = ""
    width: int = 3520
    height: int = 2720
    instances: list[ComponentInstanceIR] = Field(default_factory=list)
    nets: list[NetIR] = Field(default_factory=list)
    wires: list[WireSegment] = Field(default_factory=list)
    ports: list[dict] = Field(default_factory=list)
    # ── Phase XI P0-A3: off-page / cross-page connectors ─────────────
    off_pages: list[dict] = Field(default_factory=list)
    """Off-page / cross-page connector references (EDIF portRef without
    instanceRef, or DSN OffPageConnector §7.8).  Each dict: ``{"name": ...,
    "net_name": ..., "x": ..., "y": ...}`` — used for cross-page net
    validation and CSA IOPORT generation (P0-C5)."""
    graphic_elements: list[dict] = Field(default_factory=list)
    """页面级图形元素（文本、线条、矩形等）。用于信息页（Cover_Page,
    Block_Diagram, Clock_Tree, Power_Tree）的 TitleBlock/GraphicInst 文本提取。"""

    def add_instance(self, inst: ComponentInstanceIR) -> None:
        self.instances.append(inst)

    def add_net(self, net: NetIR) -> None:
        self.nets.append(net)


class DesignIR(BaseModel):
    """Top-level design IR — the unified output of all parsers."""

    project_name: str = ""
    source_format: str = "CIS"
    pages: list[PageIR] = Field(default_factory=list)
    component_db: ComponentDB = Field(default_factory=lambda: _default_db())
    global_nets: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_page(self, page: PageIR) -> None:
        self.pages.append(page)

    def invalidate_caches(self) -> None:
        """Invalidate all cached_property values (Phase XII R1).

        ``cached_property`` results are stored in the instance ``__dict__``.
        Call this after mutating ``pages[].instances`` / ``pages[].nets``
        (e.g. after the ConversionEngine rebuilds page instances from the
        ComponentCatalog) so that ``all_instances`` / ``all_nets`` /
        ``instance_refdes_set`` are recomputed on next access.
        """
        for _key in ("all_instances", "all_nets", "instance_refdes_set"):
            self.__dict__.pop(_key, None)

    @cached_property
    def all_instances(self) -> list[ComponentInstanceIR]:
        result: list[ComponentInstanceIR] = []
        for page in self.pages:
            result.extend(page.instances)
        return result

    @cached_property
    def all_nets(self) -> list[NetIR]:
        result: list[NetIR] = []
        for page in self.pages:
            result.extend(page.nets)
        return result

    @property
    def total_pins(self) -> int:
        return sum(len(net.connections) for net in self.all_nets)

    @cached_property
    def instance_refdes_set(self) -> set[str]:
        """所有实例的 refdes 集合（跨页面）。"""
        result: set[str] = set()
        for page in self.pages:
            for inst in page.instances:
                result.add(inst.refdes)
        return result

    def instances_by_refdes(self) -> dict[str, 'ComponentInstanceIR']:
        """refdes → 对应 ComponentInstanceIR 的映射。

        如果多个页面有同名 refdes，返回遇到的第一个。
        """
        result: dict[str, 'ComponentInstanceIR'] = {}
        for page in self.pages:
            for inst in page.instances:
                if inst.refdes not in result:
                    result[inst.refdes] = inst
        return result

    def net_connection_map(self) -> dict[str, frozenset[str]]:
        """返回 net_name → connection_signature 的映射（跨页面）。"""
        result: dict[str, frozenset[str]] = {}
        for page in self.pages:
            for net in page.nets:
                result[net.name] = net.connection_signature
        return result

    def instances_by_type(self) -> dict[str, list['ComponentInstanceIR']]:
        """按器件类型分组返回实例列表。

        分类规则（基于 library_id 前缀）：
          - RES* → "Resistor"
          - CAP* → "Capacitor"
          - IND* / BEAD* / FERRITE* → "Inductor"
          - DIODE* / LED* / TVS* → "Diode"
          - XTAL* / CRYSTAL* / OSC* → "Crystal"
          - CONN* / J* / HEADER* → "Connector"
          - IC* / U* / RTL* → "IC"
          - 其他 → "Other"
        """
        import re

        categories: dict[str, list['ComponentInstanceIR']] = {}

        TYPE_RULES = [
            (r"^(RES|R_|RESISTOR)", "Resistor"),
            (r"^(CAP|C_|CAPACITOR|CAPSYM)", "Capacitor"),
            (r"^(IND|INDUCTOR|BEAD|FERRITE|L_)", "Inductor"),
            (r"^(DIODE|LED|TVS|D_|ZENER)", "Diode"),
            (r"^(XTAL|CRYSTAL|OSC|Y_)", "Crystal"),
            (r"^(CONN|J[A-Z]?$|HEADER|JACK|SOCKET)", "Connector"),
            (r"^(IC|U[A-Z]?$|RTL8|BCM|MTK|QCA|IPQ)", "IC"),
        ]

        for page in self.pages:
            for inst in page.instances:
                category = "Other"
                for pattern, cat in TYPE_RULES:
                    if re.match(pattern, inst.library_id.upper()):
                        category = cat
                        break
                categories.setdefault(category, []).append(inst)

        return categories


# ------------------------------------------------------------------
#  Rebuild Pydantic models to resolve forward references
#  (required by Pydantic v2 when 'from __future__ import annotations' is active)
# ------------------------------------------------------------------

PageIR.model_rebuild()
DesignIR.model_rebuild()


def _default_db() -> ComponentDB:
    from ..db.component_db import ComponentDB

    return ComponentDB()
