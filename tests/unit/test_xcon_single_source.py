"""Phase XXII T04 — xcon 单一内容源（D6，P2-3，Q6）。

Covers:
  * 全仓 ``_build_xcon_content`` 仅 1 处定义（xcon_writer.py）
  * ``OutputManager.write_xcon`` 无 content_override → ValueError
  * xcon_writer 为唯一内容源（XconWriter._build_xcon_content 存在）
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


class TestXconSingleSource:
    def test_build_xcon_content_single_definition(self):
        """全仓 `def _build_xcon_content` 仅 1 处定义。"""
        hits: list[str] = []
        for py in sorted((_ROOT / "cis2hdl").rglob("*.py")):
            text = py.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"def\s+_build_xcon_content\s*\(", text):
                hits.append(f"{py.relative_to(_ROOT)}:{m.start()}")
        assert len(hits) == 1, (
            f"expected exactly 1 definition, got {len(hits)}: {hits}"
        )
        assert "xcon_writer" in hits[0], f"single source must be xcon_writer: {hits}"

    def test_write_xcon_requires_override(self, tmp_path: Path):
        """write_xcon 无 content_override → ValueError。"""
        from cis2hdl.core.writer.output_manager import OutputManager

        mgr = OutputManager(project_name="T", output_root=tmp_path)
        mgr.setup_directory_structure()
        with pytest.raises(ValueError, match="single content source"):
            mgr.write_xcon()

    def test_write_xcon_override_path_writes(self, tmp_path: Path):
        """带 content_override 正常写盘（字节级 = 传入内容）。"""
        from cis2hdl.core.writer.output_manager import OutputManager

        mgr = OutputManager(project_name="T", output_root=tmp_path)
        mgr.setup_directory_structure()
        content = "<schema>\n<design/>\n</schema>\n"
        path = mgr.write_xcon(content_override=content)
        assert path.read_text(encoding="utf-8") == content
