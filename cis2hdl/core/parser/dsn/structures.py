"""DSN Structure Parsers — 结构体解析器（Binary DSN Parser Layer 3）。

基于 openOrCadParser/universal-netlist 的 GenericParser 和
各结构体解析函数移植。

支持 12 种 DSN 结构类型：
    SymbolDisplayProp(39), T0x10(16), PlacedInstance(13),
    WireScalar(20), WireBus(21), Port(23), LibraryPart(24),
    Package(31), Device(32), Global(37), OffPageConnector(38),
    Alias(49)

参考：
    - openOrCadParser: ParserStructure.cpp, GenericParser.hpp
    - universal-netlist: generic-parser.ts, page-parser.ts
    - BACKEND_DESIGN.md §3.1
"""

from __future__ import annotations

# ============================================================
# DSN 二进制布局常量（格式文档，不影响解析逻辑）
# ============================================================
class DSNBinaryLayout:
    """DSN 二进制格式的字段偏移量定义。

    这些常量仅用于记录格式规范，不参与运行时解析。
    参考: OpenOrCadParser DataStream.hpp, Cadence SPB 16.6 DSN XSD
    """
    # ── T0x10 (引脚-网络连接点, Type 16) ──
    T0X10_PIN_INDEX_OFFSET: int = 0      # uint16 pin_index (2's complement)
    T0X10_POINT_OFFSET: int = 2          # int16 x + int16 y
    T0X10_NET_ID_OFFSET: int = 6         # uint32
    T0X10_RESERVED_SKIP: int = 4         # 4 unknown bytes after net_id

    # ── PlacedInstance (器件实例, Type 13) ──
    PLACED_HEADER_SKIP: int = 8          # 8 unknown header bytes before pkgName
    PLACED_UNKNOWN_SKIP: int = 8         # 8 unknown bytes after dbId
    PLACED_ROT_SKIP: int = 4             # rotation + mirror flags
    PLACED_SDPS_END_SKIP: int = 1        # end-of-display-props marker
    PLACED_RESERVED_SKIP: int = 10       # 10 reserved bytes before t0x10 count
    PLACED_TAIL_SKIP: int = 2            # trailing padding

    # ── SymbolDisplayProp (显示属性, Type 39) ──
    SDP_VISIBILITY_SKIP: int = 2         # visibility flags
    SDP_RESERVED_SKIP: int = 1           # assumed 0x00 reserved byte

    # ── Wire (导线, Type 20/21) ──
    WIRE_HEADER_SKIP: int = 2            # unknown header

    # ── GraphicInst (图形实例) ──
    GI_HEADER_SKIP: int = 2              # unknown header bytes
    GI_MID_SKIP: int = 8                 # mid-structure unknown bytes
    GI_POST_COORD_SKIP: int = 2          # post-coordinate flags
    GI_SDPS_END_SKIP: int = 1            # end-of-SDPs marker
    GI_TAIL_SKIP: int = 5                # tail padding

    # ── NetAlias (网络别名, Type 49) ──
    NET_ALIAS_VISIBILITY_SKIP: int = 1   # visibility/flag byte

    # ── RTL 格式特殊字段 ──
    RTL_STRING_NUL_PADDING: int = 1      # NUL terminator after RTL strings
    T0X10_RECORD_OFFSET: int = 2         # unknown in RTL T0x10 records


import logging
import re
from dataclasses import dataclass, field
from enum import IntEnum

from .binary_reader import BinaryReader, BinaryReadError

logger = logging.getLogger(__name__)

# ── Module-level strLst (string table) ─────────────────────────────────────
# Set by page_parser.parse_page() before structure parsing begins.
# Used to resolve numeric indices in SymbolDisplayProp, PlacedInstance,
# NetAlias, and prefix properties into human-readable strings.

_strlst: list[str] | None = None


def set_strlst(strlst: list[str] | None) -> None:
    """Set the global strLst for index-to-string resolution."""
    global _strlst
    _strlst = strlst


def get_strlst() -> list[str] | None:
    """Return the global strLst, or None if not set."""
    return _strlst


def _is_valid_rtl_name(name: str) -> bool:
    """Check if a strLst-resolved name is a valid RTL instance name.

    strLst entries include both refdes/pkg_name values AND property values
    (DESCRIPTION, SOURCE_LIBRARY, etc.).  This function filters out entries
    that are clearly property values rather than component identifiers.

    Args:
        name: The resolved string from strLst.

    Returns:
        True if the name looks like a valid refdes or pkg_name.
    """
    if not name:
        return False

    # Reject Windows file paths (SOURCE_LIBRARY values)
    if '\\\\' in name or ':\\' in name:
        return False
    # Reject Unix-style absolute paths
    if name.startswith('/') and len(name) > 30:
        return False

    # Reject very long names (>60 chars — likely file paths or
    # concatenated data, not valid refdes/pkg_name)
    if len(name) > 60:
        return False

    # Reject strings with zero ASCII alphanumeric characters and
    # length > 4 — these are likely Chinese DESCRIPTION text
    # (e.g. "片式电感", "终端功率电感") rather than component names
    has_ascii_alnum = any(c.isascii() and c.isalnum() for c in name)
    if not has_ascii_alnum and len(name) > 4:
        return False

    # Reject names containing only whitespace
    if not name.strip():
        return False

    return True


