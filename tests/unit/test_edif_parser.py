"""EDIF parser unit tests — net-name extraction and pin map (v2.1 P0-3).

Covers the P0 fix where ``_parse_net`` / ``_parse_net_raw`` used
``_sym_str(net[1])`` on wrapped net names — OrCAD EDIF encodes net names
in three forms, and the wrapped forms returned "" and silently dropped
the net name:

    (net GND (joined ...))                    → plain
    (net (name PFI_DYING_GASP (display ...)) …) → name-wrapped
    (net (rename INTERNAL "EXTERNAL") ...)    → rename
"""
from pathlib import Path

from sexpdata import Symbol

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "HG5015test"


# ── _net_name unit tests ───────────────────────────────────────────

def test_net_name_plain():
    from cis2hdl.core.parser.edif_parser import _net_name
    assert _net_name(Symbol("GND")) == "GND"
    assert _net_name("GND") == "GND"
    assert _net_name(123) == "123"


def test_net_name_wrapped():
    from cis2hdl.core.parser.edif_parser import _net_name
    wrapped = ["name", Symbol("PFI_DYING_GASP"), ["display", ["figureGroupOverride", "ALIAS"]]]
    assert _net_name(wrapped) == "PFI_DYING_GASP"


def test_net_name_rename():
    from cis2hdl.core.parser.edif_parser import _net_name
    renamed = ["rename", Symbol("N12345"), "GND"]
    assert _net_name(renamed) == "GND"


def test_net_name_empty():
    from cis2hdl.core.parser.edif_parser import _net_name
    assert _net_name([]) == ""
    assert _net_name(None) == ""


# ── _parse_net_raw regression (the P0 fix) ─────────────────────────

def test_parse_net_raw_wrapped_name():
    """Wrapped (name ...) nets must produce a real net name (P0-3)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    net = [
        "net",
        ["name", Symbol("PFI_DYING_GASP"), ["display", "x"]],
        ["joined", ["portRef", Symbol("B"), ["instanceRef", Symbol("INS325")]]],
    ]
    result = EDIFParser._parse_net_raw(net)
    assert result is not None
    assert result["name"] == "PFI_DYING_GASP"
    assert result["connections"] == [
        {"refdes": "INS325", "pin_number": "B"}
    ]


def test_parse_net_raw_rename_name():
    """(rename ...) net names must resolve to the external name (P0-3)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    net = [
        "net",
        ["rename", Symbol("N12345"), "GND"],
        ["joined", ["portRef", Symbol("1"), ["instanceRef", Symbol("INS1")]]],
    ]
    result = EDIFParser._parse_net_raw(net)
    assert result is not None
    assert result["name"] == "GND"


def test_parse_net_raw_plain_name():
    """Plain net names keep working (P0-3 non-regression)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    net = ["net", Symbol("GND"), ["joined", ["portRef", Symbol("1")]]]
    result = EDIFParser._parse_net_raw(net)
    assert result is not None
    assert result["name"] == "GND"


# ── Phase XI P0-A1/A3/A5 regression tests ──────────────────────────

def test_wire_segment_polyline():
    """WireSegment polyline support (P0-A1): points derive start/end."""
    from cis2hdl.core.ir.design import WireSegment
    w = WireSegment(points=[(10, 20), (30, 40), (50, 60)], net_name="T")
    assert w.start_x == 10 and w.start_y == 20
    assert w.end_x == 50 and w.end_y == 60
    assert len(w.points) == 3


def test_wire_segment_single_segment_compat():
    """WireSegment single-segment path remains valid (backward compat)."""
    from cis2hdl.core.ir.design import WireSegment
    w = WireSegment(start_x=1, start_y=2, end_x=3, end_y=4)
    assert w.points == []
    assert w.start_x == 1


def test_extract_wire_points():
    """(figure WIRE (path (pointList (pt x y) ...))) extraction (P0-A1)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    fig = [
        "figure", Symbol("WIRE"),
        ["path", ["pointList", ["pt", 1010, -750], ["pt", 830, -750], ["pt", 800, -750]]],
    ]
    pts = EDIFParser._extract_wire_points(fig)
    assert pts == [(1010, -750), (830, -750), (800, -750)]


