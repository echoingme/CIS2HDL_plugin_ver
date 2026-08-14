"""Unit tests for Binary DSN structure parsers (BinaryReader, FutureDataList, Structure parsers, LayoutMapper)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from cis2hdl.core.parser.dsn.binary_reader import BinaryReader, BinaryReadError
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
