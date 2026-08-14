from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ElectricalType(str, Enum):
    """Unified electrical type enumeration — shared by all formats."""

    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    BIDIR = "BIDIR"
    POWER = "POWER"
    GROUND = "GROUND"
    PASSIVE = "PASSIVE"
    NC = "NC"
    TRI_STATE = "TRI_STATE"
    OPEN_COLLECTOR = "OPEN_COLLECTOR"


class PinDef(BaseModel):
    """Unified pin definition — all formats map here."""

    number: str
    name: str = ""
    type: ElectricalType = ElectricalType.PASSIVE
    is_power: bool = False  # Auto-set from type; use model_post_init
    position: Optional[tuple[float, float]] = None

    def model_post_init(self, __context: object) -> None:
        """Auto-detect is_power from POWER/GROUND types."""
        if self.type in (ElectricalType.POWER, ElectricalType.GROUND):
            object.__setattr__(self, "is_power", True)


class ComponentDef(BaseModel):
    """Unified component library definition.

    Represents a component *in the library*, not a schematic instance.
    ComponentInstanceIR references this definition.
    """

    library_id: str
    part_name: str

    category: str = ""
    phys_des_prefix: str = ""  # PHYS_DES_PREFIX from chips.prt (e.g. 'U', 'IC', 'XS')
    footprint: str = ""
    footprint_alt: list[str] = Field(default_factory=list)

    pins: list[PinDef] = Field(default_factory=list)
    pin_count: int = 0

    value: str = ""
    tolerance: str = ""
    mpn: str = ""
    description: str = ""

    bom_seq: str = ""
    sn_num: str = ""

    sections: int = 1
    section_pin_maps: dict[int, list[str]] = Field(default_factory=dict)

    symbols: list[dict] = Field(default_factory=list)

    source_format: str = ""
    source_file: str = ""

    #: Arbitrary extra data — used to store ptf_rows, cross_ref info, etc.
    extra_data: dict = Field(default_factory=dict)

    def model_post_init(self, __context: object) -> None:
        if not self.pin_count and self.pins:
            object.__setattr__(self, "pin_count", len(self.pins))

    @property
    def fingerprint(self) -> str:
        """Matching fingerprint: footprint + value + pin count."""
        return f"{self.footprint}|{self.value}|{self.pin_count}"


class ComponentInstanceIR(BaseModel):
    """Unified component instance — a component placed on a schematic page.

    Separate from ComponentDef: ComponentDef is the library definition,
    ComponentInstanceIR is a specific instance on a page.
    Multiple instances can reference the same ComponentDef.
    """

    refdes: str
    library_id: str
    section: int = 1

    loc_x: int = 0
    loc_y: int = 0
    rotation: int = 0
    #: Mirror flag — EDIF ``(orientation MY/MX/...)``; 0 = none,
    #: 1 = X-axis mirror, 2 = Y-axis mirror (P1-4).  Only meaningful
    #: when the placement transform carried an explicit orientation.
    mirror: int = 0

    value_override: str = ""
    properties: dict[str, str] = Field(default_factory=dict)
    pin_connections: dict[str, str] = Field(default_factory=dict)
    #: No-connect pins — pin names whose net is "NC" (P1-4).  These are
    #: stored so writers can emit NC flags / skip dangling pins.
    nc_pins: set[str] = Field(default_factory=set)
    extra_data: dict = Field(default_factory=dict)