def test_extract_wire_points_empty():
    """Malformed figure returns empty list (P0-A1 robustness)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    assert EDIFParser._extract_wire_points(["figure", Symbol("WIRE")]) == []
    assert EDIFParser._extract_wire_points(["figure", Symbol("PARTBODY")]) == []


def test_parse_net_extracts_wires():
    """_parse_net populates NetIR.wires from figure WIRE (P0-A1)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    net = [
        "net", Symbol("GND"),
        ["joined", ["portRef", Symbol("1"), ["instanceRef", Symbol("INS1")]]],
        ["figure", Symbol("WIRE"),
         ["path", ["pointList", ["pt", 10, 20], ["pt", 30, 40]]]],
    ]
    result = EDIFParser()._parse_net(net, page_id="1.1")
    assert result is not None
    assert result.name == "GND"
    assert len(result.wires) == 1
    assert result.wires[0].points == [(10, 20), (30, 40)]
    assert result.wires[0].net_name == "GND"
    assert result.wires[0].page_id == "1.1"


def test_net_name_ampersand_unescape():
    """OrCAD EDIF '&' escape prefix is stripped (P0-A5)."""
    from cis2hdl.core.parser.edif_parser import _net_name
    assert _net_name(Symbol("&3V3_SOC")) == "3V3_SOC"
    assert _net_name(["name", Symbol("&1V8_BUCK"), ["display", "x"]]) == "1V8_BUCK"


def test_off_page_connector_detection():
    """(portRef XXX_OFF_PAGE_CONNECTOR) without instanceRef → off_page (P0-A3)."""
    from cis2hdl.core.ir.design import PageIR
    page = PageIR(page_id="1.1", page_name="P1")
    net_raw = [
        "net", Symbol("GND"),
        ["joined",
         ["portRef", Symbol("GND_OFF_PAGE_CONNECTOR")],
         ["portRef", Symbol("1"), ["instanceRef", Symbol("INS1")]]],
    ]
    # call the same logic used in _parse_page
    from cis2hdl.core.parser.edif_parser import EDIFParser, _find_first, _find_all, _net_name, _sym_str
    joined = _find_first(net_raw, "joined")
    net_name = _net_name(net_raw[1])
    for pref in _find_all(joined, "portRef"):
        pin_label = _sym_str(pref[1])
        if "OFF_PAGE_CONNECTOR" in pin_label.upper() and _find_first(pref, "instanceRef") is None:
            page.off_pages.append({"name": pin_label, "net_name": net_name})
    assert len(page.off_pages) == 1
    assert page.off_pages[0]["name"] == "GND_OFF_PAGE_CONNECTOR"
    assert page.off_pages[0]["net_name"] == "GND"


# ── Phase XI P0-A2: page block recognition ─────────────────────────

def _make_page_block(
    name_internal: str,
    name_display: str,
    width: int = 1654,
    height: int = 1169,
    insts: int = 0,
    nets: int = 0,
) -> list:
    """Build a synthetic ``(page (rename ...) (pageSize ...) ...)`` block."""
    block = [
        "page",
        ["rename", Symbol(name_internal), name_display],
        ["pageSize", ["rectangle", ["pt", 0, -height], ["pt", width, 0]]],
        ["boundingBox", ["rectangle", ["pt", 0, -height], ["pt", width, 0]]],
    ]
    for i in range(insts):
        block.append([
            "instance", Symbol(f"INS{i}"),
            ["viewRef", Symbol("V"),
             ["cellRef", Symbol("RES_0603_10K"), ["libraryRef", Symbol("LIB")]]],
        ])
    for i in range(nets):
        block.append([
            "net", Symbol(f"N{i}"),
            ["joined", ["portRef", Symbol("1"), ["instanceRef", Symbol("INS0")]]],
        ])
    return block


def _make_page_cell(page_blocks: list[list]) -> list:
    """Build a cell whose view/contents contains (page ...) blocks."""
    return [
        "cell", Symbol("TOP"),
        ["view", Symbol("TOP_SCH"),
         ["interface"],
         ["contents"] + page_blocks],
    ]


def test_get_page_blocks_detects_page_blocks():
    """(page ...) blocks nested in cell→view→contents are found (P0-A2)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    cell = _make_page_cell([_make_page_block("&01_COVER_PAGE", "01-Cover_Page")])
    blocks = EDIFParser()._get_page_blocks(cell)
    assert len(blocks) == 1
    assert blocks[0][0] == "page"


def test_get_page_blocks_empty_without_pages():
    """Cells with no page blocks return an empty list (P0-A2 fallback)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    cell = ["cell", Symbol("RES_0603_10K"),
            ["view", Symbol("V"), ["interface", ["port", Symbol("1")]]]]
    assert EDIFParser()._get_page_blocks(cell) == []


