"""Unit tests for DSN Parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from cis2hdl.core.parser.dsn.dsn_parser import DSNParser


@pytest.mark.unit
class TestDSNParser:
    def test_parser_registers_with_correct_format_name(self) -> None:
        """DSNParser exposes FORMAT_NAME='CIS_DSN' and .dsn extension."""
        parser = DSNParser()
        assert parser.FORMAT_NAME == "CIS_DSN"
        assert ".dsn" in parser.FILE_EXTENSIONS

    def test_parse_real_dsn_yields_design_with_pages(
        self, real_dsn_path: Path,
    ) -> None:
        """Parsing a real .dsn file produces a DesignIR with at least 1 page."""
        if not real_dsn_path.exists():
            pytest.skip(f"Test file not found: {real_dsn_path}")

        parser = DSNParser()
        design = parser.parse(real_dsn_path)
        assert design.project_name == "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0"
        assert len(design.pages) > 0
        total_inst = sum(len(p.instances) for p in design.pages)
        assert total_inst > 0, "Should have at least one instance"

    def test_parse_real_dsn_instances_have_coordinates(
        self, real_dsn_path: Path,
    ) -> None:
        """DSN-parsed instances include integer coordinates (at least one non-zero)."""
        if not real_dsn_path.exists():
            pytest.skip(f"Test file not found: {real_dsn_path}")

        parser = DSNParser()
        design = parser.parse(real_dsn_path)

        for page in design.pages:
            for inst in page.instances:
                assert isinstance(inst.loc_x, int)
                assert isinstance(inst.loc_y, int)
                if inst.loc_x != 0 or inst.loc_y != 0:
                    return  # Found coordinates — test passes

        pytest.fail("No instances with non-zero coordinates found")
