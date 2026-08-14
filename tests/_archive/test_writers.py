"""Unit tests for Writer layer — Phase I-A."""

import tempfile
from pathlib import Path

from cis2hdl.core.ir.component import ComponentInstanceIR, ComponentDef, PinDef, ElectricalType
from cis2hdl.core.ir.design import DesignIR, NetIR, NetConnection, PageIR
from cis2hdl.core.db.component_db import ComponentDB
from cis2hdl.core.writer.cpm_writer import CPMWriter
from cis2hdl.core.writer.cdslib_writer import CDSLibWriter
from cis2hdl.core.writer.sch_writer import SCHWriter


def _make_sample_design() -> DesignIR:
    """Create a minimal test design with 2 resistors on 1 page."""
    r1 = ComponentInstanceIR(refdes="R1", library_id="RES_0603_10K", loc_x=100, loc_y=100)
    r2 = ComponentInstanceIR(refdes="R2", library_id="RES_0603_10K", loc_x=300, loc_y=100)
    net = NetIR(name="N00001", connections=[
        NetConnection(refdes="R1", pin_number="1"),
        NetConnection(refdes="R2", pin_number="2"),
    ])
    page = PageIR(page_id="1.1", page_name="MAIN", instances=[r1, r2], nets=[net])
    return DesignIR(project_name="test_design", pages=[page])


class TestCPMWriter:
    def test_generate(self) -> None:
        writer = CPMWriter()
        design = _make_sample_design()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            paths = writer.write(design, out)
            assert len(paths) == 1
            assert paths[0].suffix == ".cpm"
            content = paths[0].read_text()
            assert "START_GLOBAL" in content
            assert "END_GLOBAL" in content
            assert "design_name" in content
            assert "cpm_version" in content
            assert "session_name" in content


class TestCDSLibWriter:
    def test_generate(self) -> None:
        writer = CDSLibWriter()
        design = _make_sample_design()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            paths = writer.write(design, out)
            assert len(paths) == 1
            content = paths[0].read_text()
            assert "DEFINE" in content
            assert "worklib" in content
            assert "INCLUDE $CONCEPT_INST_DIR" in content


class TestSCHWriter:
    def test_generate(self) -> None:
        writer = SCHWriter()
        design = _make_sample_design()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            paths = writer.write(design.pages[0], out)
            assert len(paths) == 1
            content = (out / "top.sch.1.1").read_text()
            assert "BEGIN SCHEMATIC" in content
            assert "R1" in content
            assert "R2" in content
            assert "N00001" in content
            assert "SIGNAL N00001" in content

    def test_empty_page(self) -> None:
        writer = SCHWriter()
        page = PageIR(page_id="2.1")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            paths = writer.write(page, out)
            assert len(paths) == 1
            content = (out / "top.sch.2.1").read_text()
            assert "BEGIN SCHEMATIC" in content

    def test_auto_layout(self) -> None:
        """Instances wrap to next row when exceeding usable width."""
        writer = SCHWriter()
        insts = [ComponentInstanceIR(refdes=f"R{i}", library_id="R",
                                      loc_x=0, loc_y=0) for i in range(1, 4)]
        page = PageIR(page_id="1.1", instances=insts, width=600)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            writer.write(page, out)
            content = (out / "top.sch.1.1").read_text()
            assert "R1" in content
            assert "R3" in content
            # R1 at (100,100), R2 at (300,100), R3 wraps to (100,300)
            # because max_x = 600-200 = 400, so x=500 > 400 triggers wrap
            assert "BEGIN INSTANCE R1 100 100" in content
            assert "BEGIN INSTANCE R2 300 100" in content
            assert "BEGIN INSTANCE R3 100 300" in content

    def test_dsn_coordinate_injection(self) -> None:
        """When instances have real DSN coordinates, they are injected directly."""
        writer = SCHWriter(use_dsn_coordinates=True)
        insts = [
            ComponentInstanceIR(refdes="U1", library_id="IC1", loc_x=1250, loc_y=3400),
            ComponentInstanceIR(refdes="R1", library_id="RES", loc_x=600, loc_y=1200),
        ]
        page = PageIR(page_id="1.1", instances=insts)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            writer.write(page, out)
            content = (out / "top.sch.1.1").read_text()
            assert "BEGIN INSTANCE U1 1250 3400" in content
            assert "BEGIN INSTANCE R1 600 1200" in content

    def test_dsn_coordinates_disabled_falls_back(self) -> None:
        """When use_dsn_coordinates=False, falls back to auto-layout even with real coords."""
        writer = SCHWriter(use_dsn_coordinates=False)
        insts = [
            ComponentInstanceIR(refdes="U1", library_id="IC1", loc_x=1250, loc_y=3400),
        ]
        page = PageIR(page_id="1.1", instances=insts)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            writer.write(page, out)
            content = (out / "top.sch.1.1").read_text()
            # Should use auto-layout start position, not 1250/3400
            assert "BEGIN INSTANCE U1 100 100" in content

    def test_wire_segment_output(self) -> None:
        """DSN wire segments are written to .sch file."""
        from cis2hdl.core.ir.design import WireSegment

        writer = SCHWriter()
        inst = ComponentInstanceIR(refdes="R1", library_id="RES", loc_x=100, loc_y=100)
        wire = WireSegment(start_x=100, start_y=100, end_x=300, end_y=100, net_name="NET_001")
        page = PageIR(page_id="1.1", instances=[inst], wires=[wire])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            writer.write(page, out)
            content = (out / "top.sch.1.1").read_text()
            assert "BEGIN WIRE 100 100 300 100" in content
            assert "NET_001" in content or "unnamed" in content
