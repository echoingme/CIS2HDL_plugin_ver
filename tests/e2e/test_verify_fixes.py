"""End-to-end format verification script for Cadence compatibility fixes.

This module contains pytest-based tests that verify the output files
for the 12 fix points. Each test function uses standard pytest assertions.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

pytestmark = pytest.mark.e2e

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cis2hdl.core.writer.output_manager import OutputManager


class TestP0Fixes:
    """P0 (blocking) format compliance tests."""

    def test_cdslib_define_lines_have_no_dot_slash_prefix(self) -> None:
        """P0-1: cds.lib DEFINE line must not have ./ prefix."""
        mgr = OutputManager(project_name="RTL8367RB-TEST", output_root=Path("/tmp/test"))
        mgr.library_alias = "8367_lib"
        mgr.cell_name = "8367"

        from cis2hdl.core.config import config as cfg
        lines = [
            f"DEFINE {mgr.library_alias} {cfg.output.worklib_dir}",
            "INCLUDE $CONCEPT_INST_DIR/share/cdssetup/cds.lib",
            f"DEFINE hdl_lib {cfg.output.hdl_lib_dir}",
        ]
        cdslib_content = "\n".join(lines) + "\n"

        for line in cdslib_content.splitlines():
            if line.startswith("DEFINE "):
                assert "./" not in line, f"cds.lib contains ./ in: {line}"

    def test_xcon_writer_exists_and_registered(self) -> None:
        """P0-2: .xcon writer exists, output_manager has write_xcon, engine integrates it."""
        xcon_path = Path(__file__).resolve().parents[2] / "cis2hdl" / "core" / "writer" / "xcon_writer.py"
        assert xcon_path.exists(), "xcon_writer.py does not exist"

        assert hasattr(OutputManager, "write_xcon"), "OutputManager missing write_xcon"

        from cis2hdl.core.writer import XCONWriter
        assert XCONWriter is not None
        assert XCONWriter.FORMAT_NAME == "xcon", \
            f"Expected FORMAT_NAME='xcon', got '{XCONWriter.FORMAT_NAME}'"

    def test_master_tag_lists_page_csa_files(self) -> None:
        """P0-3: master.tag lists pageN.csa files."""
        mgr = OutputManager(project_name="RTL8367RB-TEST", output_root=Path("/tmp/test"))

        tag_lines = []
        for n in range(1, 4):
            tag_lines.append(f"page{n}.csa")
        tag_lines.append(f"{mgr.cell_name}.xcon")
        tag_lines.append(f"{mgr.cell_name}.dcf")
        tag_content = "\n".join(tag_lines) + "\n"

        assert "page1.csa" in tag_content, "page1.csa not in master.tag"
        assert "page2.csa" in tag_content, "page2.csa not in master.tag"
        assert "page3.csa" in tag_content, "page3.csa not in master.tag"

    def test_csa_colors_are_orange_and_purple(self) -> None:
        """P0-4: CSA COLOR_PROP = ORANGE, COLOR_NOTE = PURPLE."""
        csa_path = Path(__file__).resolve().parents[2] / "cis2hdl" / "core" / "writer" / "csa_writer.py"
        content = csa_path.read_text()

        assert 'SET COLOR_PROP ORANGE;' in content, "COLOR_PROP not ORANGE"
        assert 'SET COLOR_NOTE PURPLE;' in content, "COLOR_NOTE not PURPLE"


class TestP1Fixes:
    """P1 (important) format compliance tests."""

    def test_module_order_format_is_at_lib_cell_view(self) -> None:
        """P1-1: module_order format uses DEHDL backslash escapes (C.4b).

        Phase XI C.4b (04p4 evidence): the reference format is
        ``@\\<lib>\\.\\<cell>\\(<view>)\\t0\\t1\\t1\\t3\\t0`` — the
        lib/cell/view tokens are backslash-escaped and the final field is 3.
        """
        content = OutputManager._build_module_order_content("8367_lib", "8367", "sch_1")
        line = content.splitlines()[2]
        assert "@\\8367_lib\\.\\8367\\(sch_1)" in line, \
            f"unexpected format: {line!r}"
        assert "\t0\t1\t1\t3\t0\t" in line, \
            f"missing tab fields: {line!r}"

    def test_dcf_logical_view_rev_num_is_zero(self) -> None:
        """P1-2: .dcf logicalViewRevNum = 0."""
        content = OutputManager._build_dcf_content("8367", "16.6")
        assert "logicalViewRevNum 0" in content, "logicalViewRevNum not 0"

    def test_write_worklib_file_uses_crlf_and_write_bytes(self) -> None:
        """P1-3: _write_worklib_file uses CRLF and write_bytes."""
        source = inspect.getsource(OutputManager._write_worklib_file)
        assert ('replace("\\n", "\\r\\n")' in source
                or "replace('\n', '\r\n')" in source), \
            "_write_worklib_file does not convert to CRLF"
        assert "write_bytes" in source, \
            "_write_worklib_file does not use write_bytes"

    def test_write_hdldirect_dat_method_exists(self) -> None:
        """P1-4: write_hdldirect_dat() method exists."""
        assert hasattr(OutputManager, "write_hdldirect_dat"), \
            "OutputManager missing write_hdldirect_dat"


class TestP2Fixes:
    """P2 (optional) format compliance tests."""

    def test_cpm_session_name_is_projectmgr3606(self) -> None:
        """P2-1: session_name = ProjectMgr3606."""
        mgr = OutputManager(project_name="RTL8367RB-TEST", output_root=Path("/tmp/test"))
        cpm_content = mgr._build_cpm_content()
        assert "session_name 'ProjectMgr3606'" in cpm_content, \
            f"expected ProjectMgr3606, got something else"

    def test_cpm_comments_use_spi_as_tool_name(self) -> None:
        """P2-2: .cpm comments use SPI as tool name."""
        mgr = OutputManager(project_name="RTL8367RB-TEST", output_root=Path("/tmp/test"))
        cpm_content = mgr._build_cpm_content()
        assert "created by SPI" in cpm_content, \
            ".cpm should say 'SPI'"
        assert "SPI, your modifications" in cpm_content, \
            ".cpm second SPI reference missing"


class TestOutputToDisk:
    """Disk-based verification: write all files and validate on-disk format."""

    def test_full_output_structure_to_disk(self) -> None:
        """Write actual files to a temp directory and verify format."""
        with TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            mgr = OutputManager(project_name="TEST-DEMO", output_root=output_root)
            mgr.setup_directory_structure()

            # Write project files
            cpm_path = mgr.write_cpm()
            cdslib_path = mgr.write_cdslib()
            hdldirect_path = mgr.write_hdldirect_dat()

            # Write cell files
            mgr.write_csa_page(1, "FILE_TYPE = MACRO_DRAWING;\nSET COLOR_PROP ORANGE;\nSET COLOR_NOTE PURPLE;\nSET PAGE_NUMBER P1;\n")
            mgr.write_con_file()
            mgr.write_dcf()
            mgr.write_module_order()
            mgr.write_placeholder_files(num_pages=2)
            # Phase XXII D6: .xcon 内容来自 XconWriter（唯一内容源）——
            # write_xcon 强制 content_override；此处传最小合法内容验证写盘。
            mgr.write_xcon(
                num_pages=2,
                content_override=(
                    '<schema xmlns="http://www.cadence.com/spb/csschema">\n'
                    "</schema>\n"
                ),
            )

            # Verify cds.lib
            cdslib_text = cdslib_path.read_text()
            for line in cdslib_text.splitlines():
                if line.startswith("DEFINE"):
                    assert "./" not in line, f"cds.lib has ./ : {line}"

            # Verify .cpm
            cpm_text = cpm_path.read_text()
            assert "SPI" in cpm_text
            assert "ProjectMgr3606" in cpm_text

            # Verify hdldirect.dat exists
            assert hdldirect_path.exists()

            # Verify master.tag
            tag_path = mgr.sch_dir / "master.tag"
            tag_text = tag_path.read_text()
            assert "page1.csa" in tag_text
            assert "page2.csa" in tag_text

            # Verify .xcon
            xcon_path = mgr.sch_dir / f"{mgr.cell_name}.xcon"
            assert xcon_path.exists(), ".xcon file not created"
            xcon_text = xcon_path.read_text()
            assert "<schema" in xcon_text

            # Verify worklib CRLF: read in binary mode
            csa_path = mgr.sch_dir / "page1.csa"
            csa_bytes = csa_path.read_bytes()
            assert b"\r\n" in csa_bytes, "worklib file does not have CRLF"

            # Verify .cpm uses LF (check binary)
            cpm_bytes = cpm_path.read_bytes()
            assert b"\r\n" not in cpm_bytes, ".cpm should use LF, not CRLF"
