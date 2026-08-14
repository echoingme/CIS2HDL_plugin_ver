"""PST parser unit tests — pstchip, pstxprt, pstxnet parsers."""
from pathlib import Path

import pytest

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "HG5015test"


# ── pstchip_parser ────────────────────────────────────────────────

def test_pstchip_parse_basic():
    from cis2hdl.core.parser.pstchip_parser import PstchipParser
    parser = PstchipParser()
    result = parser.parse(_FIXTURES / "pstchip.dat")
    assert len(result) > 100, f"Expected >100 primitives, got {len(result)}"


def test_pstchip_parse_value_jedec():
    from cis2hdl.core.parser.pstchip_parser import PstchipParser
    parser = PstchipParser()
    result = parser.parse(_FIXTURES / "pstchip.dat")
    # Check a known capacitor primitive
    entry = result.get("C_HSC0201-HDTA_8.2PF*")
    assert entry is not None, "C_HSC0201-HDTA_8.2PF* not found"
    assert entry.part_name == "C"
    assert entry.jedec_type == "HSC0201-HDTA"
    assert "8.2" in entry.value


def test_pstchip_parse_pins():
    from cis2hdl.core.parser.pstchip_parser import PstchipParser
    parser = PstchipParser()
    result = parser.parse(_FIXTURES / "pstchip.dat")
    entry = result.get("C_HSC0201-HDTA_8.2PF*")
    assert entry.pins == {"A": "1", "B": "2"}, f"Unexpected pins: {entry.pins}"


def test_pstchip_file_missing():
    from cis2hdl.core.parser.pstchip_parser import PstchipParser
    parser = PstchipParser()
    result = parser.parse(Path("/nonexistent/pstchip.dat"))
    assert result == {}


# ── pstxprt_parser ────────────────────────────────────────────────

def test_pstxprt_parse_entries():
    from cis2hdl.core.parser.pstxnet_parser import PstxnetParser
    parser = PstxnetParser()
    ir = parser.parse(_FIXTURES / "pstxprt.dat")
    entries = ir.metadata["pstxnet_entries"]
    assert len(entries) > 800, f"Expected >800 entries, got {len(entries)}"


def test_pstxprt_ins_to_refdes():
    from cis2hdl.core.parser.pstxnet_parser import PstxnetParser
    parser = PstxnetParser()
    ir = parser.parse(_FIXTURES / "pstxprt.dat")
    ins_map = ir.metadata["ins_to_refdes"]
    assert len(ins_map) > 800, f"Expected >800 INSxxxs, got {len(ins_map)}"
    # Check known mapping from the file
    assert "INS32276" in ins_map, "INS32276 should map to C1"
    assert ins_map["INS32276"] == "C1"


def test_pstxprt_led_entries():
    """LED5/LED6 should be parsed (they were missing before the rewrite)."""
    from cis2hdl.core.parser.pstxnet_parser import PstxnetParser
    parser = PstxnetParser()
    ir = parser.parse(_FIXTURES / "pstxprt.dat")
    entries = ir.metadata["pstxnet_entries"]
    refdes_set = {e.refdes for e in entries}
    assert "LED5" in refdes_set, "LED5 should be found"
    assert "LED6" in refdes_set, "LED6 should be found"
    assert "M1" in refdes_set, "M1 should be found"


def test_pstxprt_file_missing():
    from cis2hdl.core.parser.pstxnet_parser import PstxnetParser
    parser = PstxnetParser()
    ir = parser.parse(Path("/nonexistent/pstxprt.dat"))
    assert ir.metadata["pstxnet_entries"] == []
    assert ir.metadata["ins_to_refdes"] == {}


# ── pstxnet_parser ────────────────────────────────────────────────

def test_pstxnet_parse_basic():
    from cis2hdl.core.parser.pstxnet_netlist_parser import PstxnetNetlistParser
    parser = PstxnetNetlistParser()
    result = parser.parse(_FIXTURES / "pstxnet.dat")
    assert len(result) > 500, f"Expected >500 refdes, got {len(result)}"


def test_pstxnet_parse_connections():
    from cis2hdl.core.parser.pstxnet_netlist_parser import PstxnetNetlistParser
    parser = PstxnetNetlistParser()
    result = parser.parse(_FIXTURES / "pstxnet.dat")
    # C361 should have pin connections
    assert "C361" in result, "C361 should have net connections"
    assert "2" in result["C361"], "C361 pin 2 should be connected"