def _resolve_strlst(idx: int) -> str:
    """Resolve a strLst index to its string value.

    Args:
        idx: Index into the string table.

    Returns:
        The resolved string, or empty string if out of range or strlst not set.
    """
    if _strlst is not None and 0 <= idx < len(_strlst):
        return _strlst[idx]
    return ""


# ── 结构体类型枚举 ────────────────────────────────────────────────────────


class StructureType(IntEnum):
    """DSN 二进制流中的结构体类型标识。"""

    Page = 10
    PlacedInstance = 13
    T0x10 = 16  # 引脚到网络连接点
    WireScalar = 20
    WireBus = 21
    Port = 23
    LibraryPart = 24
    Package = 31
    Device = 32
    Global = 37  # 全局信号标记 (VCC/GND)
    OffPageConnector = 38
    SymbolDisplayProp = 39
    Alias = 49  # 网络标签
    Junction = 50  # 连接点（某些版本）
    TitleBlock = 65  # 标题栏


# ── 前缀记录 ──────────────────────────────────────────────────────────────


@dataclass
class PrefixProperty:
    """PlacedInstance 前缀属性（PartInstUserProp）。"""

    name: str = ""
    value: str = ""

    def __repr__(self) -> str:
        return f"PrefixProperty({self.name}={self.value})"


# ── 结构体数据类 ──────────────────────────────────────────────────────────


@dataclass
class SymbolDisplayProp:
    """显示属性结构（Type 39）。

    定义文本属性在原理图上的显示方式（位置、旋转、字体、颜色）。
    XSD 映射：PartInstDisplayProp。
    """

    name_idx: int  # 字符串表索引
    loc_x: int
    loc_y: int
    text_font_idx: int  # 低 14 位是字体索引
    rotation: int  # 高 2 位：0/1/2/3 → 0°/90°/180°/270°
    color: int  # 颜色索引

    def is_visible(self) -> bool:
        """显示属性是否可见（非黑色/0时通常可见）。"""
        return self.color != 0


@dataclass
class T0x10:
    """引脚到网络连接点结构（Type 16）。

    连接 PlacedInstance 的引脚到具体网络。
    """

    pin_index: int  # 引脚索引（补码编码：<32768 为正，否则取补）
    point_x: int  # 引脚连接点坐标 X
    point_y: int  # 引脚连接点坐标 Y
    net_id: int  # 网络 ID
    display_props: list[SymbolDisplayProp] = field(default_factory=list)


@dataclass
class PlacedInstance:
    """放置的器件实例结构（Type 13）。

    原理图页面上的每个器件对应一个 PlacedInstance。
    XSD 映射：PartInst。
    """

    pkg_name: str  # 器件封装名
    db_id: int  # 数据库 ID
    reference: str  # 位号 "R1", "U3"
    source_package: str  # 来源 Package 名
    part_value_idx: int  # 器件值在 strLst 中的索引
    loc_x: int  # 放置位置 X 坐标
    loc_y: int  # 放置位置 Y 坐标
    display_props: list[SymbolDisplayProp] = field(default_factory=list)
    t0x10_list: list[T0x10] = field(default_factory=list)
    prefix_props: list[PrefixProperty] = field(default_factory=list)
    rotation: int = 0
    mirror: int = 0


@dataclass
class WireSegment:
    """线段结构（Type 20/21）。"""

    segment_id: int
    wire_id: int
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    aliases: list[int] = field(default_factory=list)  # Alias ID 列表


@dataclass
class GraphicInst:
    """图形实例（Type 23/37/38 的公共结构）。

    用于 Port、Global、OffPageConnector。
    """

    name: str  # 名称或全局信号名
    db_id: int
    loc_x: int
    loc_y: int
    rotation: int = 0
    pairing_id: int = 0  # 配对 ID（Port/OffPage 的跨页关联）
    display_props: list[SymbolDisplayProp] = field(default_factory=list)


@dataclass
class NetAlias:
    """网络标签结构（Type 49）。"""

    alias_id: int
    name: str  # 网络名
    loc_x: int
    loc_y: int
    color: int = 0
    rotation: int = 0


@dataclass
class TitleBlockText:
    """标题栏文本结构（Type 65）。

    从 4 信息页（Cover_Page, Block_Diagram, Clock_Tree, Power_Tree）的
    TitleBlock 结构中提取的文本注释。
    """

    text: str = ""
    loc_x: int = 0
    loc_y: int = 0


# ── FutureDataList — 检查点边界追踪器 ──────────────────────────────────────

PREAMBLE_MAGIC = bytes([0xFF, 0xE4, 0x5C, 0x39])


