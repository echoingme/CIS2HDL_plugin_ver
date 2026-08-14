"""Unit tests for FileInventory and DSNInternalInventory components."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from cis2hdl.core.diagnostics.diagnostic_report import (
    Severity,
    FileState,
    FileStatus,
    DSNInternalInventory,
)
from cis2hdl.core.diagnostics.file_inventory import (
    FileInventory,
    DSNInternalInventoryBuilder,
)


# ── FileInventory Tests ──────────────────────────────────────────────────


class TestFileInventory:
    """FileInventory scanner tests."""

    def test_empty_input(self) -> None:
        """Empty file list produces empty inventory."""
        builder = FileInventory()
        inv = builder.scan([])
        assert len(inv.files) == 0

    def test_scan_edif(self) -> None:
        """Scan a valid EDIF file."""
        with tempfile.NamedTemporaryFile(suffix=".edf", delete=False, mode="w") as f:
            f.write("(edif test_project\n")
            tmp = Path(f.name)
        try:
            builder = FileInventory()
            inv = builder.scan([tmp])
            assert len(inv.files) == 1
            status = list(inv.files.values())[0]
            assert status.file_type == "EDF"
            assert status.state == FileState.FOUND_OK
        finally:
            tmp.unlink()

    def test_scan_missing_file(self) -> None:
        """Missing file gets MISSING state."""
        builder = FileInventory()
        inv = builder.scan([Path("/nonexistent/project.dsn")])
        assert len(inv.files) == 1
        status = list(inv.files.values())[0]
        assert status.state == FileState.MISSING

    def test_scan_empty_file(self) -> None:
        """Empty file gets CORRUPTED state."""
        with tempfile.NamedTemporaryFile(suffix=".dsn", delete=False) as f:
            tmp = Path(f.name)
        try:
            builder = FileInventory()
            inv = builder.scan([tmp])
            status = list(inv.files.values())[0]
            assert status.state == FileState.CORRUPTED
        finally:
            tmp.unlink()

    def test_scan_non_cfb_as_dsn(self) -> None:
        """Non-CFB file claimed as .dsn gets BAD_FORMAT."""
        with tempfile.NamedTemporaryFile(suffix=".dsn", delete=False, mode="wb") as f:
            f.write(b"NOT A VALID CFB FILE!!!")
            tmp = Path(f.name)
        try:
            builder = FileInventory()
            inv = builder.scan([tmp])
            status = list(inv.files.values())[0]
            assert status.file_type == "DSN"
            assert status.state == FileState.BAD_FORMAT
        finally:
            tmp.unlink()

    def test_generates_actions_for_missing_essentials(self) -> None:
        """Missing essential files generate action items."""
        builder = FileInventory()
        with tempfile.NamedTemporaryFile(suffix=".edf", delete=False, mode="w") as f:
            f.write("(edif test\n")
            tmp = Path(f.name)
        try:
            inv = builder.scan([tmp])
            # Should suggest providing DSN
            assert len(inv.actions) > 0
            actions_text = " ".join(str(a) for a in inv.actions)
            assert ".dsn" in actions_text or "DSN" in actions_text
        finally:
            tmp.unlink()


# ── DSNInternalInventory Tests ────────────────────────────────────────────


class TestDSNInternalInventory:
    """DSNInternalInventory tests."""

    def test_empty_inventory(self) -> None:
        """Default DSNInternalInventory has all False."""
        inv = DSNInternalInventory()
        assert inv.total_pages == 0
        assert inv.pages_parsed == 0
        assert inv.instances_parsed == 0
        assert inv.stream_integrity_score == 0.0

    def test_all_streams_present(self) -> None:
        """All streams present → score 1.0."""
        inv = DSNInternalInventory()
        inv.has_root = True
        inv.has_views = True
        inv.has_pages = True
        inv.has_cache = True
        inv.has_library = True
        inv.has_hierarchy = True
        assert inv.stream_integrity_score == 1.0

    def test_page_completeness(self) -> None:
        """Page completeness ratio is correct."""
        inv = DSNInternalInventory()
        inv.total_pages = 10
        inv.pages_parsed = 7
        assert inv.page_completeness == 0.7

    def test_summary_text(self) -> None:
        """Summary text contains key metrics."""
        inv = DSNInternalInventory(
            total_pages=3,
            pages_parsed=3,
            instances_parsed=42,
            cache_entries=5,
            strlst_entries=100,
            olb_references=["CAPSYM", "Discrete"],
        )
        text = inv.summary_text()
        assert "3/3 pages" in text
        assert "42 instances" in text
        assert "5 cache" in text

    def test_real_dsn_inventory(self, real_dsn_path: Path) -> None:
        """Build inventory from a real .dsn file."""
        if not real_dsn_path.exists():
            pytest.skip(f"Test file not found: {real_dsn_path}")

        builder = DSNInternalInventoryBuilder()
        inv = builder.build(real_dsn_path)
        assert inv.has_pages
        assert inv.total_pages > 0
        assert inv.pages_parsed > 0
        assert inv.stream_integrity_score > 0.0
