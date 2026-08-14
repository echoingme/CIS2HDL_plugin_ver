"""Regression tests for Cadence DEHDL output format compatibility fixes.

Tests cover:
- .dcf file generation (P0 fix)
- master.tag file list format (P0 fix)
- page.map page mapping format (P0 fix)
- generate_all_cell_files() integration (P1 fix)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from cis2hdl.core.writer.output_manager import OutputManager


class TestDCFWriter:
    """Test .dcf design constraint file generation."""

    @pytest.fixture
    def output_mgr(self, tmp_path: Path) -> OutputManager:
        mgr = OutputManager(project_name="test_project", output_root=tmp_path)
        mgr.setup_directory_structure()
        return mgr

    def test_write_dcf_creates_file(self, output_mgr: OutputManager) -> None:
        """DCF file should be created at the correct path."""
        dcf_path = output_mgr.write_dcf()
        assert dcf_path.exists()
        assert dcf_path.suffix == ".dcf"
        assert dcf_path.parent.name == "sch_1"

    def test_dcf_contains_version(self, output_mgr: OutputManager) -> None:
        """DCF file must contain version 16.6."""
        dcf_path = output_mgr.write_dcf()
        content = dcf_path.read_text(encoding="utf-8")
        assert "( 16.6 )" in content

    def test_dcf_contains_cell_name(self, output_mgr: OutputManager) -> None:
        """DCF file must reference the cell name."""
        dcf_path = output_mgr.write_dcf()
        content = dcf_path.read_text(encoding="utf-8")
        assert output_mgr.cell_name in content

    def test_dcf_starts_with_constraint_file(self, output_mgr: OutputManager) -> None:
        """DCF file must start with ConstraintFile S-expression."""
        dcf_path = output_mgr.write_dcf()
        content = dcf_path.read_text(encoding="utf-8")
        assert content.startswith('( ConstraintFile ')

    def test_dcf_ends_with_close_paren(self, output_mgr: OutputManager) -> None:
        """DCF file must end with closing parenthesis."""
        dcf_path = output_mgr.write_dcf()
        content = dcf_path.read_text(encoding="utf-8")
        assert content.rstrip().endswith(')')

    def test_dcf_s_expr_balanced(self, output_mgr: OutputManager) -> None:
        """DCF file S-expression parentheses must be balanced."""
        dcf_path = output_mgr.write_dcf()
        content = dcf_path.read_text(encoding="utf-8")
        open_count = content.count('(')
        close_count = content.count(')')
        assert open_count == close_count, (
            f"Unbalanced ({open_count} open vs {close_count} close)"
        )


class TestMasterTagFormat:
    """Test master.tag file list format."""

    @pytest.fixture
    def output_mgr(self, tmp_path: Path) -> OutputManager:
        mgr = OutputManager(project_name="test_project", output_root=tmp_path)
        mgr.setup_directory_structure()
        return mgr

    def test_master_tag_contains_file_list(self, output_mgr: OutputManager) -> None:
        """master.tag must contain .csa, .xcon, .dcf file entries."""
        files = output_mgr.write_placeholder_files()
        tag_path = output_mgr.sch_dir / "master.tag"
        content = tag_path.read_text(encoding="utf-8")

        cell = output_mgr.cell_name
        assert "page1.csa" in content
        assert f"{cell}.xcon" in content
        assert f"{cell}.dcf" in content

    def test_master_tag_no_longer_cds_system(self, output_mgr: OutputManager) -> None:
        """master.tag must NOT contain the old 'CDS_SYSTEM' placeholder."""
        files = output_mgr.write_placeholder_files()
        tag_path = output_mgr.sch_dir / "master.tag"
        content = tag_path.read_text(encoding="utf-8")
        assert "CDS_SYSTEM" not in content

    def test_master_tag_three_lines(self, output_mgr: OutputManager) -> None:
        """master.tag lists .csa, .xcon, .dcf (no .cpc — Phase XI C.4b).

        Real 04p4 master.tag omits .cpc files: pageN.csa per page, then
        <cell>.xcon and <cell>.dcf.
        """
        files = output_mgr.write_placeholder_files()
        tag_path = output_mgr.sch_dir / "master.tag"
        lines = tag_path.read_text(encoding="utf-8").strip().splitlines()
        # 1 page = page1.csa + cell.xcon + cell.dcf = 3 lines (no .cpc)
        assert len(lines) == 3
        assert "page1.cpc" not in "\n".join(lines)


class TestPageMapFormat:
    """Test page.map page mapping format."""

    @pytest.fixture
    def output_mgr(self, tmp_path: Path) -> OutputManager:
        mgr = OutputManager(project_name="test_project", output_root=tmp_path)
        mgr.setup_directory_structure()
        return mgr

    def test_page_map_format_default(self, output_mgr: OutputManager) -> None:
        """page.map default format: '1 1 DDR3'."""
        files = output_mgr.write_placeholder_files()
        map_path = output_mgr.sch_dir / "page.map"
        content = map_path.read_text(encoding="utf-8").strip()
        assert content == "1 1 DDR3"

    def test_page_map_with_custom_name(self, output_mgr: OutputManager) -> None:
        """page.map should accept custom page name."""
        files = output_mgr.write_placeholder_files(page_name="POWER")
        map_path = output_mgr.sch_dir / "page.map"
        content = map_path.read_text(encoding="utf-8").strip()
        assert "POWER" in content

    def test_page_map_with_multiple_pages(self, output_mgr: OutputManager) -> None:
        """page.map should reflect actual page count."""
        files = output_mgr.write_placeholder_files(num_pages=3)
        map_path = output_mgr.sch_dir / "page.map"
        content = map_path.read_text(encoding="utf-8").strip()
        assert content.startswith("1 3 ")

    def test_page_map_not_empty(self, output_mgr: OutputManager) -> None:
        """page.map must NOT be empty."""
        files = output_mgr.write_placeholder_files()
        map_path = output_mgr.sch_dir / "page.map"
        content = map_path.read_text(encoding="utf-8").strip()
        assert len(content) > 0


class TestGenerateAllCellFiles:
    """Test generate_all_cell_files() integration including .dcf."""

    @pytest.fixture
    def output_mgr(self, tmp_path: Path) -> OutputManager:
        mgr = OutputManager(project_name="test_project", output_root=tmp_path)
        mgr.setup_directory_structure()
        return mgr

    def test_generates_dcf(self, output_mgr: OutputManager) -> None:
        """generate_all_cell_files() must include .dcf file."""
        files = output_mgr.generate_all_cell_files()
        dcf_paths = [f for f in files if f.suffix == ".dcf"]
        assert len(dcf_paths) == 1
        assert dcf_paths[0].exists()

    def test_generates_con_file(self, output_mgr: OutputManager) -> None:
        """.con file should still be generated."""
        files = output_mgr.generate_all_cell_files()
        con_paths = [f for f in files if f.suffix == ".con"]
        assert len(con_paths) == 1

    def test_generates_module_order(self, output_mgr: OutputManager) -> None:
        """module_order.dat should be generated."""
        files = output_mgr.generate_all_cell_files()
        mo_paths = [f for f in files if f.name == "module_order.dat"]
        assert len(mo_paths) == 1

    def test_generates_master_tag(self, output_mgr: OutputManager) -> None:
        """master.tag should be generated via placeholder files."""
        files = output_mgr.generate_all_cell_files()
        tag_paths = [f for f in files if f.name == "master.tag"]
        assert len(tag_paths) == 1

    def test_generates_page_map(self, output_mgr: OutputManager) -> None:
        """page.map should be generated via placeholder files."""
        files = output_mgr.generate_all_cell_files()
        map_paths = [f for f in files if f.name == "page.map"]
        assert len(map_paths) == 1

    def test_all_files_exist_on_disk(self, output_mgr: OutputManager) -> None:
        """All generated files must actually exist on disk."""
        files = output_mgr.generate_all_cell_files()
        for fpath in files:
            assert fpath.exists(), f"Missing: {fpath}"

    def test_total_file_count(self, output_mgr: OutputManager) -> None:
        """Should generate 6 files: .con, .dcf, module_order, master.tag, page.map, .cpc.

        Phase XXII D6/Q6：.xcon 不再由 output_manager 生成（XconWriter 唯一
        内容源）—— 文件数 7→6。
        """
        files = output_mgr.generate_all_cell_files()
        assert len(files) == 6, (
            f"Expected 6 files, got {len(files)}: {[f.name for f in files]}"
        )
        # .xcon 由 XconWriter 产出，不在本方法返回清单内。
        assert not any(f.suffix == ".xcon" for f in files)

    def test_write_xcon_requires_content_override(self, output_mgr: OutputManager) -> None:
        """D6：write_xcon 无 content_override → ValueError（单一内容源）。"""
        import pytest

        with pytest.raises(ValueError, match="single content source"):
            output_mgr.write_xcon()

    def test_write_xcon_with_override_writes(self, output_mgr: OutputManager) -> None:
        """D6：带 content_override 正常写盘（XconWriter 路径）。"""
        content = '<schema xmlns="http://www.cadence.com/spb/csschema">\n</schema>\n'
        path = output_mgr.write_xcon(content_override=content)
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith("<schema")


class TestCPMVersionCompatibility:
    """Test .cpm file format is Cadence 16.6 compatible."""

    @pytest.fixture
    def output_mgr(self, tmp_path: Path) -> OutputManager:
        mgr = OutputManager(project_name="test_project", output_root=tmp_path)
        mgr.setup_directory_structure()
        return mgr

    def test_cpm_contains_version_16_6(self, output_mgr: OutputManager) -> None:
        """CPM file must specify cpm_version '16.6'."""
        cpm_path = output_mgr.write_cpm()
        content = cpm_path.read_text(encoding="utf-8")
        assert "cpm_version '16.6'" in content

    def test_cpm_uses_start_global_format(self, output_mgr: OutputManager) -> None:
        """CPM must use START_GLOBAL/END_GLOBAL section format.

        The old format used ``START_DESIGN`` / ``END_DESIGN`` sections
        (without ``cpm_version``), which triggered UPREV in Cadence.
        The new format uses ``START_GLOBAL`` / ``END_GLOBAL`` with
        ``cpm_version '16.6'``.
        """
        cpm_path = output_mgr.write_cpm()
        content = cpm_path.read_text(encoding="utf-8")

        # Must have START_GLOBAL
        assert "START_GLOBAL" in content

        # START_DESIGNSYNC is expected; START_DESIGN (standalone) is NOT.
        # Check that the only "START_" blocks are the allowed ones.
        start_blocks = [
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("START_")
        ]
        allowed = {"START_GLOBAL", "START_CONCEPTHDL", "START_PKGRXL",
                    "START_DESIGNSYNC", "START_CONSTRAINT_MGR"}
        for block in start_blocks:
            assert block in allowed, (
                f"Unexpected CPM section: {block}"
            )

    def test_cpm_has_concepthdl_section(self, output_mgr: OutputManager) -> None:
        """CPM must include START_CONCEPTHDL section."""
        cpm_path = output_mgr.write_cpm()
        content = cpm_path.read_text(encoding="utf-8")
        assert "START_CONCEPTHDL" in content
        assert "END_CONCEPTHDL" in content
