"""OLBParser — OLB 文件顶层解析器。

完整的 OLB 解析管道:
    OleReader → Package流 + Device流 + NormalView流 → DesignIR(ComponentDef 集合)

OLB 文件结构:
    MyLib.olb (CFB)
    ├── Packages/{PkgName}           ← Type 31 Package 结构体
    │   └── Devices                  ← Type 32 Device 定义(含 pinMap)
    ├── Library/strLst               ← 全局字符串表
    └── Symbols/{LibPart}/NormalView ← 符号图形数据(Line/Ellipse/Arc/Polygon/Rect)

OLB Parse 输出一个 DesignIR，其 component_db 中包含所有 Package 的 ComponentDef。

参考:
    - openOrCadParser: OlbParser.cpp
    - universal-netlist: olb-parser.ts
    - BACKEND_DESIGN.md §3.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ..base import ParserBase
from ...ir.design import DesignIR
from ...ir.component import ComponentDef, PinDef, ElectricalType
from ...exceptions import CIS2HDLParseError

from .olb_reader import OLBOleReader
from ..dsn.binary_reader import BinaryReader, BinaryReadError
from ..dsn.structures import (
    PREAMBLE_MAGIC,
    read_preamble,
    FutureDataList,
    auto_read_prefixes,
    StructureType,
    SymbolDisplayProp,
    parse_symbol_display_props,
)

logger = logging.getLogger(__name__)

# ── OLB 结构体类型扩展 ────────────────────────────────────────────────────


class OLBStructureType:
    """OLB 特有的二进制流元素类型标识。

    NormalView 中的图形元素使用类型 ID 区分。
    这些 ID 值来自 openOrCadParser C++ 实现中的 GraphicStyle 枚举。
    """

    NONE = 0x00
    LINE = 0x01
    ELLIPSE = 0x02
    ARC = 0x03
    POLYGON = 0x04
    RECTANGLE = 0x05
    POLYLINE = 0x06
    ELLIPTICAL_ARC = 0x07
    BEZIER = 0x08
    TEXT = 0x09


# ── OLB 结构体数据类 ──────────────────────────────────────────────────────


@dataclass
class OLBPackageData:
    """OLB Package (Type 31) 解析结果。

    与 DSN structures.py 中的 PlacedInstance 共享相似布局，
    但 OLB 中的 Package 是库定义而非页面实例。
    """

    name: str = ""
    refdes_prefix: str = ""
    alphabetic_numbering: int = 0
    is_homogeneous: int = 0
    pcb_lib: str = ""
    pcb_footprint: str = ""
    view_ref: str = ""
    display_props: list[SymbolDisplayProp] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class OLBDeviceData:
    """OLB Device (Type 32) 解析结果 — 单器件引脚定义。"""

    name: str = ""
    pin_count: int = 0
    pins: list[PinDef] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class NormalViewGraphic:
    """NormalView 中的单个图形元素。

    支持: Line, Ellipse, Arc, Polygon, Rectangle。
    """

    graphic_type: int = OLBStructureType.NONE
    # Line / Rectangle
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    # Ellipse
    cx: int = 0
    cy: int = 0
    rx: int = 0
    ry: int = 0
    # Arc
    start_angle: float = 0.0
    end_angle: float = 0.0
    # Polygon
    points: list[tuple[int, int]] = field(default_factory=list)
    # Common
    line_width: int = 0
    color: int = 0


@dataclass
class NormalViewData:
    """NormalView 符号图形解析结果。"""

    lib_part_name: str = ""
    graphics: list[NormalViewGraphic] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)  # x1,y1,x2,y2
    pin_name_visible: bool = True
    pin_number_visible: bool = True


# ── 二进制结构体解析函数 ──────────────────────────────────────────────────


def parse_olb_package(reader: BinaryReader) -> OLBPackageData:
    """解析 OLB Package 结构体 (Type 31)。

    OLB Package 流的结构与 DSN 中的 Package 不同：
    - 前面有 32 字节的索引头（4 个 8 字节块）
    - 之后才是标准的 preamble + string 结构

    实际二进制布局:
        [32-byte header: 4 × (uint16 type, uint16, uint32 value)]
        preamble (8B): FF E4 5C 39 + uint32(0)
        name: uint16(str_len) + str_len bytes + NUL  ← same as RTL format
        view_ref: uint16(str_len) + str_len bytes + NUL
        rest: remaining structure data

    Args:
        reader: 定位到结构体起始位置的 BinaryReader。

    Returns:
        OLBPackageData 实例。
    """
    # ── Skip 32-byte OLB header ────────────────────────────────────
    # OLB Package streams start with a 32-byte index header:
    #   4 entries of { uint16 type, uint16 unknown, uint32 value }
    # The last entry has type=0xFF, value=-1 (terminator)
    # We skip this header by seeking to the preamble.
    _skip_olb_header(reader)

    # ── Now at preamble ────────────────────────────────────────────
    future_data = FutureDataList(reader)  # empty — header already consumed

    dsn_format = read_preamble(reader)
    # OLB packages use RTL-format strings (uint16 length prefix)
    future_data.checkpoint()

    # ── Package name ───────────────────────────────────────────────
    name: str = ""
    if reader.remaining() >= 2:
        name_len = reader.read_uint16()
        if 0 < name_len <= 200 and name_len <= reader.remaining():
            name = reader.read_bytes(name_len).decode("latin-1", errors="replace")
            # Skip NUL terminator
            if reader.remaining() >= 1 and reader.peek(1)[0] == 0:
                reader.skip(1)

    # ── View/LibPart reference ─────────────────────────────────────
    view_ref: str = ""
    if reader.remaining() >= 2:
        view_len = reader.read_uint16()
        if 0 < view_len <= 200 and view_len <= reader.remaining():
            view_ref = reader.read_bytes(view_len).decode("latin-1", errors="replace")
            if reader.remaining() >= 1 and reader.peek(1)[0] == 0:
                reader.skip(1)

    # ── Extract refdes prefix from name ────────────────────────────
    # e.g., "CAP NP" → "C", "14x2PIN" → "J", "8P4R_0" → "R"
    refdes_prefix = _infer_refdes_prefix(name)

    # ── Skip remaining structure data ──────────────────────────────
    future_data.checkpoint()
    future_data.read_rest_of_structure()

    return OLBPackageData(
        name=name,
        refdes_prefix=refdes_prefix,
        view_ref=view_ref,
    )


def _skip_olb_header(reader: BinaryReader) -> None:
    """跳过 OLB Package 流的 32 字节索引头，定位到 preamble。

    OLB 头格式（4 个条目，每个 8 字节）:
        uint16 type, uint16 unknown, uint32 value
    最后一个条目: type=0x06, value=0xFFFF (终止标记)
    有些变体: type=0x3b/0x3d/etc.

    我们扫描寻找 preamble magic (FF E4 5C 39)。
    """
    start = reader.tell()
    end = min(start + 128, reader._size)

    for i in range(start, end - 4):
        if (reader._buf[i] == 0xFF and reader._buf[i + 1] == 0xE4
                and reader._buf[i + 2] == 0x5C and reader._buf[i + 3] == 0x39):
            reader.seek(i)
            return

    # No preamble found — reset and let caller handle error
    reader.seek(start)


def _infer_refdes_prefix(name: str) -> str:
    """从器件名称推断位号前缀。

    常见规则:
        - R, RES, RESISTOR → "R"
        - C, CAP, CAPACITOR → "C"
        - L, IND, INDUCTOR → "L"
        - D, DIODE → "D"
        - J, CONN, HEADER → "J"
        - U, IC → "U"
        - Q, TRANSISTOR → "Q"
        - 其他 → name 首字母（如果为大写）

    Args:
        name: 器件名称。

    Returns:
        推断的位号前缀。
    """
    name_upper = name.upper().strip()

    # Direct matches for common prefixes in name
    prefix_map: dict[str, str] = {
        "RES": "R", "RESISTOR": "R", "R_": "R",
        "CAP": "C", "CAPACITOR": "C", "C_": "C",
        "IND": "L", "INDUCTOR": "L",
        "DIODE": "D", "D_": "D",
        "LED": "D",
        "CONN": "J", "HEADER": "J",
        "CRYSTAL": "Y", "XTAL": "Y",
        "TRANS": "Q",
        "MP": "U", "APW": "U", "V": "U",
        "SHORT": "TP",
    }

    for key, prefix in prefix_map.items():
        if name_upper.startswith(key):
            return prefix

    # Check if name starts with a standard refdes prefix
    if name and name[0].isalpha() and name[0].isupper():
        return name[0]

    return "U"


def parse_olb_device(reader: BinaryReader) -> OLBDeviceData:
    """解析 OLB Device 结构体 (Type 32) — 器件引脚定义。

    Device 结构体包含器件的引脚映射 (pinMap)。
    二进制布局（推测，基于 openOrCadParser Device.cpp）:
        preamble (8B)
        name_or_id: string
        [header fields]
        pin_count: uint16
        [for each pin]:
            pin_number: string / uint16
            pin_name: string
            pin_type: uint32
        ...

    Args:
        reader: 定位到结构体起始位置的 BinaryReader。

    Returns:
        OLBDeviceData 包含所有引脚定义。
    """
    future_data = FutureDataList(reader)
    props = auto_read_prefixes(reader, future_data, None)

    dsn_format = read_preamble(reader)
    future_data.checkpoint()

    # ── Name ────────────────────────────────────────────────────────
    name: str = ""
    if dsn_format == "rtl":
        name_len = reader.read_uint16()
        if 0 < name_len <= 200:
            name = reader.read_bytes(name_len).decode("latin-1")
            reader.skip(1)
    else:
        name = reader.read_string_len_zero_term()

    # ── Pin count ───────────────────────────────────────────────────
    pin_count: int = 0
    pins: list[PinDef] = []

    # Device structure has a variable layout.
    # Strategy: read until we find a uint16 that looks like a pin count,
    # then parse that many pin entries.
    _parse_device_pins(reader, dsn_format, pins)

    # Try to read pin_count from remaining header
    if not pins:
        try:
            pin_count = reader.read_uint16()
            if 0 < pin_count <= 2000:
                _parse_device_pin_list(reader, dsn_format, pin_count, pins)
        except BinaryReadError:
            pass

    future_data.checkpoint()
    future_data.read_rest_of_structure()

    return OLBDeviceData(
        name=name,
        pin_count=len(pins),
        pins=pins,
        properties={pp.name: pp.value for pp in props},
    )


def _parse_device_pins(
    reader: BinaryReader,
    dsn_format: str,
    pins: list[PinDef],
) -> None:
    """尝试从 Device 流中提取引脚定义。

    使用启发式方法：扫描寻找看起来像引脚号的模式（小正整数）。

    Args:
        reader: 二进制读取器。
        dsn_format: DSN 格式标识 ("rtl" 或 "standard")。
        pins: 输出引脚列表（原地修改）。
    """
    # Device pins use the same general layout:
    # Each pin: pin_number (uint16 or string), pin_name (string), pin_type (uint32)
    #
    # We use a scanning approach: iterate through the remaining data
    # looking for patterns that match pin definitions.

    remaining = reader.remaining()
    if remaining < 8:
        return

    start_pos = reader.tell()
    buf_end = reader._size

    # Scan for pin entries using heuristics
    # Pin number candidates: uint16 values in range 1-2000
    i = reader.tell()
    pin_entries_found = 0

    while i < buf_end - 4:
        # Read potential pin number
        try:
            reader.seek(i)
            pin_num_raw = reader.read_uint16()
            # Valid pin numbers are 1-2000
            if 1 <= pin_num_raw <= 2000:
                # Try to read pin name (next field should be a valid string)
                pos_after_num = reader.tell()
                try:
                    if dsn_format == "rtl":
                        name_len = reader.read_uint16()
                        if 0 < name_len <= 100:
                            pin_name_bytes = reader.read_bytes(name_len)
                            pin_name = pin_name_bytes.decode("latin-1", errors="replace")
                            reader.skip(1)  # NUL
                        else:
                            i += 2
                            continue
                    else:
                        pin_name = reader.read_string_len_zero_term()

                    if pin_name and len(pin_name) <= 100:
                        # Try to read pin type
                        try:
                            pin_type_val = reader.read_uint32()
                            pin_type = _map_olb_pin_type(pin_type_val)
                        except BinaryReadError:
                            pin_type = ElectricalType.PASSIVE

                        pins.append(PinDef(
                            number=str(pin_num_raw),
                            name=pin_name,
                            type=pin_type,
                        ))
                        pin_entries_found += 1
                        i = reader.tell()
                        continue
                except (BinaryReadError, UnicodeDecodeError):
                    pass
            i += 2
        except BinaryReadError:
            break

    reader.seek(start_pos)  # Reset position
    logger.debug("Scanned %d potential pin entries", pin_entries_found)


def _parse_device_pin_list(
    reader: BinaryReader,
    dsn_format: str,
    pin_count: int,
    pins: list[PinDef],
) -> None:
    """解析已知数量的引脚列表。

    Args:
        reader: 二进制读取器。
        dsn_format: DSN 格式标识。
        pin_count: 期望的引脚数量。
        pins: 输出引脚列表（原地修改）。
    """
    for _ in range(min(pin_count, 2000)):
        try:
            # Pin number (uint16)
            pin_num = reader.read_uint16()
            if not (1 <= pin_num <= 2000):
                break

            # Pin name
            if dsn_format == "rtl":
                name_len = reader.read_uint16()
                if not (0 < name_len <= 100):
                    break
                pin_name = reader.read_bytes(name_len).decode("latin-1", errors="replace")
                reader.skip(1)  # NUL
            else:
                pin_name = reader.read_string_len_zero_term()

            if not pin_name:
                break

            # Pin type (uint32)
            pin_type_val = reader.read_uint32()
            pin_type = _map_olb_pin_type(pin_type_val)

            pins.append(PinDef(
                number=str(pin_num),
                name=pin_name,
                type=pin_type,
            ))
        except BinaryReadError:
            break


def _map_olb_pin_type(type_val: int) -> ElectricalType:
    """将 OLB 原始引脚类型值映射到统一的 ElectricalType。

    OLB 引脚类型值（来自 OrCAD 内部枚举）:
        0  = INPUT
        1  = OUTPUT
        2  = BIDIR
        3  = POWER
        4  = GROUND
        5  = PASSIVE
        6  = NC
        7  = TRI_STATE
        8  = OPEN_COLLECTOR
        9  = OPEN_EMITTER
        10 = 3-STATE

    Args:
        type_val: 原始类型值。

    Returns:
        ElectricalType 枚举值。
    """
    mapping: dict[int, ElectricalType] = {
        0: ElectricalType.INPUT,
        1: ElectricalType.OUTPUT,
        2: ElectricalType.BIDIR,
        3: ElectricalType.POWER,
        4: ElectricalType.GROUND,
        5: ElectricalType.PASSIVE,
        6: ElectricalType.NC,
        7: ElectricalType.TRI_STATE,
        8: ElectricalType.OPEN_COLLECTOR,
    }
    return mapping.get(type_val, ElectricalType.PASSIVE)


# ── NormalView 解析 ───────────────────────────────────────────────────────


def parse_normal_view(reader: BinaryReader, lib_part_name: str = "") -> NormalViewData:
    """解析 NormalView 符号图形流。

    NormalView 包含器件的符号图形定义:
        - Line (线段)
        - Ellipse (椭圆/圆)
        - Arc (弧线)
        - Polygon (多边形)
        - Rectangle (矩形)

    二进制布局（推测）:
        preamble (8B)
        [graphic elements loop]:
            element_type: uint8/uint16
            [element-specific data]
        ...

    Args:
        reader: 定位到 NormalView 流起始位置的 BinaryReader。
        lib_part_name: 符号部件名称。

    Returns:
        NormalViewData 包含所有图形元素。
    """
    result = NormalViewData(lib_part_name=lib_part_name)

    try:
        read_preamble(reader)
    except BinaryReadError:
        logger.debug("NormalView '%s': no preamble found", lib_part_name)
        return result

    # ── Parse graphic elements ──────────────────────────────────────
    _parse_graphic_elements(reader, result)

    return result


def _parse_graphic_elements(reader: BinaryReader, result: NormalViewData) -> None:
    """从 NormalView 流中解析图形元素序列。

    扫描流中的图形类型标记并解析对应的几何数据。

    Args:
        reader: 定位到图形数据起始位置的 BinaryReader。
        result: NormalViewData 实例（原地修改）。
    """
    max_elements = 5000
    for _ in range(max_elements):
        if reader.remaining() < 4:
            break

        pos = reader.tell()
        try:
            elem_type = reader.read_uint8()

            if elem_type == OLBStructureType.NONE:
                continue

            graphic = _parse_single_graphic(reader, elem_type)
            if graphic is not None:
                result.graphics.append(graphic)

                # Track bounding box
                if graphic.x1 or graphic.y1 or graphic.x2 or graphic.y2:
                    min_x = min(graphic.x1, graphic.x2)
                    max_x = max(graphic.x1, graphic.x2)
                    min_y = min(graphic.y1, graphic.y2)
                    max_y = max(graphic.y1, graphic.y2)
                    bbox = result.bbox
                    if bbox == (0, 0, 0, 0):
                        result.bbox = (min_x, min_y, max_x, max_y)
                    else:
                        result.bbox = (
                            min(bbox[0], min_x),
                            min(bbox[1], min_y),
                            max(bbox[2], max_x),
                            max(bbox[3], max_y),
                        )
        except BinaryReadError:
            reader.seek(pos + 1)
            continue
        except Exception:
            break


def _parse_single_graphic(
    reader: BinaryReader, elem_type: int
) -> NormalViewGraphic | None:
    """解析单个图形元素。

    Args:
        reader: 二进制读取器。
        elem_type: 图形元素类型。

    Returns:
        NormalViewGraphic 或 None。
    """
    if elem_type == OLBStructureType.LINE:
        return _parse_graphic_line(reader)
    elif elem_type == OLBStructureType.ELLIPSE:
        return _parse_graphic_ellipse(reader)
    elif elem_type == OLBStructureType.ARC:
        return _parse_graphic_arc(reader)
    elif elem_type == OLBStructureType.POLYGON:
        return _parse_graphic_polygon(reader)
    elif elem_type == OLBStructureType.RECTANGLE:
        return _parse_graphic_rectangle(reader)
    elif elem_type == OLBStructureType.POLYLINE:
        return _parse_graphic_polygon(reader)  # Same layout as polygon
    elif elem_type == OLBStructureType.BEZIER:
        return _parse_graphic_bezier(reader)
    elif elem_type == OLBStructureType.TEXT:
        return _parse_graphic_text(reader)
    else:
        # Unknown type — skip a reasonable amount
        skip = min(reader.remaining(), 64)
        reader.skip(skip)
        return None


def _parse_graphic_line(reader: BinaryReader) -> NormalViewGraphic:
    """解析 LINE 图形元素。

    布局: uint8(type) int16(x1) int16(y1) int16(x2) int16(y2) uint16(color) uint16(width)
    """
    try:
        x1 = reader.read_int16()
        y1 = reader.read_int16()
        x2 = reader.read_int16()
        y2 = reader.read_int16()
        color = reader.read_uint16()
        line_width = reader.read_uint16()
    except BinaryReadError:
        # Minimal fallback
        reader.skip(max(0, reader.remaining() - 2))
        return NormalViewGraphic(graphic_type=OLBStructureType.LINE)

    return NormalViewGraphic(
        graphic_type=OLBStructureType.LINE,
        x1=x1, y1=y1, x2=x2, y2=y2,
        color=color, line_width=line_width,
    )


def _parse_graphic_ellipse(reader: BinaryReader) -> NormalViewGraphic:
    """解析 ELLIPSE 图形元素。

    布局: uint8(type) int16(cx) int16(cy) int16(rx) int16(ry) uint16(color) uint16(width)
    """
    try:
        cx = reader.read_int16()
        cy = reader.read_int16()
        rx = reader.read_int16()
        ry = reader.read_int16()
        color = reader.read_uint16()
        line_width = reader.read_uint16()
    except BinaryReadError:
        reader.skip(max(0, reader.remaining() - 2))
        return NormalViewGraphic(graphic_type=OLBStructureType.ELLIPSE)

    return NormalViewGraphic(
        graphic_type=OLBStructureType.ELLIPSE,
        cx=cx, cy=cy, rx=rx, ry=ry,
        x1=cx - rx, y1=cy - ry, x2=cx + rx, y2=cy + ry,
        color=color, line_width=line_width,
    )


def _parse_graphic_arc(reader: BinaryReader) -> NormalViewGraphic:
    """解析 ARC 图形元素。

    布局: uint8(type) int16(cx) int16(cy) int16(r) float(start_angle) float(end_angle) uint16(color) uint16(width)
    """
    import struct as _struct

    try:
        cx = reader.read_int16()
        cy = reader.read_int16()
        radius = reader.read_int16()
        # Angles stored as floats (4 bytes each, little-endian)
        start_angle_bytes = reader.read_bytes(4)
        end_angle_bytes = reader.read_bytes(4)
        start_angle = _struct.unpack("<f", start_angle_bytes)[0]
        end_angle = _struct.unpack("<f", end_angle_bytes)[0]
        color = reader.read_uint16()
        line_width = reader.read_uint16()
    except (BinaryReadError, _struct.error):
        reader.skip(max(0, reader.remaining() - 2))
        return NormalViewGraphic(graphic_type=OLBStructureType.ARC)

    return NormalViewGraphic(
        graphic_type=OLBStructureType.ARC,
        cx=cx, cy=cy,
        x1=cx - radius, y1=cy - radius,
        x2=cx + radius, y2=cy + radius,
        start_angle=start_angle, end_angle=end_angle,
        color=color, line_width=line_width,
    )


def _parse_graphic_polygon(reader: BinaryReader) -> NormalViewGraphic:
    """解析 POLYGON/POLYLINE 图形元素。

    布局: uint8(type) uint16(n_points) [int16(x) int16(y)]*n_points uint16(color) uint16(width)
    """
    try:
        n_points = reader.read_uint16()
        if n_points > 500:
            reader._pos -= 2
            return NormalViewGraphic(graphic_type=OLBStructureType.POLYGON)

        points: list[tuple[int, int]] = []
        for _ in range(n_points):
            x = reader.read_int16()
            y = reader.read_int16()
            points.append((x, y))

        color = reader.read_uint16()
        line_width = reader.read_uint16()
    except BinaryReadError:
        reader.skip(max(0, reader.remaining() - 2))
        return NormalViewGraphic(graphic_type=OLBStructureType.POLYGON)

    return NormalViewGraphic(
        graphic_type=OLBStructureType.POLYGON,
        points=points,
        color=color, line_width=line_width,
    )


def _parse_graphic_rectangle(reader: BinaryReader) -> NormalViewGraphic:
    """解析 RECTANGLE 图形元素。

    布局: uint8(type) int16(x1) int16(y1) int16(x2) int16(y2) uint16(color) uint16(width) uint16(fill)
    """
    try:
        x1 = reader.read_int16()
        y1 = reader.read_int16()
        x2 = reader.read_int16()
        y2 = reader.read_int16()
        color = reader.read_uint16()
        line_width = reader.read_uint16()
        # Fill flag (may or may not be present)
        if reader.remaining() >= 2:
            reader.read_uint16()  # fill
    except BinaryReadError:
        reader.skip(max(0, reader.remaining() - 2))
        return NormalViewGraphic(graphic_type=OLBStructureType.RECTANGLE)

    return NormalViewGraphic(
        graphic_type=OLBStructureType.RECTANGLE,
        x1=x1, y1=y1, x2=x2, y2=y2,
        color=color, line_width=line_width,
    )


def _parse_graphic_bezier(reader: BinaryReader) -> NormalViewGraphic:
    """解析 BEZIER 图形元素。

    贝塞尔曲线使用与控制点相同的布局: n_points + points[].
    """
    return _parse_graphic_polygon(reader)


def _parse_graphic_text(reader: BinaryReader) -> NormalViewGraphic:
    """解析 TEXT 图形元素（简化）。

    TEXT 元素包含坐标和字符串表索引。
    """
    try:
        x = reader.read_int16()
        y = reader.read_int16()
        # Skip remaining text metadata (variable length)
        # Text has name_idx, font, rotation, color, etc.
        reader.skip(min(reader.remaining(), 20))
    except BinaryReadError:
        pass

    return NormalViewGraphic(
        graphic_type=OLBStructureType.TEXT,
        x1=x if "x" in dir() else 0,
        y1=y if "y" in dir() else 0,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  OLBParser
# ═══════════════════════════════════════════════════════════════════════════


class OLBParser(ParserBase):
    """OLB 库文件解析器 — 将 .olb 文件解析为 DesignIR（ComponentDef 集合）。

    OLB 是 OrCAD Capture 的器件库文件。与 DSN 不同，OLB 不包含页面和网络，
    而是包含 Package 定义（器件元数据）和符号图形。

    OLB → DesignIR 映射:
        Package → ComponentDef (library_id = package_name)
        Device  → ComponentDef.pins (pinMap)
        NormalView → ComponentDef.symbols (graphics dict)

    Usage:
        parser = OLBParser()
        ir = parser.parse(Path("mylib.olb"))
        for comp in ir.component_db.all_components:
            print(comp.library_id, comp.pin_count)
    """

    FORMAT_NAME = "CIS_OLB"
    FILE_EXTENSIONS = [".olb", ".OLB"]

    def parse(self, olb_path: Path) -> DesignIR:
        """解析 OLB 库文件。

        Args:
            olb_path: .olb 文件路径。

        Returns:
            DesignIR，其 component_db 包含所有器件的 ComponentDef。

        Raises:
            CIS2HDLParseError: 解析失败。
        """
        logger.info("Parsing OLB library: %s", olb_path)

        try:
            reader = OLBOleReader(olb_path)
        except Exception as exc:
            raise CIS2HDLParseError(
                f"Failed to open OLB file: {exc}",
                file_path=str(olb_path),
            ) from exc

        # ── 1. List packages ────────────────────────────────────────
        package_names = reader.list_packages()
        if not package_names:
            # Try raw directory entries as fallback
            raw_dirs = reader.list_raw_dir_entries()
            package_names = [
                e.name for e in raw_dirs
                if e.dir_type == 1 and "Package" in e.full_path
            ]
            logger.info(
                "No packages via tree; raw scan found %d storage entries",
                len(package_names),
            )

        logger.info("Discovered %d package(s) in OLB", len(package_names))

        # ── 2. Build DesignIR ───────────────────────────────────────
        project_name = olb_path.stem
        design = DesignIR(project_name=project_name, source_format="CIS_OLB")

        for pkg_name in package_names:
            try:
                comp_def = self._parse_single_package(reader, pkg_name)
                if comp_def is not None:
                    design.component_db.add(comp_def)
            except Exception as exc:
                logger.error(
                    "Failed to parse package '%s' in %s: %s",
                    pkg_name, olb_path.name, exc,
                )
                continue

        # ── 3. Metadata ─────────────────────────────────────────────
        design.metadata["source_file"] = str(olb_path)
        design.metadata["package_count"] = len(package_names)
        design.metadata["component_count"] = len(design.component_db)
        design.metadata["format"] = "CIS_OLB"

        # List all symbols for metadata
        try:
            symbols = reader.list_symbols()
            design.metadata["symbol_count"] = len(symbols)
        except Exception:
            design.metadata["symbol_count"] = 0

        logger.info(
            "OLB parse complete: %d package(s), %d component(s)",
            len(package_names),
            len(design.component_db),
        )

        return design

    # ── Single package parsing ──────────────────────────────────────

    def _parse_single_package(
        self,
        reader: OLBOleReader,
        pkg_name: str,
    ) -> ComponentDef | None:
        """解析单个 Package（含 Device 和 NormalView）。

        Args:
            reader: OLBOleReader 实例。
            pkg_name: Package 名称。

        Returns:
            ComponentDef 或 None（解析失败时）。
        """
        # ── Parse Package stream (Type 31) ──────────────────────────
        try:
            pkg_buffer = reader.read_package_stream(pkg_name)
        except Exception:
            logger.debug("Package stream not found for '%s'", pkg_name)
            return None

        br = BinaryReader(pkg_buffer)
        pkg_data = parse_olb_package(br)

        # ── Parse Device stream (Type 32) ───────────────────────────
        device_data: OLBDeviceData | None = None
        try:
            dev_buffer = reader.read_device_stream(pkg_name)
            br_dev = BinaryReader(dev_buffer)
            device_data = parse_olb_device(br_dev)
        except Exception:
            logger.debug("Device stream not found for '%s'", pkg_name)

        # ── Build ComponentDef ──────────────────────────────────────
        # Try to find the symbol/libpart name associated with this package
        lib_part_name = self._resolve_lib_part_name(reader, pkg_name, pkg_data)

        comp_def = ComponentDef(
            library_id=pkg_data.name or pkg_name,
            part_name=pkg_data.name or pkg_name,
            footprint=pkg_data.pcb_footprint,
            source_format="CIS_OLB",
            source_file=pkg_name,
        )

        # Properties
        for k, v in pkg_data.properties.items():
            if k.lower() == "value":
                comp_def.value = v
            elif k.lower() == "mpn" or k.lower() == "part number":
                comp_def.mpn = v
            elif k.lower() == "description":
                comp_def.description = v

        # Pins from Device
        if device_data is not None and device_data.pins:
            comp_def.pins = device_data.pins
            comp_def.pin_count = len(device_data.pins)

        # Symbol graphics from NormalView
        if lib_part_name:
            try:
                nv_buffer = reader.read_normal_view(lib_part_name)
                br_nv = BinaryReader(nv_buffer)
                nv_data = parse_normal_view(br_nv, lib_part_name)
                if nv_data.graphics:
                    comp_def.symbols.append({
                        "lib_part": lib_part_name,
                        "graphics_count": len(nv_data.graphics),
                        "bbox": list(nv_data.bbox),
                        "graphics": [
                            {
                                "type": g.graphic_type,
                                "x1": g.x1, "y1": g.y1,
                                "x2": g.x2, "y2": g.y2,
                            }
                            for g in nv_data.graphics
                        ],
                    })
            except Exception:
                logger.debug(
                    "NormalView not found for '%s' (lib_part='%s')",
                    pkg_name, lib_part_name,
                )

        return comp_def

    # ── LibPart name resolution ─────────────────────────────────────

    @staticmethod
    def _resolve_lib_part_name(
        reader: OLBOleReader,
        pkg_name: str,
        pkg_data: OLBPackageData,
    ) -> str | None:
        """解析 Package 对应的 LibPart 名称。

        策略:
        1. 使用 view_ref（从 Package 流中解析的 NormalView 引用）
        2. 查找与 Package 同名的 Symbol
        3. 查找名称包含 Package 名称的 Symbol

        Args:
            reader: OLBOleReader 实例。
            pkg_name: Package 名称。
            pkg_data: 解析后的 Package 数据。

        Returns:
            LibPart 名称，或 None。
        """
        # If view_ref was parsed from the stream (e.g. "8P4R_0.Normal"),
        # extract the base name
        if pkg_data.view_ref:
            base = pkg_data.view_ref.split(".")[0]
            symbols = reader.list_symbols()
            if base in symbols:
                return base
            # Try without extension
            return pkg_data.view_ref.split(".")[0]

        symbols = reader.list_symbols()

        # Exact match
        if pkg_name in symbols:
            return pkg_name

        # Case-insensitive match
        pkg_lower = pkg_name.lower()
        for sym in symbols:
            if sym.lower() == pkg_lower:
                return sym

        # Substring match
        for sym in symbols:
            if pkg_lower in sym.lower() or sym.lower() in pkg_lower:
                return sym

        return None
