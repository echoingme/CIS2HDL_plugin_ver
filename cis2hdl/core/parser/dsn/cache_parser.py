"""Cache stream parser — extract component definitions from OrCAD DSN Cache stream.

The Cache stream contains ALL component definitions for the design:
LibraryParts (pin names) and Packages (pin maps). It is parsed sequentially
from byte 0 to EOF.

Key format details:
- Cache entries use **uint16** length prefix for ALL strings (metadata + structure bodies).
- This differs from Packages/ streams which use uint32 length prefix.
- Header: 2 bytes 0x0000 + 2 bytes unknown = 4 bytes total.

Reference:
    OpenOrCadParser: src/Streams/StreamCache.cpp
    universal-netlist: src/parsers/cadence/dsn/cache-parser.ts
    dsn-format.md §10
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .binary_reader import BinaryReader, BinaryReadError
from .structures import (
    FutureDataList,
    PREAMBLE_MAGIC,
    StructureType,
    parse_symbol_display_props,
)
from ...ir.component import ComponentDef, PinDef, ElectricalType

logger = logging.getLogger(__name__)


# ============================================================
#  Cache-specific string reader (uint16 length prefix)
# ============================================================
# The Cache stream's metadata section uses uint16 length-prefixed
# strings matching the DSN format spec §3.1:
#     uint16   length       # byte count of string content (not including null)
#     char[]   content      # length bytes
#     uint8    0x00         # null terminator
#
# This differs from read_string_len_zero_term() (uint32) used in
# structure body parsing. The uint32 variant only works via its
# fallback-to-null-terminated mechanism when the uint32 value
# exceeds remaining() — but in Cache metadata, the 0x00 high byte
# of the uint16 length causes the fallback to read truncated strings.
# Hence we use a dedicated uint16 reader here.


def _read_cache_string(reader: BinaryReader) -> str:
    """Read a uint16-length-prefixed null-terminated string (Cache metadata).

    Format:
        uint16  length    # content length, NOT including null
        char[]  content   # length bytes
        uint8   NUL       # 0x00

    Returns:
        Decoded string (empty string if length == 0).
    """
    length = reader.read_uint16()
    if length == 0:
        reader.skip(1)  # skip the null terminator
        return ""
    if length > reader.remaining():
        raise BinaryReadError(
            f"Cache string length {length} exceeds remaining {reader.remaining()}",
            position=reader.tell(),
        )
    result = reader.read_bytes(length).decode("latin-1")
    reader.skip(1)  # null terminator
    return result


# ============================================================
#  Internal: Standard Prefix Chain Parser
# ============================================================
# Implements the standard DSN prefix chain format used in Cache and
# Packages streams (long prefixes: 1+4+4 bytes; short prefix: 1+2+8N bytes).
# This is the same format as OpenOrCadParser GenericParser.cpp and
# universal-netlist generic-parser.ts.
#
# NOTE: These functions use a DIFFERENT prefix format than the
# auto_read_prefixes in structures.py (which reads uint32-size chunks).
# The Cache/Packages structure bodies use the standard prefix chain,
# so we implement our own reader here rather than modifying structures.py.

_LONG_PREFIX_SIZE = 9  # type(uint8) + byte_offset(uint32) + unknown(uint32)


def _read_long_prefix(reader: BinaryReader) -> tuple[int, int]:
    """Read a long prefix: type(uint8) + byte_offset(uint32) + unknown(uint32).

    Returns:
        (type_id, byte_offset) where byte_offset is relative to the end
        of the 9-byte header and defines the checkpoint boundary.
    """
    type_id = reader.read_uint8()
    byte_offset = reader.read_uint32()
    reader.skip(4)  # unknown (usually 0x00000000)
    return type_id, byte_offset


def _read_short_prefix(reader: BinaryReader) -> tuple[int, list[tuple[int, int]]]:
    """Read a short (final) prefix: type(uint8) + count(int16) + pairs.

    Each pair is (name_idx: uint32, val_idx: uint32) into the Library strLst.
    If count < 0, there are no pairs.

    Returns:
        (type_id, list of (name_idx, val_idx) pairs).
    """
    type_id = reader.read_uint8()
    count = reader.read_int16()
    props: list[tuple[int, int]] = []
    if count >= 0:
        for _ in range(count):
            name_idx = reader.read_uint32()
            val_idx = reader.read_uint32()
            props.append((name_idx, val_idx))
    return type_id, props


def _auto_read_prefixes(
    reader: BinaryReader,
    future_data: FutureDataList,
    expected_type: int | None = None,
) -> tuple[int, list[tuple[int, int]]]:
    """Auto-detect prefix count by trying 10 down to 1.

    The first N-1 prefixes are long, the last is short. All must share
    the same type ID. The first count that parses without error wins.

    Args:
        reader: BinaryReader positioned at start of prefix chain.
        future_data: FutureDataList to populate with checkpoint boundaries.
        expected_type: If set, validates the detected type matches.

    Returns:
        (detected_type_id, list of (name_idx, val_idx) properties).

    Raises:
        BinaryReadError: If no valid prefix count could be found.
    """
    start_offset = reader.tell()

    # Save the current stops so we can restore on failed attempts
    saved_stops = list(future_data._stops)  # type: ignore[attr-defined]

    for prefix_count in range(10, 0, -1):
        reader.seek(start_offset)
        # Restore stops to clean state before each attempt
        future_data._stops[:] = saved_stops  # type: ignore[attr-defined]
        try:
            first_type: int | None = None
            props: list[tuple[int, int]] = []

            for i in range(prefix_count):
                preamble_offset = reader.tell()
                if i == prefix_count - 1:
                    type_id, props = _read_short_prefix(reader)
                else:
                    type_id, byte_offset = _read_long_prefix(reader)
                    # Push boundary: absolute stop = preamble + 9 + byte_offset
                    future_data.push(preamble_offset, _LONG_PREFIX_SIZE + byte_offset)

                if first_type is None:
                    first_type = type_id
                elif type_id != first_type:
                    raise BinaryReadError(
                        f"Prefix type mismatch: {first_type} vs {type_id}",
                        position=reader.tell(),
                    )

            # Validate expected type
            if expected_type is not None and first_type != expected_type:
                raise BinaryReadError(
                    f"Expected type {expected_type}, got {first_type}",
                    position=reader.tell(),
                )

            return first_type, props
        except (BinaryReadError, Exception):
            pass  # try next count

    raise BinaryReadError(
        f"Could not find valid prefix count at offset 0x{start_offset:X}",
        position=start_offset,
    )


def _try_read_preamble(reader: BinaryReader) -> bool:
    """Try to read preamble magic (FF E4 5C 39 + uint32 data_len).

    Silently returns False if magic not present.

    Returns:
        True if preamble was found and consumed.
    """
    start = reader.tell()
    try:
        magic = reader.read_bytes(4)
        if magic == PREAMBLE_MAGIC:
            data_len = reader.read_uint32()
            reader.skip(data_len)
            return True
    except BinaryReadError:
        pass
    reader.seek(start)
    return False


def _skip_structure(reader: BinaryReader) -> None:
    """Skip an unknown structure by reading its prefixes and jumping to end."""
    future_data = FutureDataList(reader)
    _auto_read_prefixes(reader, future_data)
    future_data.read_rest_of_structure()


def _skip_to_next_boundary(future_data: FutureDataList, reader: BinaryReader) -> bool:
    """Skip to the nearest unvisited checkpoint boundary >= current position.

    Returns:
        True if a boundary was found and skipped to.
    """
    pos = reader.tell()
    stops: list[int] = future_data._stops  # type: ignore[attr-defined]
    if not stops:
        return False

    nearest: int | None = None
    for stop in stops:
        if stop >= pos:
            if nearest is None or stop < nearest:
                nearest = stop

    if nearest is None:
        return False
    if nearest > pos:
        reader.skip(nearest - pos)
    return True


def _dump_hex_context(reader: BinaryReader, context_bytes: int, label: str) -> None:
    """Dump hex context around the current reader position for debugging.

    Prints a hex dump of the reader buffer centred on the current position:
    ``context_bytes`` total, split evenly before and after.

    Args:
        reader: BinaryReader positioned at the point of interest.
        context_bytes: Total number of bytes to dump (evenly split before/after).
        label: Human-readable label for the log entry.
    """
    half: int = context_bytes // 2
    pos: int = reader.tell()
    buf: bytes = reader._buf  # type: ignore[attr-defined]

    start: int = max(0, pos - half)
    end: int = min(len(buf), pos + half)

    hex_str: str = " ".join(f"{b:02X}" for b in buf[start:end])
    ascii_str: str = "".join(
        chr(b) if 32 <= b < 127 else "." for b in buf[start:end]
    )

    logger.warning(
        "%s @ 0x%X: [%s] |%s|",
        label, pos, hex_str, ascii_str,
    )


# ============================================================
#  Structure Parsers (standard DSN structures)
# ============================================================


@dataclass
class _SymbolPin:
    """Internal: parsed SymbolPin from LibraryPart."""
    name: str


@dataclass
class _Device:
    """Internal: parsed Device from Package."""
    unit_ref: str
    ref_des: str
    pin_map: list[str | None]  # physical pin numbers, None for skipped entries


@dataclass
class _Package:
    """Internal: parsed Package from Cache."""
    name: str
    ref_des: str
    pcb_footprint: str
    devices: list[_Device] = field(default_factory=list)


@dataclass
class _LibraryPart:
    """Internal: parsed LibraryPart from Cache."""
    name: str
    pin_names: list[str]  # functional pin names
    default_value: str = ""


def _parse_symbol_pin(reader: BinaryReader) -> _SymbolPin:
    """Parse a SymbolPin structure (type 0x1A/0x1B).

    Layout (dsn-format.md §9.4):
        PREFIXES (type 0x1A or 0x1B)
        PREAMBLE
        string  name             # functional pin name (uint32 len prefix)
        int32   start_x
        int32   start_y
        int32   hotpt_x
        int32   hotpt_y
        uint16  pin_shape
        uint16  unknown
        uint32  port_type
        uint32  unknown
        uint16  len_sdps
        SymbolDisplayProp[]
        -- checkpoint --
    """
    future_data = FutureDataList(reader)
    _auto_read_prefixes(reader, future_data)  # accepts SymbolPinScalar (0x1A) or SymbolPinBus (0x1B)
    _try_read_preamble(reader)
    future_data.checkpoint()

    # NOTE: Cache stream structures use uint16-length-prefixed strings
    # (via _read_cache_string), NOT uint32 like Packages/ streams.
    name = _read_cache_string(reader)
    # Skip: start_x(4) + start_y(4) + hotpt_x(4) + hotpt_y(4) +
    #       pin_shape(2) + unknown(2) + port_type(4) + unknown(4) = 28 bytes
    reader.skip(28)

    sdp_count = reader.read_uint16()
    parse_symbol_display_props(reader, sdp_count)

    future_data.checkpoint()
    future_data.read_rest_of_structure()
    return _SymbolPin(name=name)


def _parse_device(reader: BinaryReader) -> _Device:
    """Parse a Device structure (type 0x20).

    Layout (dsn-format.md §9.2):
        PREFIXES (type 0x20)
        PREAMBLE
        string  unit_ref         # uint32 len prefix
        string  ref_des          # uint32 len prefix
        uint16  pin_count
        For each pin:
            peek int16:
            if == -1 (0xFFFF): skip (no entry in pin_map)
            else:
                string  pin_name     # uint32 len prefix
                uint8   pin_config
        -- checkpoint --
    """
    future_data = FutureDataList(reader)
    _auto_read_prefixes(reader, future_data, StructureType.Device)
    _try_read_preamble(reader)
    future_data.checkpoint()

    # NOTE: Cache stream structures use uint16-length-prefixed strings.
    unit_ref = _read_cache_string(reader)
    ref_des = _read_cache_string(reader)

    pin_count = reader.read_uint16()
    pin_map: list[str | None] = []

    for _ in range(pin_count):
        str_len = reader.read_int16()
        if str_len == -1:
            # no entry in pin_map
            pin_map.append(None)
            continue
        # Put back the 2 bytes (they're the uint16 string length prefix)
        reader.seek(reader.tell() - 2)
        pin_name = _read_cache_string(reader)
        reader.skip(1)  # pin_config (bit 7=pin_ignore, bits 6-0=pin_group)
        pin_map.append(pin_name)

    future_data.checkpoint()
    future_data.read_rest_of_structure()
    return _Device(unit_ref=unit_ref, ref_des=ref_des, pin_map=pin_map)


def _parse_package(reader: BinaryReader) -> _Package:
    """Parse a Package structure (type 0x1F).

    Layout (dsn-format.md §9.1):
        PREFIXES (type 0x1F)
        PREAMBLE
        string  name             # uint32 len prefix
        string  source_library   # discard
        -- checkpoint --
        string  ref_des          # uint32 len prefix
        string  unknown_str1     # discard
        string  pcb_footprint    # uint32 len prefix
        uint16  len_devices
        Device[] sub-records
        -- checkpoint --
    """
    future_data = FutureDataList(reader)
    _auto_read_prefixes(reader, future_data, StructureType.Package)
    _try_read_preamble(reader)
    future_data.checkpoint()

    # NOTE: Cache stream structures use uint16-length-prefixed strings.
    name = _read_cache_string(reader)
    _read_cache_string(reader)  # source_library (discard)
    future_data.checkpoint()

    ref_des = _read_cache_string(reader)
    _read_cache_string(reader)  # unknown_str1 (discard)
    pcb_footprint = _read_cache_string(reader)

    len_devices = reader.read_uint16()
    devices: list[_Device] = []
    for _ in range(len_devices):
        devices.append(_parse_device(reader))

    future_data.checkpoint()
    future_data.read_rest_of_structure()
    return _Package(name=name, ref_des=ref_des, pcb_footprint=pcb_footprint, devices=devices)


def _heuristic_scan_symbol_pins(reader: BinaryReader) -> int:
    """Scan forward up to 512 bytes for valid SymbolPin starting patterns.

    When the normal boundary skip fails to position the reader at the
    correct symbol pin area (prefix byte_offset is insufficient for
    certain HG5015 DSN variants), this heuristic scans for sequences
    that look like valid SymbolPin headers.

    A valid SymbolPin starts with type 0x1A or 0x1B (SymbolPinScalar
    or SymbolPinBus), followed by a reasonable prefix chain.

    Args:
        reader: BinaryReader positioned past the _skip_to_next_boundary area.

    Returns:
        Estimated number of symbol pins, or 0 if none found.
    """
    start_pos = reader.tell()
    scan_limit = min(reader.remaining(), 512)

    pin_count = 0
    pos = start_pos
    end_pos = start_pos + scan_limit

    while pos < end_pos - 2:
        reader.seek(pos)
        try:
            b = reader.read_uint8()
            if b in (0x1A, 0x1B):
                # This looks like a SymbolPin type byte.
                # Peek ahead to see if it's followed by reasonable prefix data.
                if reader.remaining() >= 2:
                    next_byte = reader.peek(1)[0]
                    # SymbolPin prefix chain usually starts with 0x1A/0x1B
                    # followed by a 4-byte size or 9-byte long prefix
                    if next_byte in (0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
                        # Looks like a valid short-prefix-count or long-prefix start
                        pin_count += 1
                        pos += 1
                        continue
            pos += 1
        except BinaryReadError:
            pos += 1

    reader.seek(start_pos)
    logger.debug(
        "_heuristic_scan_symbol_pins: found %d candidate pins "
        "in %d bytes at offset 0x%X",
        pin_count, scan_limit, start_pos,
    )
    return pin_count


def _parse_library_part(reader: BinaryReader) -> _LibraryPart:
    """Parse a LibraryPart structure (type 0x18).

    Layout (dsn-format.md §9.3):
        PREFIXES (type 0x18)
        PREAMBLE
        string  name             # uint32 len prefix
        string  source_library   # discard
        -- checkpoint --
        uint32  unknown
        uint16  len_primitives   # skip (non-standard format)
        -- skip to next boundary --
        uint16  len_symbol_pins
        SymbolPin[] sub-records
        uint16  len_sdps
        SymbolDisplayProp[] (skip)
        -- checkpoint --
        (optional) GeneralProperties:
            string  impl_path
            string  impl
            string  ref_des
            string  part_value
            uint8   properties
            uint8   padding
        -- checkpoint --

    For HG5015 DSN variants where the boundary prefix byte_offset does
    not cover the full LibraryPart graphic area, a three-tier approach
    is used:
      1. Normal path — _skip_to_next_boundary → read len_symbol_pins.
      2. Heuristic path — when symbol pins cannot be read correctly,
         scan forward for valid SymbolPin patterns.
      3. Minimal path — when both fail, return empty pin names with a
         warning and use numbered fallback pins.
    """
    future_data = FutureDataList(reader)
    _auto_read_prefixes(reader, future_data, StructureType.LibraryPart)
    _try_read_preamble(reader)
    future_data.checkpoint()

    # NOTE: Cache stream structures use uint16-length-prefixed strings.
    name = _read_cache_string(reader)
    _read_cache_string(reader)  # source_library (discard)
    future_data.checkpoint()

    reader.skip(4)  # unknown

    # Skip graphical primitives (non-standard format)
    reader.read_uint16()  # len_primitives
    if not _skip_to_next_boundary(future_data, reader):
        logger.warning(
            "LibraryPart %s: boundary skip failed at offset 0x%X",
            name, reader.tell(),
        )
        _dump_hex_context(reader, 32, "LibraryPart boundary fail")

    # ── Three-tier pin reading ─────────────────────────────────────
    pin_names: list[str] = []

    # Tier 1: Normal path — read len_symbol_pins
    try:
        len_symbol_pins = reader.read_uint16()
    except (BinaryReadError, Exception):
        len_symbol_pins = 0

    # Tier 1 fallback → Tier 2: heuristic scan
    if len_symbol_pins == 0 or len_symbol_pins > 100:
        logger.debug(
            "LibraryPart %s: suspicious pin count %d at offset 0x%X, "
            "attempting heuristic scan",
            name, len_symbol_pins, reader.tell(),
        )
        heuristic_count = _heuristic_scan_symbol_pins(reader)
        if heuristic_count > 0 and heuristic_count <= 100:
            len_symbol_pins = heuristic_count
        else:
            # Tier 3: Minimal path — return empty pin names
            logger.warning(
                "LibraryPart %s: unable to determine pin count "
                "(normal=%d, heuristic=%d), using minimal fallback",
                name, len_symbol_pins, heuristic_count,
            )
            len_symbol_pins = 0

    for _ in range(len_symbol_pins):
        # 0x00 byte marks a "convert view" pin placeholder.
        try:
            if reader.peek(1)[0] == 0x00:
                reader.skip(1)
                pin_names.append("")
                continue
            pin = _parse_symbol_pin(reader)
            pin_names.append(pin.name)
        except (BinaryReadError, Exception) as exc:
            logger.warning(
                "LibraryPart %s: failed to parse symbol pin %d/%d: %s",
                name, len(pin_names), len_symbol_pins, exc,
            )
            pin_names.append("")
            # Try to skip ahead to next valid position
            try:
                _skip_to_next_boundary(future_data, reader)
            except (BinaryReadError, Exception):
                break

    sdp_count = reader.read_uint16()
    parse_symbol_display_props(reader, sdp_count)

    future_data.checkpoint()

    # Try reading optional GeneralProperties block
    default_value = ""
    try:
        _read_cache_string(reader)  # impl_path
        _read_cache_string(reader)  # impl
        _read_cache_string(reader)  # ref_des
        part_value = _read_cache_string(reader)
        if part_value:
            default_value = part_value
        reader.skip(2)  # properties bitfield + padding
        future_data.checkpoint()
    except (BinaryReadError, Exception):
        # GeneralProperties is optional — silently skip
        pass

    future_data.read_rest_of_structure()
    return _LibraryPart(name=name, pin_names=pin_names, default_value=default_value)


# ============================================================
#  Cache Stream Parser
# ============================================================


@dataclass
class CacheParsedData:
    """Result of parsing the Cache stream.

    Attributes:
        components: ComponentDef list extracted from Cache.
        component_count: Number of components parsed.
        packages: Raw Package structures (for pin map fallback).
        library_parts: Raw LibraryPart structures (for pin name fallback).
    """
    components: list[ComponentDef] = field(default_factory=list)
    component_count: int = 0
    packages: list[_Package] = field(default_factory=list)
    library_parts: list[_LibraryPart] = field(default_factory=list)


def parse_cache_stream(cache_bytes: bytes) -> CacheParsedData:
    """Parse the Cache stream, extracting component definitions.

    The Cache contains all component definitions in a sequential format:
    4-byte header, then entries with variable-length metadata, twin IDs,
    a structure type uint16, and a standard prefix-chain + body structure.

    Args:
        cache_bytes: Raw bytes of the Cache OLE stream.

    Returns:
        CacheParsedData containing extracted ComponentDef objects.
    """
    reader = BinaryReader(cache_bytes)
    packages: list[_Package] = []
    library_parts: list[_LibraryPart] = []
    components: list[ComponentDef] = []

    # ── Empty cache check ─────────────────────────────────────────
    if reader.remaining() <= 10:
        logger.info("Cache stream is empty (%d bytes)", reader.remaining())
        return CacheParsedData(
            components=components, component_count=0,
            packages=packages, library_parts=library_parts,
        )

    # ── Header: 2 zero bytes + 2 unknown bytes ────────────────────
    reader.skip(4)

    # ── Helper: tryRead probe (C++ reference pattern) ─────────────
    def _try_read(fn) -> bool:
        """Probe: run fn, always reset position. Returns True if fn succeeded."""
        saved = reader.tell()
        try:
            fn()
        except (BinaryReadError, Exception):
            reader.seek(saved)
            return False
        reader.seek(saved)
        return True

    # ── Phase 1: Sequential entry parsing ──────────────────────────
    _parse_cache_sequential(reader, cache_bytes, packages, library_parts, components)

    # ── Phase 2: Brute-force preamble recovery ─────────────────────
    # Reset reader to start and scan for any remaining structures.
    reader.seek(0)
    _scan_for_structures(reader, cache_bytes, packages, library_parts, components)

    # ── Post-process: apply LibraryPart pin names ──────────────────
    _apply_all_library_part_pin_names(packages, library_parts, components)

    logger.info(
        "Cache parsed: %d packages, %d library_parts, %d components",
        len(packages), len(library_parts), len(components),
    )
    return CacheParsedData(
        components=components,
        component_count=len(components),
        packages=packages,
        library_parts=library_parts,
    )


def _parse_cache_sequential(
    reader: BinaryReader,
    cache_bytes: bytes,
    packages: list[_Package],
    library_parts: list[_LibraryPart],
    components: list[ComponentDef],
) -> None:
    """Phase 1: Sequential metadata-based cache entry parsing.

    Reads cache entries sequentially from the current reader position,
    handling variable-length metadata, twin ID checks, and structure bodies.
    Falls back to brute-force scanning on parse failures.
    """
    # Helper: tryRead probe (C++ reference pattern)
    def _try_read(fn) -> bool:
        saved = reader.tell()
        try:
            fn()
        except (BinaryReadError, Exception):
            reader.seek(saved)
            return False
        reader.seek(saved)
        return True

    entry_count = 0
    while not reader.is_eof():
        try:
            # ── 1. Variable-length metadata (3 variants) ──────────
            has_str_now = _try_read(lambda: _read_cache_string(reader))

            if not has_str_now:
                has_str_after_8 = _try_read(
                    lambda: (reader.skip(8), _read_cache_string(reader))
                )
                if has_str_after_8:
                    reader.skip(2)
                    _read_cache_string(reader)  # refDes descriptor
                reader.skip(2)

            _read_cache_string(reader)  # entry name

            # ── 2. Twin ID check ──────────────────────────────────
            peek_bytes = reader.peek(8)
            id0 = int.from_bytes(peek_bytes[0:4], 'little')
            id1 = int.from_bytes(peek_bytes[4:8], 'little')

            if id0 != id1:
                while True:
                    some_val = reader.read_uint16()
                    if reader.is_eof():
                        break
                    try:
                        reader.skip(1)
                        if reader.is_eof():
                            break
                        reader.seek(reader.tell() - 1)
                    except BinaryReadError:
                        break
                    if not _try_read(lambda: _read_cache_string(reader)):
                        reader.skip(2)
                    _read_cache_string(reader)
                    if some_val != 0:
                        break
                if reader.is_eof():
                    break

            # ── 3. Read twin IDs + structure type ─────────────────
            reader.read_uint32()
            reader.read_uint32()
            struct_type = reader.read_uint16()

            # ── 4. Parse or skip the structure ────────────────────
            struct_start = reader.tell()
            try:
                if struct_type == StructureType.Package:
                    pkg = _parse_package(reader)
                    packages.append(pkg)
                    for comp_def in _package_to_component_defs(pkg):
                        components.append(comp_def)
                elif struct_type == StructureType.LibraryPart:
                    lp = _parse_library_part(reader)
                    library_parts.append(lp)
                    _apply_library_part_pin_names(lp, components)
                else:
                    _skip_structure(reader)
            except (BinaryReadError, Exception) as struct_exc:
                logger.debug(
                    "Cache seq entry %d struct 0x%02X failed at 0x%X: %s",
                    entry_count, struct_type, struct_start, struct_exc,
                )
                reader.seek(struct_start)
                try:
                    _skip_structure(reader)
                except (BinaryReadError, Exception):
                    break

            entry_count += 1

        except (BinaryReadError, Exception) as exc:
            logger.debug(
                "Cache seq entry %d metadata failed at 0x%X: %s",
                entry_count, reader.tell(), exc,
            )
            break

    logger.debug("Sequential cache parsing: %d entries", entry_count)


# ============================================================
#  ComponentDef Construction
# ============================================================


def _package_to_component_defs(pkg: _Package) -> list[ComponentDef]:
    """Build ComponentDef objects from a parsed Package.

    Each Device in the Package becomes a separate ComponentDef variant.

    Args:
        pkg: Parsed Package structure.

    Returns:
        List of ComponentDef objects.
    """
    result: list[ComponentDef] = []
    base_name = _strip_numeric_suffix(pkg.name)

    for device in pkg.devices:
        if device.unit_ref:
            library_id = f"{base_name}.{device.unit_ref}"
        else:
            library_id = base_name

        pins: list[PinDef] = []
        for phy_pin in device.pin_map:
            if phy_pin is not None:
                pins.append(PinDef(
                    number=phy_pin,
                    name="",
                    type=ElectricalType.PASSIVE,
                ))

        comp_def = ComponentDef(
            library_id=library_id,
            part_name=base_name,
            footprint=pkg.pcb_footprint,
            pins=pins,
            pin_count=len(pins),
            source_format="CIS_DSN",
        )
        result.append(comp_def)

    return result


def _strip_numeric_suffix(name: str) -> str:
    """Strip trailing '_N' numeric suffix from Cache package names.

    Cache Package names may include a numeric suffix from the Package
    stream they originated in (e.g., 'RES_0' → 'RES').
    LibraryPart names may have a suffix like '_0.Normal'.
    """
    # Strip trailing _N where N is one or more digits
    result = re.sub(r'_\d+$', '', name)
    # Also strip .Normal / .Convert suffixes
    result = re.sub(r'\.(Normal|Convert)$', '', result)
    return result


def _apply_library_part_pin_names(
    lp: _LibraryPart, components: list[ComponentDef],
) -> None:
    """Apply functional pin names from a LibraryPart to matching ComponentDefs.

    LibraryPart.pin_names[i] corresponds to logical pin index i.
    ComponentDef.pins[j] corresponds to physical pin from Device.pin_map[j].

    Args:
        lp: Parsed LibraryPart structure.
        components: Existing ComponentDef list to enrich (mutated in place).
    """
    lp_base = _strip_numeric_suffix(lp.name)

    for comp in components:
        if comp.part_name != lp_base:
            # Try matching without suffix stripping for exact names
            continue

        min_len = min(len(lp.pin_names), len(comp.pins))
        for i in range(min_len):
            pin_name = lp.pin_names[i]
            if pin_name:
                comp.pins[i].name = pin_name


def _apply_all_library_part_pin_names(
    packages: list[_Package],
    library_parts: list[_LibraryPart],
    components: list[ComponentDef],
) -> None:
    """Post-process: apply all LibraryPart pin names to components."""
    for lp in library_parts:
        _apply_library_part_pin_names(lp, components)

    # Also try matching LibraryParts to Packages that haven't been
    # converted to ComponentDef yet
    lp_by_base: dict[str, _LibraryPart] = {}
    for lp in library_parts:
        base = _strip_numeric_suffix(lp.name)
        if base not in lp_by_base:
            lp_by_base[base] = lp

    for pkg in packages:
        base = _strip_numeric_suffix(pkg.name)
        lp = lp_by_base.get(base)
        if lp is None:
            # Try fuzzy match: remove _\d+ from lp names and compare
            for lp_key, lp_val in lp_by_base.items():
                if lp_key == base or base.startswith(lp_key) or lp_key.startswith(base):
                    lp = lp_val
                    break

        if lp is None:
            continue

        # Apply pin names to matching components
        for comp in components:
            if _strip_numeric_suffix(comp.part_name) != base:
                continue
            min_len = min(len(lp.pin_names), len(comp.pins))
            for i in range(min_len):
                pin_name = lp.pin_names[i]
                if pin_name and not comp.pins[i].name:
                    comp.pins[i].name = pin_name


# ============================================================
#  Brute-Force Preamble Recovery
# ============================================================


def _scan_for_structures(
    reader: BinaryReader,
    buffer: bytes,
    packages: list[_Package],
    library_parts: list[_LibraryPart],
    components: list[ComponentDef],
) -> None:
    """Brute-force scan for Package/LibraryPart via preamble magic.

    When sequential metadata parsing fails mid-stream, search the
    remaining buffer for preamble magic (FF E4 5C 39) and check if
    3 bytes before each match is a valid short prefix type byte
    for Package (0x1F) or LibraryPart (0x18).

    Reference: cache-parser.ts scanForStructures()
    """
    pos = reader.tell()
    buffer_len = len(buffer)

    recovered = 0
    while pos < buffer_len - 10:
        magic_idx = buffer.find(PREAMBLE_MAGIC, pos)
        if magic_idx < 3:
            break

        # Short prefix is 3 bytes (type + int16 count) before preamble.
        short_prefix_start = magic_idx - 3
        type_byte = buffer[short_prefix_start]

        if type_byte in (StructureType.Package, StructureType.LibraryPart):
            # Walk backward from short prefix to find the first long prefix.
            # Long prefixes are 9 bytes each, all with the same type byte.
            prefix_start = short_prefix_start
            while prefix_start >= 9:
                candidate = prefix_start - 9
                if buffer[candidate] == type_byte:
                    prefix_start = candidate
                else:
                    break

            reader.seek(prefix_start)
            try:
                if type_byte == StructureType.Package:
                    pkg = _parse_package(reader)
                    packages.append(pkg)
                    for comp_def in _package_to_component_defs(pkg):
                        components.append(comp_def)
                else:
                    lp = _parse_library_part(reader)
                    library_parts.append(lp)
                    _apply_library_part_pin_names(lp, components)
                recovered += 1
                pos = reader.tell()
                continue
            except (BinaryReadError, Exception):
                pass

        pos = magic_idx + 1

    if recovered > 0:
        logger.info("Brute-force recovery found %d additional structures", recovered)

    # Seek to end so main loop terminates
    reader.seek(buffer_len)