class FutureDataList:
    """结构体检查点边界追踪器。

    移植自 openOrCadParser C++ 的 FutureData 类。
    用于解析包含"未来"未知数据的可变长度结构体块。

    工作原理：
    1. 遇到未知前缀块时 push(preamble_offset, size) 添加到队列
    2. checkpoint() 验证当前读取位置在已知边界内
    3. 结构体解析完成后 read_rest_of_structure() 跳过所有剩余未知块
    """

    def __init__(self, reader: BinaryReader) -> None:
        self._reader = reader
        self._stops: list[int] = []

    def push(self, preamble_offset: int, size: int) -> None:
        """添加未知块的边界。

        Args:
            preamble_offset: 块的起始偏移（在原始缓冲区中的位置）。
            size: 块的大小（字节数）。
        """
        self._stops.append(preamble_offset + size)

    def get_max_stop_offset(self) -> int:
        """返回当前所有未知块的最大结束偏移。"""
        return max(self._stops) if self._stops else self._reader.tell()

    def checkpoint(self) -> None:
        """验证当前位置小于等于最大边界偏移。

        如果当前位置超出预期边界，扩展边界以容纳实际数据，
        避免因边界溢出导致下游解析失败。
        """
        if not self._stops:
            return
        max_stop = self.get_max_stop_offset()
        current = self._reader.tell()
        if current > max_stop:
            logger.debug(
                "Structure parse position 0x%X exceeds max stop 0x%X; "
                "extending boundary to accommodate actual data",
                current,
                max_stop,
            )
            # Extend the last stop boundary to the current position
            # so that subsequent read_rest_of_structure() won't skip backward
            self._stops[-1] = current

    def read_rest_of_structure(self) -> None:
        """跳过剩余未知数据到最大边界位置。"""
        if not self._stops:
            return
        max_stop = self.get_max_stop_offset()
        current = self._reader.tell()
        skip_size = max_stop - current
        if skip_size > 0:
            logger.debug(
                "Skipping %d unknown bytes to reach structure boundary",
                skip_size,
            )
            self._reader.skip(skip_size)
        self._stops.clear()


# ── 通用解析框架 ──────────────────────────────────────────────────────────


def read_preamble(reader: BinaryReader) -> str:
    """读取并验证结构体前导码 FF E4 5C 39，返回格式标识符。

    返回:
        "rtl"     — RTL DSN 变体格式（data_len == 0，字符串使用 uint16 长度前缀）
        "standard" — 标准 OrCAD 格式（data_len > 0，字符串使用 NUL 终止）

    Raises:
        BinaryReadError: 前导码不匹配。
    """
    magic = reader.read_bytes(4)
    if magic != PREAMBLE_MAGIC:
        raise BinaryReadError(
            f"Expected preamble {PREAMBLE_MAGIC.hex(' ')}, got {magic.hex(' ')}",
            position=reader.tell() - 4,
        )
    # Read trailing data length (uint32) and skip that many bytes.
    # In RTL DSN files this is always 0x00000000, meaning structure data
    # starts immediately after the preamble (8 bytes total: 4 magic + 4 len).
    # Reference: OpenOrCadParser GenericParser::readPreamble()
    data_len = reader.read_uint32()
    reader.skip(data_len)
    return "rtl" if data_len == 0 else "standard"


def skip_struct_header(reader: BinaryReader) -> int:
    """跳过结构体头部块，返回块大小。

    DSN 结构中常见的前缀块格式：
        uint32 size, uint32 chunk_type, <size-8 bytes of data>

    返回 size 以便外层追踪边界。
    """
    size = reader.read_uint32()
    if size < 8:
        return size
    reader.skip(size - 4)  # Remaining after size field itself
    return size


def read_until_zero(reader: BinaryReader, max_len: int = 1024) -> tuple[int, ...]:
    """读取 uint32 列表直到遇到 0。

    用于读取 strLst 索引列表（如 net_id_list）。
    """
    result: list[int] = []
    for _ in range(max_len):
        val = reader.read_uint32()
        if val == 0:
            break
        result.append(val)
    return tuple(result)


def _read_dsn_string(reader: BinaryReader, dsn_format: str) -> str:
    """根据 DSN 格式标识读取字符串。

    Args:
        reader: 二进制读取器。
        dsn_format: "rtl" 或 "standard"，由 read_preamble() 返回。

    Returns:
        解码后的字符串。

    RTL 格式使用 uint16 长度前缀 + 原始字节（无 NUL 终止）。
    Standard 格式使用 uint32 长度前缀 + NUL 终止字符串。
    """
    if dsn_format == "rtl":
        return _read_rtl_string(reader)
    else:
        return reader.read_string_len_zero_term()


def _read_rtl_string(reader: BinaryReader) -> str:
    """读取 RTL DSN 格式的字符串：uint16(len) + len 字节 + NUL 填充。

    RTL DSN 变体格式中的字符串编码：
        uint16 长度前缀（不含 NUL）
        + 字符串原始字节（latin-1 编码）
        + 1 字节 NUL 填充/终止

    与 read_string_uint16_len() 的区别：额外跳过末尾的 NUL 字节。
    """
    result = reader.read_string_uint16_len()
    # DSNBinaryLayout.RTL_STRING_NUL_PADDING
    reader.skip(1)  # Skip trailing NUL/padding byte
    return result


