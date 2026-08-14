"""Unit tests for DSN OLE/CFB Reader components."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from cis2hdl.core.parser.dsn.ole_reader import OleReader, CFBError


# ── OleReader Tests ──────────────────────────────────────────────────────


class TestOleReader:
    """OleReader CFB 容器测试。"""

    def test_valid_ole_magic(self, real_dsn_path: Path) -> None:
        """测试有效 OLE 文件打开。
        
        使用真实 .dsn 测试文件（需存在）。
        """
        if not real_dsn_path.exists():
            pytest.skip(f"Test file not found: {real_dsn_path}")
        ole = OleReader(real_dsn_path)
        assert ole.sector_size > 0

    def test_invalid_magic_raises(self) -> None:
        """测试无效 OLE 魔数抛出异常。"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dsn", delete=False) as f:
            f.write(b"NOT A VALID OLE FILE!!!!!")
            tmp_path = f.name
        try:
            with pytest.raises(CFBError, match="Invalid OLE magic"):
                OleReader(Path(tmp_path))
        finally:
            Path(tmp_path).unlink()

    def test_list_entries_from_real_dsn(self, real_dsn_path: Path) -> None:
        """测试从真实 DSN 列出条目。"""
        if not real_dsn_path.exists():
            pytest.skip(f"Test file not found: {real_dsn_path}")
        ole = OleReader(real_dsn_path)
        entries = ole.list_all_entries()
        assert len(entries) > 0
        # Should have page entries
        pages = [e for e in entries if "Pages" in e.full_path]
        assert len(pages) > 0, f"No page entries found in {real_dsn_path}"
