"""Page Stream Parser — DSN 页面流解析。

将 DSN 内部 Page 流解析为结构化的页面数据。

参考：
    - openOrCadParser: PageParser.cpp
    - universal-netlist: page-parser.ts

.. rubric:: Research Note — DSN Wire Parsing Limitation (RTL Format)

The HG5015 DSN uses an RTL variant format.  Wire structures (type 20/21)
are parsed by scanning for preamble magic bytes (``0xFFE45C39``) in the
binary stream via ``parse_page()``.  This preamble-scanning approach:

* **Works** when structure headers align with preamble positions
  (standard "wireframe" DSN pages).
* **Fails** when the RTL format uses different structure layouts
  (e.g., pages with TitleBlock/GraphicInst-only metadata, or pages
  where wire data is embedded differently).

**Observed results** (HG5015-BE36_V10.DSN, 24 pages):

* 7 pages have visible wire structures (segments parsed successfully).
* 13 pages have 0 wire segments (preamble scanning misses them).
* The 3717 nets are **reconnected logically** from wire_id → alias
  mapping and port/global definitions, so *logical connectivity* is
  correct across all pages — only the *coordinate data* (wire segments)
  is missing from those 13 pages.

**Cadence DEHDL auto-rendering**: Cadence does **not** auto-draw visible
wires from ``.con`` net definitions.  The ``.con`` provides logical
connectivity that enables:

* Net highlighting in the navigator
* Cross-probing between schematic and PCB
* ERC (electrical rule checking)
* Design sync with PCB layout

Visible wires still need ``PAINT WIRE`` commands in CSA or manual drawing
in the DEHDL editor.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .binary_reader import BinaryReader
from .structures import (
    PlacedInstance,
    T0x10,
    WireSegment,
    GraphicInst,
    NetAlias,
    TitleBlockText,
    PREAMBLE_MAGIC,
    parse_placed_instance,
    parse_wire,
    parse_port,
    parse_global,
    parse_off_page_connector,
    parse_net_alias,
    parse_title_block,
    set_strlst,
)

logger = logging.getLogger(__name__)


@dataclass
class PageData:
    """解析完成的页面数据。

    Attributes:
        page_id: 页面标识符（如 'PAGE1'）。
        page_name: 页面显示名称。
        width: 页面宽度。
        height: 页面高度。
        instances: 器件实例列表。
        wires: 连线列表。
        ports: 端口列表。
        globals_: 全局信号列表。
        off_pages: 跨页连接器列表。
        aliases: 网络标签列表。
    """

    page_id: str = ""
    page_name: str = ""
    width: int = 3520
    height: int = 2720
    instances: list[PlacedInstance] = field(default_factory=list)
    wires: list[WireSegment] = field(default_factory=list)
    ports: list[GraphicInst] = field(default_factory=list)
    globals_: list[GraphicInst] = field(default_factory=list)
    off_pages: list[GraphicInst] = field(default_factory=list)
    aliases: list[NetAlias] = field(default_factory=list)
    title_blocks: list[TitleBlockText] = field(default_factory=list)

    @property
    def total_instances(self) -> int:
        return len(self.instances)

    @property
    def total_nets(self) -> int:
        """推断网络总数（从 T0x10 的 net_id 去重计数）。"""
        net_ids: set[int] = set()
        for inst in self.instances:
            for t0 in inst.t0x10_list:
                net_ids.add(t0.net_id)
        return len(net_ids)


# ── Parser dispatch table ────────────────────────────────────────────────
# Maps each parse function to the list it appends to and a label for logging.
_PARSER_DISPATCH: list[tuple] = [
    (parse_placed_instance, "instances", "inst"),
    (parse_wire, "wires", "wire"),
    (parse_port, "ports", "port"),
    (parse_global, "globals_", "global"),
    (parse_off_page_connector, "off_pages", "offpage"),
    (parse_net_alias, "aliases", "alias"),
    (parse_title_block, "title_blocks", "titleblock"),
]


def parse_page(buffer: bytes, page_id: str = "",
               strlst: list[str] | None = None) -> PageData:
    """解析 DSN 页面流为 PageData。

    The page stream consists of a variable-length page header (containing
    metadata like the design name) followed by a list of structure blocks.
    Each structure block starts with the preamble FF E4 5C 39.

    We locate all preamble positions in the buffer, then try each parse
    function at each preamble.  The first successful parse marks the
    boundary between page metadata (header) and the structure list.
    Subsequent preambles are parsed as structures directly.

    Args:
        buffer: 页面流原始字节。
        page_id: 页面标识符。
        strlst: 字符串表（用于解析索引引用），可选。

    Returns:
        解析完成的 PageData 对象。
    """
    # Set module-level strLst for structure parsers to use
    set_strlst(strlst)

    # DEBUG: dump first 100 bytes of page buffer for format diagnostics
    logger.debug(
        "Page %s: first 100 bytes: %s",
        page_id, buffer[:100].hex(" "),
    )

    reader = BinaryReader(buffer)
    page = PageData(page_id=page_id)

    # ── 1.  Collect all preamble positions ─────────────────────────
    preamble_positions: list[int] = []
    search_start = 0
    while True:
        pos = buffer.find(PREAMBLE_MAGIC, search_start)
        if pos == -1:
            break
        preamble_positions.append(pos)
        search_start = pos + 4  # jump past the magic, don't rescan within it

    if not preamble_positions:
        logger.warning("Page %s: no preamble found — empty page?", page_id)
        return page

    # ── 2.  Find the first valid structure (marks end of header) ──
    # Preamble #0 and #1 are page metadata (design name + sheet name),
    # not structures.  Their format is:
    #   PREAMBLE | uint32(0) | uint16(len) | string
    # Skip them to prevent false-positive matches against metadata strings.
    structure_start_idx: int | None = None
    metadata_preamble_count = 2
    search_start = min(metadata_preamble_count, len(preamble_positions))
    for idx in range(search_start, len(preamble_positions)):
        pos = preamble_positions[idx]
        reader.seek(pos)
        for parse_fn, list_attr, _label in _PARSER_DISPATCH:
            reader.seek(pos)
            try:
                result = parse_fn(reader)
            except Exception:
                continue
            if _is_valid_result(result, _label):
                getattr(page, list_attr).append(result)
                structure_start_idx = idx + 1  # next preamble
                break
        if structure_start_idx is not None:
            logger.debug(
                "Page %s: structure list starts at preamble #%d (offset 0x%X)",
                page_id,
                idx,
                pos,
            )
            break

    if structure_start_idx is None:
        # v0.5.1: Info page fallback — try sequential layout parsing
        # 4 info pages (Cover/Clock/Power/Block) use a different binary
        # layout without standard structure preambles.  Attempt to parse
        # TitleBlock text and GraphicInst elements from the raw stream.
        if len(preamble_positions) >= 2:
            logger.debug(
                "Page %s: trying sequential fallback parsing for info page",
                page_id,
            )
            try:
                _parse_info_page_sequential(reader, page, preamble_positions, buffer)
            except Exception as exc:
                logger.debug(
                    "Page %s: sequential fallback parsing failed: %s",
                    page_id, exc,
                )
        
        logger.warning(
            "Page %s: no valid structures found at any of %d preamble positions",
            page_id,
            len(preamble_positions),
        )
        return page

    # ── 3.  Parse remaining structures ─────────────────────────────
    for idx in range(structure_start_idx, len(preamble_positions)):
        pos = preamble_positions[idx]
        reader.seek(pos)

        for parse_fn, list_attr, _label in _PARSER_DISPATCH:
            reader.seek(pos)
            try:
                result = parse_fn(reader)
            except Exception:
                continue
            if _is_valid_result(result, _label):
                getattr(page, list_attr).append(result)
                break
        # If no parser succeeded, the preamble is simply not a
        # recognised structure — move on to the next one.

    # ── 4.  Summary ───────────────────────────────────────────────
    logger.info(
        "Page %s: %d instances, %d wires, %d ports, %d globals, %d aliases",
        page_id,
        len(page.instances),
        len(page.wires),
        len(page.ports),
        len(page.globals_),
        len(page.aliases),
    )

    return page


def _parse_info_page_sequential(
    reader: BinaryReader,
    page: PageData,
    preamble_positions: list[int],
    buffer: bytes,
) -> None:
    """Info page fallback: scan for TitleBlock and GraphicCommentText structures.

    Uses preamble-based scanning: at each preamble position, read the
    structure type byte and attempt TitleBlock (65) or GraphicCommentText (61)
    parsing.  Falls back to ASCII text extraction from the raw buffer.

    Reference: OpenOrCadParser StructTitleBlock, StructGraphicCommentTextInst
    """
    import re as _re

    # Structure type IDs from OpenOrCadParser
    STRUCT_TITLE_BLOCK = 65
    STRUCT_GRAPHIC_COMMENT_TEXT = 61
    
    found_texts: list[dict] = []
    
    # Skip page metadata region (first 2 preambles)
    scan_start = preamble_positions[2] if len(preamble_positions) > 2 else 0
    
    # ── Strategy 1: Preamble-based structure scanning ──
    # Each structure: [preamble 4B][type uint16][data_len uint32][data]
    # After preamble: skip 2B (prefix count?), then type byte
    for idx, pos in enumerate(preamble_positions):
        if pos < scan_start:
            continue
        reader.seek(pos)
        
        try:
            # Read preamble
            magic = reader.read_bytes(4)
            if magic != PREAMBLE_MAGIC:
                continue
            
            # Skip 2 bytes (possible prefix length/version)
            reader.skip(2)
            
            # Try reading as structure type
            struct_type = reader.read_uint16()
            reader.seek(pos + 6)  # Reset to after preamble+prefix
            
            if struct_type == STRUCT_TITLE_BLOCK:
                tb = _try_parse_titleblock_direct(reader, pos, buffer)
                if tb:
                    page.title_blocks.append(tb)
                    found_texts.append({
                        "type": "text", "text": tb.text,
                        "position": pos, "source": "title_block_65",
                    })
            elif struct_type == STRUCT_GRAPHIC_COMMENT_TEXT:
                ct = _try_parse_comment_text_direct(reader, pos, buffer)
                if ct:
                    page.title_blocks.append(ct)
                    found_texts.append({
                        "type": "text", "text": ct.text,
                        "position": pos, "source": "comment_text_61",
                    })
        except Exception:
            pass
    
    # ── Strategy 2: ASCII text scan (fallback) ──
    if not found_texts:
        raw = buffer[scan_start:]
        ascii_runs = _re.findall(rb'[\x20-\x7E]{4,}', raw)
        seen: set[str] = set()
        for tb in ascii_runs:
            text = tb.decode("ascii", errors="replace").strip()
            if text and text not in seen and len(text) >= 4:
                seen.add(text)
                tblock = TitleBlockText(text=text, loc_x=0, loc_y=0)
                page.title_blocks.append(tblock)
                found_texts.append({
                    "type": "text", "text": text,
                    "source": "ascii_fallback",
                })
    
    if found_texts:
        logger.info(
            "Info page %s: %d text(s) extracted",
            page.page_id, len(found_texts),
        )


def _try_parse_titleblock_direct(
    reader: "BinaryReader", pos: int, buffer: bytes
) -> "TitleBlockText | None":
    """Try direct TitleBlock (type 65) parsing from preamble position.

    TitleBlock = GraphicInst base (name, dbId, locX, locY, bbox, color)
               + 12 unknown bytes
               + text content (via SymbolDisplayProp)

    For HG5015 RTL variant, the text is stored as uint16-length-prefixed
    immediately after the GraphicInst bbox, before the SymbolDisplayProp list.
    """
    try:
        # Skip preamble (4B) + prefix header (2B) + type (2B)
        reader.seek(pos + 8)

        # Read GraphicInst base fields
        # name: uint16 length + bytes
        name_len = reader.read_uint16()
        if 0 < name_len < 200:
            reader.skip(name_len)
        else:
            reader.seek(pos + 8)  # Reset
        
        # dbId (4B)
        _dbid = reader.read_uint32()
        # locY, locX (int16 each)
        loc_y = reader.read_int16()
        loc_x = reader.read_int16()
        # bbox: y2, x2, x1, y1 (int16 each)
        _ = reader.read_bytes(8)
        # color (1B) + 3 unknown
        _ = reader.read_bytes(4)
        
        # Now at SymbolDisplayProp list length
        num_props = reader.read_uint16()
        if num_props > 100:
            return None
        
        text_parts: list[str] = []
        for _ in range(min(num_props, 20)):
            # Each prop: uint16 text_len + text + NUL
            tlen = reader.read_uint16()
            if 0 < tlen < 500 and tlen <= reader.remaining():
                tbytes = reader.read_bytes(tlen)
                reader.skip(1)  # NUL
                try:
                    t = tbytes.decode("latin-1").strip("\x00")
                    if t and len(t) >= 1:
                        text_parts.append(t)
                except Exception:
                    pass
        
        if text_parts:
            combined = " | ".join(text_parts)
            return TitleBlockText(text=combined, loc_x=loc_x, loc_y=loc_y)
    except Exception:
        pass
    return None


def _try_parse_comment_text_direct(
    reader: "BinaryReader", pos: int, buffer: bytes
) -> "TitleBlockText | None":
    """Try direct GraphicCommentText (type 61) parsing."""
    try:
        reader.seek(pos + 8)
        name_len = reader.read_uint16()
        if 0 < name_len < 200:
            reader.skip(name_len)
        _ = reader.read_uint32()  # dbId
        loc_y = reader.read_int16()
        loc_x = reader.read_int16()
        _ = reader.read_bytes(8)  # bbox
        _ = reader.read_bytes(4)  # color + unknown
        num_props = reader.read_uint16()
        if num_props > 100:
            return None
        text_parts: list[str] = []
        for _ in range(min(num_props, 20)):
            tlen = reader.read_uint16()
            if 0 < tlen < 500:
                tbytes = reader.read_bytes(tlen)
                reader.skip(1)
                try:
                    t = tbytes.decode("latin-1").strip("\x00")
                    if t and len(t) >= 1:
                        text_parts.append(t)
                except Exception:
                    pass
        if text_parts:
            return TitleBlockText(text=" | ".join(text_parts), loc_x=loc_x, loc_y=loc_y)
    except Exception:
        pass
    return None


def _is_valid_result(result: object, label: str) -> bool:
    """Return True if *result* looks like a real parsed structure.

    Rejects degenerate parses where the parser consumed a preamble but
    produced garbage (common when the preamble is actually page metadata).

    Validation heuristics are intentionally tighter than "any non-empty
    value" to avoid false positives from the page metadata region while
    still accepting the wide variety of real design data.
    """
    if label == "inst":
        # PlacedInstance — must have BOTH a non-empty package name AND a
        # non-empty reference.  Metadata regions sometimes produce a
        # partial pkg_name (e.g. "-VB_LQ128EP_0.Normal") with empty ref.
        # Phase XI T04: RTL chip-package views (RTL8367RB) carry pin-level
        # PlacedInstances whose reference may be empty — accept a non-empty
        # pkg_name in that case so the instance list is not zeroed.
        pkg: str = getattr(result, "pkg_name", "")
        ref: str = getattr(result, "reference", "")
        if not pkg or len(pkg) < 2:
            return False
        # Reject metadata-region garbage: pkg names that are pure view
        # suffixes without a real symbol identity.
        if pkg.startswith("-") or pkg.endswith(".Normal") or "Unknown" in pkg:
            return False
        return True
    elif label == "wire":
        # WireSegment — segment_id / wire_id must be positive AND
        # plausible (not the 8M+ values that come from misaligned reads).
        sid: int = getattr(result, "segment_id", 0)
        wid: int = getattr(result, "wire_id", 0)
        return bool(0 < sid < 1_000_000 and 0 < wid < 1_000_000)
    elif label in ("port", "global", "offpage"):
        # GraphicInst — name must be a plausible identifier (at least
        # 2 characters, no leading dash from partial metadata reads).
        name: str = getattr(result, "name", "")
        return bool(name and len(name) >= 2 and not name.startswith("-"))
    elif label == "alias":
        # NetAlias — alias_id must be positive and reasonable.
        aid: int = getattr(result, "alias_id", 0)
        return bool(0 < aid < 1_000_000)
    elif label == "titleblock":
        # TitleBlockText — text must be non-empty and at least 2 chars.
        text: str = getattr(result, "text", "")
        return bool(text and len(text) >= 2)
    return False