# ── RTL 结构体统一解析 ────────────────────────────────────────────────────


@dataclass
class _RtlStructure:
    """RTL DSN 变体格式的通用结构体头部。

    RTL 格式中所有 STRING 类型结构（Port/Global/PlacedInstance）共用
    同一二进制布局：

        preamble(8B)
        uint16(str_len) + str_len bytes + NUL     ← name
        uint32[0]                                  ← db_id / coord
        uint32[1]                                  ← coord / flags
        uint32[2]                                  ← coord (symmetric)
        uint32[3]                                  ← coord
        uint32[4]                                  ← flags
        uint32[5]                                  ← t0x10_count
        [T0x10 sub-structures...]                  ← variable
    """

    name: str
    db_id: int
    loc_x: int
    loc_y: int
    t0x10_count: int
    from_strlst: bool = False  # True if name was resolved from strLst index
    strlst_index: int = 0  # strLst index when from_strlst=True

    @classmethod
    def parse(cls, reader: BinaryReader) -> _RtlStructure:
        """从当前读取位置解析 RTL 结构体头部。

        Raises:
            ValueError: 如果结构体不是有效的 RTL STRING 类型
                       （例如 LAYOUT 或其他非 STRING 前导码）。
        """
        # Validate: RTL STRING structures have uint16 string length 1-200
        # LAYOUT/Wire structures have first uint16 > 200 (e.g. 0x2E2E)
        # HOWEVER: in HG5015 DSN variant, this field may be a strLst index
        # (uint16, typically 600-5000), not a string length.
        # We only apply strLst resolution for values > 200 to avoid
        # confusing metadata entries (indices 1-200) with real components.
        str_len = reader.read_uint16()

        # ── Check if this is a strLst index (> 200, < len(strlst)) ──
        # Using > 200 threshold to avoid confusing Port/Wire/Global
        # RTL structures (whose internal data can fall in the 1-200 range)
        # with strLst indices (typically 600-5000 for HG5015).
        # Threshold 100 was too low: Port/Wire structures with str_len in
        # 100-200 range were misidentified as strLst indices, producing
        # garbled names for non-PlacedInstance structures.
        strlst = get_strlst()
        from_strlst = False
        strlst_index = 0
        if strlst and str_len > 200 and str_len < len(strlst):
            # HG5015 variant: strLst index for pkg_name/reference
            name = strlst[str_len]
            from_strlst = True
            strlst_index = str_len
            logger.debug("_RtlStructure: str_len=%d -> resolved '%s' from strLst", str_len, name[:60])

            # Validate: some strLst entries are property values
            # (DESCRIPTION like "片式电感", SOURCE_LIBRARY paths)
            # rather than valid refdes/pkg_name identifiers.
            if not _is_valid_rtl_name(name):
                raise ValueError(
                    f"RTL name resolved from strLst[{str_len}] is not a "
                    f"valid refdes/pkg_name: {name!r}"
                )
        elif str_len == 0 or str_len > 200:
            # Not a valid RTL string length and not a strLst index
            logger.debug("_RtlStructure: str_len=%d -> ValueError (out of range)", str_len)
            raise ValueError(
                f"Invalid RTL string length {str_len} — "
                f"not a Port/Instance structure"
            )
        else:
            # Normal RTL string: read str_len bytes + trailing NUL
            if str_len > reader.remaining():
                logger.debug("_RtlStructure: str_len=%d -> ValueError (exceeds remaining)", str_len)
                raise ValueError(
                    f"RTL string length {str_len} exceeds remaining data"
                )
            name = reader.read_bytes(str_len).decode("latin-1")
            # DSNBinaryLayout.RTL_STRING_NUL_PADDING
            reader.skip(1)  # NUL terminator

        db_id = reader.read_uint32()

        # Read 4 uint32 coordinate/flag fields
        c0 = reader.read_uint32()
        c1 = reader.read_uint32()
        c2 = reader.read_uint32()
        c3 = reader.read_uint32()

        # c2 encodes the X coordinate (low 16 bits → signed int16).
        # c3 encodes the Y coordinate (low 16 bits → signed int16).
        # For ports, c2 is the pin offset from chip origin (e.g. -30 left,
        # 500 right) and c3.lo is a type flag (0x0021=33).
        # For PlacedInstance, c2.lo = page X, c3.lo = page Y.
        def _int16_from_u32(val: int, shift: int = 0) -> int:
            """Extract signed int16 from a 16-bit slice of a uint32."""
            v = (val >> shift) & 0xFFFF
            return v - 0x10000 if v >= 0x8000 else v

        loc_x = _int16_from_u32(c2, 0)
        loc_y = _int16_from_u32(c3, 0)

        # c0 often mirrors c2 (both are the same coordinate value)
        # Use c0 as db_id fallback if it's more reasonable
        if db_id == 0 and 0 < c0 < 10000:
            db_id = c0

        flags = reader.read_uint32()
        t0x10_count = reader.read_uint32()

        return cls(
            name=name,
            db_id=db_id,
            loc_x=loc_x,
            loc_y=loc_y,
            t0x10_count=t0x10_count,
            from_strlst=from_strlst,
            strlst_index=strlst_index,
        )


