"""Unit tests for SCH Writer — .sch page file generation."""

import pytest

from cis2hdl.core.ir.component import ComponentInstanceIR
from cis2hdl.core.ir.design import PageIR, WireSegment
from cis2hdl.core.writer.sch_writer import SCHWriter


@pytest.mark.unit
class TestSCHWriter:
    def test_generate_writes_valid_sch_with_instances(
        self, sample_page: PageIR, temp_output_dir,
    ) -> None:
        """SCH writer produces a valid .sch file with expected content."""
        writer = SCHWriter()
        paths = writer.write(sample_page, temp_output_dir)
        assert len(paths) == 1
        content = (temp_output_dir / "top.sch.1.1").read_text()
        assert "BEGIN SCHEMATIC" in content
        assert "R1" in content
        assert "R2" in content
        assert "N00001" in content
        assert "SIGNAL N00001" in content

    def test_empty_page_produces_minimal_sch(self, temp_output_dir) -> None:
        """SCH writer handles pages with no instances."""
        writer = SCHWriter()
        page = PageIR(page_id="2.1")
        paths = writer.write(page, temp_output_dir)
        assert len(paths) == 1
        content = (temp_output_dir / "top.sch.2.1").read_text()
        assert "BEGIN SCHEMATIC" in content

    def test_auto_layout_wraps_instances_to_next_row(self, temp_output_dir) -> None:
        """Instances wrap to next row when exceeding usable width."""
        writer = SCHWriter()
        insts = [
            ComponentInstanceIR(refdes=f"R{i}", library_id="R", loc_x=0, loc_y=0)
            for i in range(1, 4)
        ]
        page = PageIR(page_id="1.1", instances=insts, width=600)
        writer.write(page, temp_output_dir)
        content = (temp_output_dir / "top.sch.1.1").read_text()
        assert "BEGIN INSTANCE R1 100 100" in content
        assert "BEGIN INSTANCE R2 300 100" in content
        assert "BEGIN INSTANCE R3 100 300" in content

    def test_dsn_coordinate_injection_uses_real_coords(self, temp_output_dir) -> None:
        """When instances have real DSN coordinates, they are injected directly."""
        writer = SCHWriter(use_dsn_coordinates=True)
        insts = [
            ComponentInstanceIR(refdes="U1", library_id="IC1", loc_x=1250, loc_y=3400),
            ComponentInstanceIR(refdes="R1", library_id="RES", loc_x=600, loc_y=1200),
        ]
        page = PageIR(page_id="1.1", instances=insts)
        writer.write(page, temp_output_dir)
        content = (temp_output_dir / "top.sch.1.1").read_text()
        assert "BEGIN INSTANCE U1 1250 3400" in content
        assert "BEGIN INSTANCE R1 600 1200" in content

    def test_coordinates_disabled_falls_back_to_autolayout(self, temp_output_dir) -> None:
        """When use_dsn_coordinates=False, auto-layout is used even with real coords."""
        writer = SCHWriter(use_dsn_coordinates=False)
        insts = [
            ComponentInstanceIR(refdes="U1", library_id="IC1", loc_x=1250, loc_y=3400),
        ]
        page = PageIR(page_id="1.1", instances=insts)
        writer.write(page, temp_output_dir)
        content = (temp_output_dir / "top.sch.1.1").read_text()
        assert "BEGIN INSTANCE U1 100 100" in content

    def test_wire_segments_are_written_correctly(self, temp_output_dir) -> None:
        """DSN wire segments are written to .sch with coordinates and net name."""
        writer = SCHWriter()
        inst = ComponentInstanceIR(refdes="R1", library_id="RES", loc_x=100, loc_y=100)
        wire = WireSegment(start_x=100, start_y=100, end_x=300, end_y=100, net_name="NET_001")
        page = PageIR(page_id="1.1", instances=[inst], wires=[wire])
        writer.write(page, temp_output_dir)
        content = (temp_output_dir / "top.sch.1.1").read_text()
        assert "BEGIN WIRE 100 100 300 100" in content
        assert "NET_001" in content or "unnamed" in content