def test_page_block_name_and_size():
    """Page rename display name + pageSize rectangle → (width, height) (P0-A2)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    block = _make_page_block("&01_COVER_PAGE", "01-Cover_Page", width=1654, height=1169)
    assert EDIFParser._page_block_name(block, 1) == "01-Cover_Page"
    assert EDIFParser._page_block_size(block) == (1654, 1169)
    # fallback name when rename is absent
    assert EDIFParser._page_block_name(["page"], 7) == "PAGE_7"
    # fallback size when pageSize is missing
    assert EDIFParser._page_block_size(["page"]) == (3520, 2720)


def test_parse_page_splits_page_blocks_into_pages():
    """Each (page ...) block becomes its own PageIR, no collapse (P0-A2)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    from cis2hdl.core.db.component_db import ComponentDB
    cell = _make_page_cell([
        _make_page_block("&01_COVER_PAGE", "01-Cover_Page", insts=2, nets=1),
        _make_page_block("&10_SOC_SERDES", "10-SOC_SerDes", width=1750, height=1170, insts=3, nets=2),
    ])
    pages = EDIFParser()._parse_page(cell, ComponentDB(), set(), 0)
    assert len(pages) == 2
    assert pages[0].page_name == "01-Cover_Page"
    assert pages[0].page_id == "1.1"
    assert pages[0].width == 1654 and pages[0].height == 1169
    assert len(pages[0].instances) == 2
    assert len(pages[0].nets) == 1
    assert pages[1].page_name == "10-SOC_SerDes"
    assert pages[1].page_id == "1.2"
    assert pages[1].width == 1750 and pages[1].height == 1170
    assert len(pages[1].instances) == 3
    assert len(pages[1].nets) == 2


def test_parse_page_fallback_heuristic():
    """Cells without page blocks use the legacy _cell_is_page heuristic (P0-A2)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    from cis2hdl.core.db.component_db import ComponentDB
    cell = [
        "cell", Symbol("SCHEMATIC1"),
        ["view", Symbol("SCH"),
         ["contents",
          ["instance", Symbol("INS1"),
           ["viewRef", Symbol("V"),
            ["cellRef", Symbol("RES_0603_10K"), ["libraryRef", Symbol("LIB")]]]],
          ["net", Symbol("GND"),
           ["joined", ["portRef", Symbol("1"), ["instanceRef", Symbol("INS1")]]]],
          ]],
    ]
    pages = EDIFParser()._parse_page(cell, ComponentDB(), set(), 0)
    assert len(pages) == 1
    assert pages[0].page_name == "SCHEMATIC1"
    assert pages[0].page_id == "1.1"
    assert len(pages[0].instances) == 1
    assert len(pages[0].nets) == 1


def test_parse_page_non_page_cell_returns_empty():
    """Non-page cells yield no pages (P0-A2)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    from cis2hdl.core.db.component_db import ComponentDB
    cell = ["cell", Symbol("RES_0603_10K"),
            ["view", Symbol("V"), ["interface", ["port", Symbol("1")]]]]
    assert EDIFParser()._parse_page(cell, ComponentDB(), set(), 0) == []


def test_page_block_wires_carry_page_id():
    """Nets inside page blocks get wires attributed to that page (P0-A2)."""
    from cis2hdl.core.parser.edif_parser import EDIFParser
    from cis2hdl.core.db.component_db import ComponentDB
    block = [
        "page",
        ["rename", Symbol("&01"), "01-Cover_Page"],
        ["pageSize", ["rectangle", ["pt", 0, -1169], ["pt", 1654, 0]]],
        ["net", Symbol("GND"),
         ["joined", ["portRef", Symbol("1"), ["instanceRef", Symbol("INS1")]]],
         ["figure", Symbol("WIRE"),
          ["path", ["pointList", ["pt", 10, 20], ["pt", 30, 40]]]]],
    ]
    cell = ["cell", Symbol("TOP"), ["view", Symbol("V"), ["contents", block]]]
    pages = EDIFParser()._parse_page(cell, ComponentDB(), set(), 0)
    assert len(pages) == 1
    assert len(pages[0].wires) == 1
    assert pages[0].wires[0].page_id == "1.1"
    assert pages[0].wires[0].net_name == "GND"
    assert pages[0].nets[0].wires[0].page_id == "1.1"