def _skip_rtl_t0x10_list(reader: BinaryReader, count: int) -> None:
    """跳过 RTL 格式的 T0x10 子结构列表。

    RTL 格式的 T0x10 子结构以 0x1A 字节标记分隔，变长格式。
    我们使用基于 0x1A 标记的模式来跳过它们，直到遇到下一个 preamble
    或数据结束。
    """
    if count == 0:
        return

    # RTL T0x10 sub-structures are marked by 0x1A byte
    # Each T0x10 is: 1A <variable data>
    # We skip until the remaining data doesn't look like T0x10
    for _ in range(count):
        if reader.remaining() < 1:
            break
        # Look for 0x1A marker
        try:
            marker = reader.read_uint8()
            if marker != 0x1A:
                # Put back and stop
                reader._pos -= 1
                break
            # Skip the variable-length T0x10 data
            # T0x10 data seems to be 5-11 bytes
            # Heuristic: read until next 0x1A or until preamble magic
            _skip_rtl_t0x10_body(reader)
        except BinaryReadError:
            break


def _skip_rtl_t0x10_body(reader: BinaryReader) -> None:
    """跳过单个 RTL T0x10 子结构体数据。

    扫描字节直到遇到下一个 0x1A 标记或 preamble magic，
    但最多跳过 16 字节。
    """
    start = reader.tell()
    max_scan = min(reader.remaining(), 16)
    for _ in range(max_scan):
        if reader.remaining() < 1:
            return
        b = reader._buf[reader._pos]
        if b == 0x1A or (b == 0xFF and reader.remaining() >= 4
                         and bytes(reader._buf[reader._pos:reader._pos + 4]) == PREAMBLE_MAGIC):
            # Found next marker — stop before it
            return
        reader._pos += 1
    # If we scanned 16 bytes without finding a marker, we've consumed the body


# ── 各结构体解析函数 ──────────────────────────────────────────────────────


def parse_symbol_display_props(
    reader: BinaryReader, count: int
) -> list[SymbolDisplayProp]:
    """批量解析 SymbolDisplayProp 结构列表。

    Args:
        reader: 二进制读取器。
        count: 要解析的符号显示属性数量。

    Returns:
        SymbolDisplayProp 列表。
    """
    result: list[SymbolDisplayProp] = []
    for _ in range(count):
        result.append(parse_symbol_display_prop(reader))
    return result


def parse_symbol_display_prop(reader: BinaryReader) -> SymbolDisplayProp:
    """解析单个 SymbolDisplayProp 结构（Type 39）。

    从当前读取位置开始解析一个完整的显示属性结构。
    """
    future_data = FutureDataList(reader)
    auto_read_prefixes(reader, future_data, StructureType.SymbolDisplayProp)
    read_preamble(reader)
    future_data.checkpoint()

    name_idx = reader.read_uint32()
    # Resolve strLst index to display name if available
    dsp_name = _resolve_strlst(name_idx)
    loc_x = reader.read_int16()
    loc_y = reader.read_int16()
    rot_font = reader.read_uint16()
    text_font_idx = rot_font & 0x3FFF
    rotation = rot_font >> 14
    color = reader.read_uint8()
    # DSNBinaryLayout.SDP_VISIBILITY_SKIP
    reader.skip(2)  # visibility flags
    # DSNBinaryLayout.SDP_RESERVED_SKIP
    reader.skip(1)  # reserved

    future_data.checkpoint()
    future_data.read_rest_of_structure()
    return SymbolDisplayProp(
        name_idx=name_idx,
        loc_x=loc_x,
        loc_y=loc_y,
        text_font_idx=text_font_idx,
        rotation=rotation,
        color=color,
    )


def parse_t0x10(reader: BinaryReader) -> T0x10:
    """解析 T0x10 结构（Type 16）— 引脚到网络连接点。"""
    future_data = FutureDataList(reader)
    auto_read_prefixes(reader, future_data, StructureType.T0x10)
    read_preamble(reader)
    future_data.checkpoint()

    sth = reader.read_uint16()
    # 2's complement decoding: if < 32768, it's positive; else negative
    pin_index = sth if sth < 32768 else 65536 - sth
    point_x = reader.read_int16()
    point_y = reader.read_int16()
    net_id = reader.read_uint32()
    # DSNBinaryLayout.T0X10_RESERVED_SKIP
    reader.skip(4)  # Unknown/reserved

    sdp_count = reader.read_uint16()
    sdps = parse_symbol_display_props(reader, sdp_count)

    future_data.checkpoint()
    future_data.read_rest_of_structure()
    return T0x10(
        pin_index=pin_index,
        point_x=point_x,
        point_y=point_y,
        net_id=net_id,
        display_props=sdps,
    )


