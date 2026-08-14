"""Unit tests for CPM Writer and CDSLib Writer."""

import pytest

from cis2hdl.core.ir.design import DesignIR
from cis2hdl.core.writer.cpm_writer import CPMWriter
from cis2hdl.core.writer.cdslib_writer import CDSLibWriter


@pytest.mark.unit
class TestCPMWriter:
    def test_generate_writes_valid_cpm(self, sample_design: DesignIR,
                                        temp_output_dir) -> None:
        writer = CPMWriter()
        paths = writer.write(sample_design, temp_output_dir)
        assert len(paths) == 1
        assert paths[0].suffix == ".cpm"
        content = paths[0].read_text()
        assert "START_GLOBAL" in content
        assert "END_GLOBAL" in content
        assert "design_name" in content
        assert "design_library" in content
        assert "cpm_version" in content
        assert "session_name" in content


@pytest.mark.unit
class TestCDSLibWriter:
    def test_generate_writes_valid_cdslib(self, sample_design: DesignIR,
                                           temp_output_dir) -> None:
        writer = CDSLibWriter()
        paths = writer.write(sample_design, temp_output_dir)
        assert len(paths) == 1
        content = paths[0].read_text()
        assert "DEFINE" in content
        assert "worklib" in content
        assert "INCLUDE $CONCEPT_INST_DIR" in content
        assert "hdl_lib" in content