def test_pstxnet_file_missing():
    from cis2hdl.core.parser.pstxnet_netlist_parser import PstxnetNetlistParser
    parser = PstxnetNetlistParser()
    result = parser.parse(Path("/nonexistent/pstxnet.dat"))
    assert result == {}


# ── v2.1: multi-section + skip-keyword P0 fixes ─────────────────────

def test_pstxnet_skip_all_attribute_keywords():
    """Skip regex must cover ALL net attribute keywords (P0-1).

    Missing RELATIVE_PROPAGATION_DELAY prematurely ends nets and drops
    connections.  With all 4 extra keywords the parse reaches 100% of
    the NODE_NAME lines in the file.
    """
    from cis2hdl.core.parser.pstxnet_netlist_parser import (
        PstxnetNetlistParser,
        _RE_SKIP_LINE,
    )
    # The keyword must be matched so the state machine skips it.
    assert _RE_SKIP_LINE.match("NET_PHYSICAL_TYPE='x'")
    assert _RE_SKIP_LINE.match("NET_SPACING_TYPE='x'")
    assert _RE_SKIP_LINE.match("RELATIVE_PROPAGATION_DELAY='x'")
    assert _RE_SKIP_LINE.match("RATSNEST_SCHEDULE='x'")

    # Full parse reaches every NODE_NAME line in the fixture (2821).
    parser = PstxnetNetlistParser()
    result = parser.parse(_FIXTURES / "pstxnet.dat")
    total = sum(len(v) for v in result.values())
    assert total >= 2821, f"Expected >=2821 connections, got {total}"


def test_pstxnet_u6_section_expansion():
    """U6 (531 pins) is expanded into U6A..U6I (P0-2).

    pstxnet.dat stores the whole SoC as a single 'U6' refdes while the
    schematic/EDIF side uses per-section instances U6A..U6I.  The
    expansion must distribute every U6 pin to its section.
    """
    from cis2hdl.core.parser.pstxnet_netlist_parser import PstxnetNetlistParser
    parser = PstxnetNetlistParser()
    result = parser.parse(_FIXTURES / "pstxnet.dat")

    assert "U6" in result
    assert len(result["U6"]) == 531, f"U6 should have 531 pins, got {len(result['U6'])}"

    sub_sections = {k: len(v) for k, v in result.items()
                    if k.startswith("U6") and k != "U6"}
    expected = {"U6A", "U6B", "U6C", "U6D", "U6E", "U6F", "U6G", "U6H", "U6I"}
    assert set(sub_sections) == expected, f"Unexpected U6 sub-sections: {sub_sections}"
    assert sum(sub_sections.values()) == 531, (
        f"Expanded U6 pins should total 531, got {sum(sub_sections.values())}"
    )
    # A known section-A pin: U6A pin C2 connects to WL_5G_IN_C0
    assert result["U6A"].get("C2") == "WL_5G_IN_C0"


def test_pstxprt_multi_section_entries():
    """pstxprt parser captures ALL sections of a multi-section part (P0-2)."""
    from cis2hdl.core.parser.pstxnet_parser import PstxnetParser
    parser = PstxnetParser()
    ir = parser.parse(_FIXTURES / "pstxprt.dat")
    entries = ir.metadata["pstxnet_entries"]

    u6_entries = [e for e in entries if e.refdes.upper() == "U6"]
    assert len(u6_entries) == 9, (
        f"Expected 9 U6 section entries, got {len(u6_entries)}"
    )
    sections = {e.section for e in u6_entries}
    assert sections == {"A", "B", "C", "D", "E", "F", "G", "H", "I"}
    assert all(e.part_name == "TG1_ABB_2_BGA531-26-2727B_TG1_A"
               for e in u6_entries)


# ── pstchip lookup bridge ──────────────────────────────────────────

def test_build_pstchip_lookup():
    from cis2hdl.core.parser.pstxnet_parser import PstxnetParser
    from cis2hdl.core.parser.pstchip_parser import PstchipParser
    parser_xprt = PstxnetParser()
    ir = parser_xprt.parse(_FIXTURES / "pstxprt.dat")
    entries = ir.metadata["pstxnet_entries"]
    pstchip = PstchipParser().parse(_FIXTURES / "pstchip.dat")
    lookup = PstxnetParser.build_pstchip_lookup(entries, pstchip)
    assert len(lookup) > 400, f"Expected >400 refdes, got {len(lookup)}"
    # C1 should map to C_SC0603-TD_10UF
    chip_c1 = lookup.get("C1")
    assert chip_c1 is not None, "C1 should have pstchip entry"
    assert chip_c1.jedec_type == "SC0603-TD"