def parse_placed_instance(reader: BinaryReader) -> PlacedInstance:
    """解析 PlacedInstance 结构（Type 13）— 原理图上的器件实例。

    Phase XI T04: RTL format path restored (v0.5.0 removed it, breaking
    RTL DSNs like RTL8367RB which yield 0 instances).  The RTL variant
    shares the generic _RtlStructure layout; component identity still
    comes from CrossRef CSV in the conversion pipeline, but the raw
    instance data must be parseable for inventory/pages.
    """
    future_data = FutureDataList(reader)
    prefix_props = auto_read_prefixes(
        reader, future_data, StructureType.PlacedInstance
    )
    dsn_format = read_preamble(reader)
    future_data.checkpoint()

    if dsn_format == "rtl":
        # Phase XI T04: restore RTL PlacedInstance parsing.  Layout per
        # _RtlStructure: name(strLst/str) + 6 uint32 + T0x10 list.
        return _parse_placed_instance_rtl(reader, future_data, prefix_props)
    else:
        return _parse_placed_instance_standard(reader, future_data, prefix_props)


def _parse_placed_instance_rtl(
    reader: BinaryReader,
    future_data: FutureDataList,
    prefix_props: list[PrefixProperty],
) -> PlacedInstance:
    """Parse an RTL-variant PlacedInstance (Type 13).

    Mirrors _parse_graphic_inst_rtl: _RtlStructure.parse for the header,
    then a trailing reference string (refdes), then the T0x10 list.
    """
    rtl = _RtlStructure.parse(reader)
    reference = ""
    # Reference (refdes) is a trailing strLst-or-string after the header.
    try:
        str_len = reader.read_uint16()
        if 0 < str_len <= 100:
            raw = reader.read_bytes(str_len)
            reader.skip(1)  # NUL
            reference = raw.decode("latin-1", errors="replace").strip()
    except BinaryReadError:
        reference = ""
    # T0x10 sub-structures (pin → net) — parse count entries.
    t0x10_list: list[T0x10] = []
    for _ in range(max(0, rtl.t0x10_count)):
        try:
            t0x10_list.append(parse_t0x10(reader))
        except BinaryReadError:
            break
    future_data.checkpoint()
    future_data.read_rest_of_structure()
    return PlacedInstance(
        pkg_name=rtl.name,
        db_id=rtl.db_id,
        reference=reference,
        source_package=rtl.name,
        part_value_idx=0,
        loc_x=rtl.loc_x,
        loc_y=rtl.loc_y,
        display_props=[],
        t0x10_list=t0x10_list,
        prefix_props=prefix_props,
    )


def _parse_placed_instance_standard(
    reader: BinaryReader,
    future_data: FutureDataList,
    prefix_props: list[PrefixProperty],
) -> PlacedInstance:
    """标准 OrCAD 格式的 PlacedInstance 解析。"""
    # DSNBinaryLayout.PLACED_HEADER_SKIP
    reader.skip(8)  # Unknown header

    # ── pkg_name: may be a strLst index (HG5015 variant) or a
    #     length-prefixed string (standard OrCAD format).
    # Strategy: first try uint16 (common for HG5015), then uint32,
    # then fall back to length-prefixed string read.
    # Using > 200 threshold avoids confusing legitimate string lengths
    # (1-200 bytes) with strLst entries.
    strlst = get_strlst()
    pos_before = reader.tell()

    # Try 1: uint16 strLst index (HG5015 common case)
    candidate_u16 = reader.read_uint16()
    if strlst and candidate_u16 > 100 and candidate_u16 < len(strlst):
        pkg_name = strlst[candidate_u16]
    else:
        # Try 2: uint32 strLst index (HG5015 alternate case)
        reader.seek(pos_before)
        candidate_u32 = reader.read_uint32()
        if strlst and candidate_u32 > 100 and candidate_u32 < len(strlst):
            pkg_name = strlst[candidate_u32]
        else:
            # Fallback: standard OrCAD string format
            reader.seek(pos_before)
            pkg_name = reader.read_string_len_zero_term()
    if not pkg_name or not pkg_name.isascii():
        pos = reader.tell()
        logger.debug(
            "PlacedInstance pkg_name garbled: %r (pos=0x%X, next bytes: %s)",
            pkg_name, pos,
            reader.peek(min(20, reader.remaining())).hex() if reader.remaining() > 0 else "<EOF>",
        )
    db_id = reader.read_uint32()
    # DSNBinaryLayout.PLACED_UNKNOWN_SKIP
    reader.skip(8)  # Unknown
    loc_x = reader.read_int16()
    loc_y = reader.read_int16()
    # DSNBinaryLayout.PLACED_ROT_SKIP
    reader.skip(4)  # Unknown (possibly rotation/mirror flags)

    sdp_count = reader.read_uint16()
    sdps = parse_symbol_display_props(reader, sdp_count)
    # DSNBinaryLayout.PLACED_SDPS_END_SKIP
    reader.skip(1)  # Reserved / end-of-sdps marker
    future_data.checkpoint()

    # ── reference: same strLst-index-or-string logic as pkg_name ──
    pos_before_ref = reader.tell()
    ref_u16 = reader.read_uint16()
    if strlst and ref_u16 > 100 and ref_u16 < len(strlst):
        reference = strlst[ref_u16]
    else:
        reader.seek(pos_before_ref)
        ref_u32 = reader.read_uint32()
        if strlst and ref_u32 > 100 and ref_u32 < len(strlst):
            reference = strlst[ref_u32]
        else:
            reader.seek(pos_before_ref)
            reference = reader.read_string_len_zero_term()
    if not reference or not reference.isascii():
        logger.debug(
            "PlacedInstance reference garbled: %r (pkg_name=%r)",
            reference, pkg_name,
        )
    part_value_idx = reader.read_uint32()
    # Resolve strLst index to part value string
    part_value = _resolve_strlst(part_value_idx)
    # DSNBinaryLayout.PLACED_RESERVED_SKIP
    reader.skip(10)  # Unknown/reserved block

    t0x10_count = reader.read_uint16()
    t0x10_list = [parse_t0x10(reader) for _ in range(t0x10_count)]
    future_data.checkpoint()

    source_package = reader.read_string_len_zero_term()
    # DSNBinaryLayout.PLACED_TAIL_SKIP
    reader.skip(2)
    future_data.checkpoint()
    future_data.read_rest_of_structure()

    return PlacedInstance(
        pkg_name=pkg_name,
        db_id=db_id,
        reference=reference,
        source_package=source_package,
        part_value_idx=part_value_idx,
        loc_x=loc_x,
        loc_y=loc_y,
        display_props=sdps,
        t0x10_list=t0x10_list,
        prefix_props=prefix_props,
    )


