"""Phase XVIII R2 — temp_lib 库结构断言（validate_temp_lib_structure.py）。

Covers:
  * master.tag 分目录内容 = golden（sym_1→symbol.css / chips→chips.prt /
    entity→verilog.v）
  * entity 四文件齐全（pc.db / verilog.v / vhdl.vhd / vlog004u.sir）
  * cell 根目录无 master.tag
  * 目录名大写（与 FORCEADD 引用名一致）
"""

from __future__ import annotations

from pathlib import Path


def _structure():
    from cis2hdl.core.writer.validate_symbol_css import validate_temp_lib_structure

    return validate_temp_lib_structure


def _build_mock_lib(tmp_path: Path, cell: str = "U6_PH") -> Path:
    """写入一个真实的 mock temp_lib（走 MockIconLibrary 主流程）。"""
    from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

    lib = MockIconLibrary()
    lib.symbol_for(cell.rstrip("_PH"), 1, [("K18", "A0"), ("G20", "GND")])
    lib.write_to_temp_lib(tmp_path)
    return tmp_path


class TestMasterTagByRole:
    def test_master_tag_contents(self, tmp_path):
        root = _build_mock_lib(tmp_path)
        assert (root / "U6_PH" / "sym_1" / "master.tag").read_text().strip() == "symbol.css"
        assert (root / "U6_PH" / "chips" / "master.tag").read_text().strip() == "chips.prt"
        assert (root / "U6_PH" / "entity" / "master.tag").read_text().strip() == "verilog.v"

    def test_cell_root_no_master_tag(self, tmp_path):
        root = _build_mock_lib(tmp_path)
        assert not (root / "U6_PH" / "master.tag").exists()

    def test_structure_validator_passes(self, tmp_path):
        root = _build_mock_lib(tmp_path)
        assert _structure()(root) == []

    def test_wrong_master_tag_detected(self, tmp_path):
        root = _build_mock_lib(tmp_path)
        (root / "U6_PH" / "sym_1" / "master.tag").write_text("CDS_SYSTEM\n")
        errors = _structure()(root)
        assert any("master.tag" in e and "symbol.css" in e for e in errors)


class TestEntityFiles:
    def test_entity_four_files(self, tmp_path):
        root = _build_mock_lib(tmp_path)
        entity = root / "U6_PH" / "entity"
        for fname in ("master.tag", "pc.db", "verilog.v", "vhdl.vhd", "vlog004u.sir"):
            assert (entity / fname).exists(), f"entity/{fname} missing"

    def test_missing_entity_file_detected(self, tmp_path):
        root = _build_mock_lib(tmp_path)
        (root / "U6_PH" / "entity" / "vhdl.vhd").unlink()
        errors = _structure()(root)
        assert any("vhdl.vhd" in e for e in errors)


class TestDirUppercase:
    def test_lowercase_cell_detected(self, tmp_path):
        root = _build_mock_lib(tmp_path)
        # 伪造小写目录（Cadence Windows 大小写不敏感，但结构断言仍校验）。
        lower = root / "j4_ph"
        lower.mkdir()
        (lower / "sym_1").mkdir()
        (lower / "sym_1" / "symbol.css").write_text("", encoding="utf-8")
        (lower / "sym_1" / "master.tag").write_text("symbol.css\n")
        (lower / "chips").mkdir()
        (lower / "chips" / "chips.prt").write_text("", encoding="utf-8")
        (lower / "chips" / "master.tag").write_text("chips.prt\n")
        (lower / "entity").mkdir()
        (lower / "entity" / "master.tag").write_text("verilog.v\n")
        for f in ("pc.db", "verilog.v", "vhdl.vhd", "vlog004u.sir"):
            (lower / "entity" / f).write_text("", encoding="utf-8")
        errors = _structure()(root)
        assert any("uppercase" in e and "j4_ph" in e for e in errors)

    def test_missing_sym_dir_detected(self, tmp_path):
        root = _build_mock_lib(tmp_path)
        (root / "U6_PH" / "sym_1").rename(root / "U6_PH" / "sym_x")
        errors = _structure()(root)
        assert any("sym_1" in e for e in errors) or any("master.tag" in e for e in errors)


class TestWriteValidationWiring:
    def test_write_to_temp_lib_runs_validation(self, tmp_path):
        """R1/R2 校验在 write_to_temp_lib 写盘后自动执行（0 错才通过）。"""
        from cis2hdl.core.writer.mock_icon_lib import MockIconLibrary

        lib = MockIconLibrary(syntax_check=True, structure_check=True)
        lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "GND")])
        lib.write_to_temp_lib(tmp_path)  # 不应抛异常
        from cis2hdl.core.writer.validate_symbol_css import (
            validate_symbol_css, validate_temp_lib_structure,
        )
        css = (tmp_path / "U6_PH" / "sym_1" / "symbol.css").read_text()
        assert validate_symbol_css(css, "U6") == []
        assert validate_temp_lib_structure(tmp_path) == []
