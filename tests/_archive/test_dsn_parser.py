"""Unit tests for Binary DSN Parser components (Phase I-B)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from cis2hdl.core.parser.dsn.binary_reader import BinaryReader, BinaryReadError
from cis2hdl.core.parser.dsn.ole_reader import OleReader, CFBError
from cis2hdl.core.parser.dsn.structures import (
    PREAMBLE_MAGIC,
    FutureDataList,
    read_preamble,
    parse_symbol_display_prop,
    parse_t0x10,
    parse_placed_instance,
    parse_wire,
    StructureType,
    SymbolDisplayProp,
    T0x10,
    PlacedInstance,
    WireSegment,
    GraphicInst,
)
from cis2hdl.core.parser.dsn.page_parser import parse_page, PageData
from cis2hdl.core.parser.dsn.dsn_parser import DSNParser
from cis2hdl.core.parser.cross_validator import (
    CrossValidator,
    ValidationReport,
    ValidationIssue,
)
from cis2hdl.core.parser.layout_mapper import LayoutMapper


# ── BinaryReader Tests ────────────────────────────────────────────────────


class TestBinaryReader:
    """BinaryReader 类型化二进制读取器测试。"""

    def test_uint_readers(self) -> None:
        """测试无符号整数读取。"""
        buf = struct.pack("<BHI", 0xA5, 0x1234, 0xDEADBEEF)
        reader = BinaryReader(buf)
        assert reader.read_uint8() == 0xA5
        assert reader.read_uint16() == 0x1234
        assert reader.read_uint32() == 0xDEADBEEF
        assert reader.is_eof()

    def test_int_readers(self) -> None:
        """测试有符号整数读取。"""
        buf = struct.pack("<bhi", -1, -2, -1000)
        reader = BinaryReader(buf)
        assert reader.read_int8() == -1
        assert reader.read_int16() == -2
        assert reader.read_int32() == -1000

    def test_read_bytes(self) -> None:
        """测试原始字节读取。"""
        buf = b"\x01\x02\x03\x04\x05"
        reader = BinaryReader(buf)
        assert reader.read_bytes(3) == b"\x01\x02\x03"
        assert reader.tell() == 3
        assert reader.read_bytes(2) == b"\x04\x05"

    def test_string_zero_term(self) -> None:
        """测试零结尾字符串读取。"""
        buf = b"HELLO\x00WORLD\x00"
        reader = BinaryReader(buf)
        assert reader.read_string_zero_term() == "HELLO"
        assert reader.read_string_zero_term() == "WORLD"

    def test_seek_and_skip(self) -> None:
        """测试位置操作。"""
        buf = b"ABCDEFGH"
        reader = BinaryReader(buf)
        reader.skip(3)
        assert reader.tell() == 3
        reader.seek(0)
        assert reader.read_uint8() == 0x41  # 'A'
        reader.skip(2)
        assert reader.read_uint8() == 0x44  # 'D'

    def test_peek_and_remaining(self) -> None:
        """测试预读和剩余字节。"""
        buf = b"HELLO"
        reader = BinaryReader(buf)
        assert reader.remaining() == 5
        assert reader.peek(2) == b"HE"
        assert reader.tell() == 0  # Position unchanged after peek
        reader.skip(5)
        assert reader.is_eof()

    def test_read_past_end_raises(self) -> None:
        """测试读取超出缓冲区抛出异常。"""
        buf = b"\x01\x02"
        reader = BinaryReader(buf)
        reader.read_uint8()
        reader.read_uint8()
        with pytest.raises(BinaryReadError):
            reader.read_uint8()

    def test_seek_out_of_range_raises(self) -> None:
        """测试越界 seek 抛出异常。"""
        reader = BinaryReader(b"HELLO")
        with pytest.raises(BinaryReadError):
            reader.seek(100)

    def test_hexdump(self) -> None:
        """测试十六进制转储。"""
        buf = b"\x01\x02\x03\x04"
        reader = BinaryReader(buf)
        dump = reader.hexdump(4)
        assert "01 02 03 04" in dump


# ── OleReader Tests ──────────────────────────────────────────────────────


class TestOleReader:
    """OleReader CFB 容器测试。"""

    def test_valid_ole_magic(self) -> None:
        """测试有效 OLE 文件打开。
        
        使用真实 .dsn 测试文件（需存在）。
        """
        test_file = Path("D:/26暑假/cis2hdl/tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN")
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        ole = OleReader(test_file)
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

    def test_list_entries_from_real_dsn(self) -> None:
        """测试从真实 DSN 列出条目。"""
        test_file = Path("D:/26暑假/cis2hdl/tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN")
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        ole = OleReader(test_file)
        entries = ole.list_all_entries()
        assert len(entries) > 0
        # Should have page entries
        pages = [e for e in entries if "Pages" in e.full_path]
        assert len(pages) > 0, f"No page entries found in {test_file}"


# ── FutureDataList Tests ─────────────────────────────────────────────────


class TestFutureDataList:
    """FutureDataList 检查点边界追踪器测试。"""

    def test_empty_no_issues(self) -> None:
        """空 FutureDataList 不报错。"""
        reader = BinaryReader(b"\x00" * 100)
        fdl = FutureDataList(reader)
        fdl.checkpoint()  # Should not raise
        fdl.read_rest_of_structure()  # Should not raise

    def test_push_and_checkpoint(self) -> None:
        """push + checkpoint 正常工作。"""
        reader = BinaryReader(b"\x00" * 200)
        fdl = FutureDataList(reader)
        fdl.push(0, 100)
        reader.seek(50)
        fdl.checkpoint()  # 50 < 100, OK

    def test_checkpoint_past_max_warns(self) -> None:
        """超过边界时发出警告但不崩溃。"""
        reader = BinaryReader(b"\x00" * 200)
        fdl = FutureDataList(reader)
        fdl.push(0, 50)
        reader.seek(100)
        # Should warn but not raise
        fdl.checkpoint()

    def test_read_rest_of_structure_skips(self) -> None:
        """read_rest_of_structure 跳过剩余未读取字节。"""
        reader = BinaryReader(b"\x00" * 200)
        fdl = FutureDataList(reader)
        fdl.push(0, 100)
        reader.seek(50)
        fdl.read_rest_of_structure()
        assert reader.tell() == 100


# ── Structure Parser Tests ──────────────────────────────────────────────


class TestStructureParsers:
    """结构体解析器测试。"""

    def test_preamble_magic_bytes(self) -> None:
        """验证前导码魔数常量。"""
        assert PREAMBLE_MAGIC == bytes([0xFF, 0xE4, 0x5C, 0x39])
        assert len(PREAMBLE_MAGIC) == 4

    def test_read_preamble_valid(self) -> None:
        """测试有效前导码解析。"""
        # Preamble format: 4 magic + 4 data_len (uint32) + skip(data_len)
        # RTL DSN: data_len == 0, so total read = 8 bytes
        buf = PREAMBLE_MAGIC + b"\x00" * 44  # 4 magic + 4 data_len (=0) + padding
        reader = BinaryReader(buf)
        read_preamble(reader)  # Should not raise
        assert reader.tell() == 8  # 4 magic + 4 data_len (RTL: data_len=0, no skip)

    def test_read_preamble_invalid_raises(self) -> None:
        """测试无效前导码抛出异常。"""
        buf = b"\xAA\xBB\xCC\xDD" + b"\x00" * 44
        reader = BinaryReader(buf)
        with pytest.raises(BinaryReadError):
            read_preamble(reader)

    def test_structure_type_values(self) -> None:
        """验证结构体类型枚举值。"""
        assert StructureType.PlacedInstance == 13
        assert StructureType.T0x10 == 16
        assert StructureType.WireScalar == 20
        assert StructureType.Port == 23
        assert StructureType.Package == 31
        assert StructureType.Device == 32
        assert StructureType.Global == 37
        assert StructureType.OffPageConnector == 38
        assert StructureType.SymbolDisplayProp == 39
        assert StructureType.Alias == 49


# ── LayoutMapper Tests ──────────────────────────────────────────────────


class TestLayoutMapper:
    """LayoutMapper 坐标映射测试。"""

    def test_map_position_snaps_to_grid(self) -> None:
        """坐标映射到网格测试。"""
        mapper = LayoutMapper(grid_spacing=16)
        hdl_x, hdl_y = mapper.map_position(100, 250)
        assert hdl_x % 16 == 0
        assert hdl_y % 16 == 0

    def test_map_position_raw_no_snapping(self) -> None:
        """原始坐标映射不丢精度。"""
        mapper = LayoutMapper()
        x, y = mapper.map_position_raw(100, 250)
        assert x == 100.0 * mapper.CIS_TO_HDL_SCALE
        assert y == 250.0 * mapper.CIS_TO_HDL_SCALE

    def test_set_scale(self) -> None:
        """设置缩放因子生效。"""
        mapper = LayoutMapper()
        mapper.set_scale(2.0)
        x, y = mapper.map_position(100, 200)
        # 100 * 2.0 = 200, 200/16 = 12.5, round(12.5)=12 or 13 → 192 or 208
        assert x in (192, 208), f"Expected 192 or 208, got {x}"

    def test_set_grid_spacing(self) -> None:
        """设置网格间距生效。"""
        mapper = LayoutMapper()
        mapper.set_grid_spacing(10)
        x, y = mapper.map_position(103, 207)
        assert x % 10 == 0
        assert y % 10 == 0


# ── CrossValidator Tests ────────────────────────────────────────────────


class TestCrossValidator:
    """交叉验证器测试。"""

    def test_empty_designs_pass(self) -> None:
        """空设计通过验证。"""
        from cis2hdl.core.ir.design import DesignIR

        edif = DesignIR(project_name="test", source_format="EDIF")
        dsn = DesignIR(project_name="test", source_format="DSN")
        validator = CrossValidator()
        report = validator.validate(edif, dsn)
        assert report.passed
        assert report.error_count == 0

    def test_different_instance_counts_fail(self) -> None:
        """不同器件数量报错。"""
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.ir.component import ComponentInstanceIR

        edif = DesignIR(project_name="test", source_format="EDIF")
        edif.pages.append(PageIR(page_id="1.1"))
        edif.pages[0].instances.append(
            ComponentInstanceIR(refdes="R1", library_id="RES")
        )

        dsn = DesignIR(project_name="test", source_format="DSN")
        dsn.pages.append(PageIR(page_id="1.1"))
        # No instances

        validator = CrossValidator()
        report = validator.validate(edif, dsn)
        assert not report.passed
        assert report.error_count >= 1


# ── DSN Parser Integration Tests ────────────────────────────────────────


class TestDSNParser:
    """DSN Parser 集成测试。"""

    def test_parser_registers(self) -> None:
        """DSNParser 可正确注册。"""
        parser = DSNParser()
        assert parser.FORMAT_NAME == "CIS_DSN"
        assert ".dsn" in parser.FILE_EXTENSIONS

    def test_parse_real_dsn(self) -> None:
        """解析真实 .dsn 文件。"""
        test_file = Path("D:/26暑假/cis2hdl/tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN")
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        parser = DSNParser()
        design = parser.parse(test_file)
        assert design.project_name == "RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0"
        assert len(design.pages) > 0

        total_inst = sum(len(p.instances) for p in design.pages)
        total_nets = sum(len(p.nets) for p in design.pages)
        assert total_inst > 0, "Should have at least one instance"
        # Nets: parser currently focuses on instances/ports; net extraction is Phase II scope

    def test_parse_real_dsn_has_coordinates(self) -> None:
        """DSN 解析结果包含坐标。"""
        test_file = Path("D:/26暑假/cis2hdl/tests/fixtures/RTL8367RB-VC-DEMO-LQFP128EP-P4L-V1_0.DSN")
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        parser = DSNParser()
        design = parser.parse(test_file)

        for page in design.pages:
            for inst in page.instances:
                # Each instance should have coordinates (not both zero)
                assert isinstance(inst.loc_x, int)
                assert isinstance(inst.loc_y, int)
                # At least some instances should have non-zero coordinates
                if inst.loc_x != 0 or inst.loc_y != 0:
                    return  # Found coordinates — test passes

        pytest.fail("No instances with non-zero coordinates found")