def parse_wire(reader: BinaryReader) -> WireSegment:
    """解析 Wire 结构（Type 20/21）— 连线线段。"""
    future_data = FutureDataList(reader)
    auto_read_prefixes(reader, future_data, None)
    read_preamble(reader)
    future_data.checkpoint()

    # DSNBinaryLayout.WIRE_HEADER_SKIP
    reader.skip(2)  # Unknown header
    segment_id = reader.read_uint32()
    wire_id = reader.read_uint32()
    start_x = reader.read_int16()
    start_y = reader.read_int16()
    end_x = reader.read_int16()
    end_y = reader.read_int16()

    # Read aliases (list of uint32 terminated by 0 or EOF marker)
    alias_count = reader.read_uint16()
    aliases: list[int] = []
    for _ in range(alias_count):
        aliases.append(reader.read_uint32())

    future_data.checkpoint()
    future_data.read_rest_of_structure()
    return WireSegment(
        segment_id=segment_id,
        wire_id=wire_id,
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        aliases=aliases,
    )


def parse_graphic_inst(reader: BinaryReader) -> GraphicInst:
    """解析图形实例结构（Type 23/37/38 公共解析器）。

    用于 Port(23)、Global(37)、OffPageConnector(38) 三种类型。
    """
    future_data = FutureDataList(reader)
    prefix = auto_read_prefixes(reader, future_data, None)
    dsn_format = read_preamble(reader)
    future_data.checkpoint()

    if dsn_format == "rtl":
        return _parse_graphic_inst_rtl(reader, future_data)
    else:
        return _parse_graphic_inst_standard(reader, future_data)


def _parse_graphic_inst_standard(
    reader: BinaryReader,
    future_data: FutureDataList,
) -> GraphicInst:
    """标准 OrCAD 格式的图形实例解析。"""
    # DSNBinaryLayout.GI_HEADER_SKIP
    reader.skip(2)
    name = reader.read_string_len_zero_term()
    db_id = reader.read_uint32()
    # DSNBinaryLayout.GI_MID_SKIP
    reader.skip(8)
    loc_x = reader.read_int16()
    loc_y = reader.read_int16()
    # DSNBinaryLayout.GI_POST_COORD_SKIP
    reader.skip(2)

    sdp_count = reader.read_uint16()
    sdps = parse_symbol_display_props(reader, sdp_count)
    # DSNBinaryLayout.GI_SDPS_END_SKIP
    reader.skip(1)
    future_data.checkpoint()

    pairing_id = reader.read_uint32()
    # DSNBinaryLayout.GI_TAIL_SKIP
    reader.skip(5)
    future_data.checkpoint()
    future_data.read_rest_of_structure()

    return GraphicInst(
        name=name,
        db_id=db_id,
        loc_x=loc_x,
        loc_y=loc_y,
        pairing_id=pairing_id,
        display_props=sdps,
    )


def _parse_graphic_inst_rtl(
    reader: BinaryReader,
    future_data: FutureDataList,
) -> GraphicInst:
    """RTL DSN 变体格式的图形实例解析。

    RTL 格式中所有 STRING 结构共用同一布局：
        preamble(8B) | uint16(len) + len bytes + NUL | uint32 × 6 | T0x10...

    与 _parse_placed_instance_rtl 共享 _RtlStructure 头部解析。
    """
    rtl = _RtlStructure.parse(reader)

    # Skip T0x10 sub-structures and remaining unknown data
    t0x10_count = rtl.t0x10_count
    _skip_rtl_t0x10_list(reader, t0x10_count)

    future_data.checkpoint()
    future_data.read_rest_of_structure()

    return GraphicInst(
        name=rtl.name,
        db_id=rtl.db_id,
        loc_x=rtl.loc_x,
        loc_y=rtl.loc_y,
        pairing_id=0,
    )


