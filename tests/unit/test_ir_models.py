"""Unit tests for IR core data models — Phase I-A."""

import pytest

from cis2hdl.core.ir.component import (
    ComponentDef,
    ComponentInstanceIR,
    ElectricalType,
    PinDef,
)
from cis2hdl.core.ir.design import (
    DesignIR,
    NetCategory,
    NetConnection,
    NetIR,
    PageIR,
)
from cis2hdl.core.ir.match import MatchResult, MatchStrategy

pytestmark = pytest.mark.unit


class TestPinDef:
    def test_basic(self) -> None:
        pin = PinDef(number="1", name="VCC", type=ElectricalType.POWER)
        assert pin.number == "1"
        assert pin.name == "VCC"
        assert pin.type == ElectricalType.POWER
        assert pin.is_power is True  # auto-detected from POWER type

    def test_default_values(self) -> None:
        pin = PinDef(number="5")
        assert pin.name == ""
        assert pin.type == ElectricalType.PASSIVE
        assert pin.is_power is False


class TestComponentDef:
    def test_basic(self) -> None:
        pins = [
            PinDef(number="1", name="A"),
            PinDef(number="2", name="B"),
        ]
        comp = ComponentDef(
            library_id="RES_0603_10K",
            part_name="RES_0603_10K",
            footprint="0603",
            value="10K",
            pins=pins,
        )
        assert comp.library_id == "RES_0603_10K"
        assert comp.pin_count == 2
        assert comp.fingerprint == "0603|10K|2"

    def test_fingerprint_differentiation(self) -> None:
        r10k = ComponentDef(
            library_id="R1", part_name="R", footprint="0603", value="10K",
            pins=[PinDef(number="1"), PinDef(number="2")],
        )
        r1k = ComponentDef(
            library_id="R2", part_name="R", footprint="0603", value="1K",
            pins=[PinDef(number="1"), PinDef(number="2")],
        )
        assert r10k.fingerprint != r1k.fingerprint

    def test_sections_default(self) -> None:
        comp = ComponentDef(
            library_id="IC", part_name="IC", footprint="SOIC-8",
            pins=[PinDef(number=str(i)) for i in range(1, 9)],
        )
        assert comp.sections == 1
        assert comp.pin_count == 8


class TestDesignIR:
    def test_minimal(self) -> None:
        design = DesignIR(project_name="test")
        assert design.project_name == "test"
        assert design.pages == []
        assert design.all_instances == []
        assert design.all_nets == []

    def test_with_page(self) -> None:
        net = NetIR(name="N1", connections=[NetConnection(refdes="R1", pin_number="1")])
        inst = ComponentInstanceIR(refdes="R1", library_id="RES", loc_x=100, loc_y=200)
        page = PageIR(page_id="1.1", instances=[inst], nets=[net])
        design = DesignIR(project_name="test", pages=[page])
        assert len(design.all_instances) == 1
        assert design.all_instances[0].refdes == "R1"
        assert design.all_instances[0].loc_x == 100
        assert len(design.all_nets) == 1
        assert design.total_pins == 1


class TestNetCategory:
    def test_ground_classification(self) -> None:
        assert NetCategory.GROUND == NetCategory.GROUND
        ground_names = ["GND", "VSS", "AGND", "DGND"]
        for name in ground_names:
            assert isinstance(name, str)

    def test_power_classification(self) -> None:
        assert NetCategory.POWER == NetCategory.POWER


class TestMatchResult:
    def test_no_match(self) -> None:
        result = MatchResult.no_match("CIS_R1")
        assert result.confidence == 0.0
        assert result.strategy == MatchStrategy.MANUAL
        assert result.source_library_id == "CIS_R1"

    def test_exact_match(self) -> None:
        result = MatchResult(
            confidence=1.0,
            strategy=MatchStrategy.EXACT,
            source_library_id="CIS_R1",
            target_library_id="HDL_R1",
        )
        assert result.confidence == 1.0
        assert result.strategy == MatchStrategy.EXACT