def parse_port(reader: BinaryReader) -> GraphicInst:
    """解析 Port 结构（Type 23）。"""
    return parse_graphic_inst(reader)


def parse_global(reader: BinaryReader) -> GraphicInst:
    """解析 Global 结构（Type 37）— 全局信号标记(VCC/GND)。"""
    return parse_graphic_inst(reader)


def parse_off_page_connector(reader: BinaryReader) -> GraphicInst:
    """解析 OffPageConnector 结构（Type 38）— 跨页连接器。"""
    return parse_graphic_inst(reader)


def parse_net_alias(reader: BinaryReader) -> NetAlias:
    """解析 NetAlias 结构（Type 49）— 网络标签。"""
    future_data = FutureDataList(reader)
    auto_read_prefixes(reader, future_data, StructureType.Alias)
    read_preamble(reader)
    future_data.checkpoint()

    alias_id = reader.read_uint32()
    name_idx = reader.read_uint32()  # strLst index
    # Resolve strLst index to alias name
    alias_name = _resolve_strlst(name_idx)
    loc_x = reader.read_int16()
    loc_y = reader.read_int16()
    rot = reader.read_uint16()
    rotation = rot >> 14
    color = reader.read_uint8()
    # DSNBinaryLayout.NET_ALIAS_VISIBILITY_SKIP
    reader.skip(1)  # visibility/flag

    future_data.checkpoint()
    future_data.read_rest_of_structure()

    return NetAlias(
        alias_id=alias_id,
        name=alias_name,  # resolved via strLst
        loc_x=loc_x,
        loc_y=loc_y,
        color=color,
        rotation=rotation,
    )


def parse_title_block(reader: BinaryReader) -> TitleBlockText:
    """解析 TitleBlock 结构（Type 65）— 标题栏文本。

    TitleBlock 结构包含一段文本注释（例如设计名、作者、日期等），
    通常出现在 4 信息页（Cover_Page, Block_Diagram, Clock_Tree,
    Power_Tree）中。

    布局（推测）：
        PREFIXES (auto_read_prefixes 自动跳过)
        PREAMBLE
        uint16 text_len + text_len bytes + NUL     ← text string
        -- checkpoint --
    """
    future_data = FutureDataList(reader)
    auto_read_prefixes(reader, future_data, StructureType.TitleBlock)
    read_preamble(reader)
    future_data.checkpoint()

    # TitleBlock 文本使用 uint16 长度前缀（RTL 格式约定）
    text_len = reader.read_uint16()
    text = ""
    if text_len > 0 and text_len <= reader.remaining():
        text = reader.read_bytes(text_len).decode("latin-1")
        reader.skip(1)  # NUL terminator

    future_data.checkpoint()
    future_data.read_rest_of_structure()

    return TitleBlockText(text=text)


# ── auto_read_prefixes ────────────────────────────────────────────────────


def auto_read_prefixes(
    reader: BinaryReader,
    future_data: FutureDataList,
    expected_type: StructureType | None = None,
) -> list[PrefixProperty]:
    """自动读取结构体前缀块链。

    在结构体的 preamble 之前，可能存在未知的"前缀"块队列。
    这些块在 C++ 代码中标记为 futureData，在 JS 代码中标记为 unknown chunks。
    本函数读取这些块并记录边界，同时提取 PlacedInstance 的属性前缀。

    Returns:
        提取的前缀属性列表（PlacedInstance 独有）。
    """
    props: list[PrefixProperty] = []

    while True:
        pos = reader.tell()
        # Check if next bytes look like preamble magic
        if reader.remaining() < 4:
            break
        peek_magic = reader.peek(4)
        if peek_magic == PREAMBLE_MAGIC:
            break

        # Read prefix chunk
        try:
            size = reader.read_uint32()
            if size < 4 or size > reader.remaining() + 4:
                break
            chunk_type = reader.read_uint32()

            # StructureType prefix
            if chunk_type == int(StructureType.SymbolDisplayProp) and expected_type:
                # Found a SymbolDisplayProp prefix inside another struct
                # This is common in PlacedInstance prefix blocks
                future_data.push(pos, size)
                reader.skip(size - 8)
                continue

            future_data.push(pos, size)

            # Extract prefix properties for PlacedInstance
            if expected_type == StructureType.PlacedInstance:
                # The prefix block may contain property name/value pairs
                try:
                    prop_count = reader.read_uint16()
                    for _ in range(prop_count):
                        prop_name = reader.read_string_byte_len()
                        prop_value = reader.read_string_byte_len()
                        props.append(PrefixProperty(name=prop_name, value=prop_value))
                except (BinaryReadError, UnicodeDecodeError):
                    # Not a property block — skip remaining
                    reader.skip(size - 10)
            else:
                reader.skip(size - 8)

        except (BinaryReadError, struct.error):
            break

    return props
