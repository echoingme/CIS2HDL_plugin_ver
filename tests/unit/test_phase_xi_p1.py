"""Phase XI P1 tests — second-round Cadence-fix tasks (2026-08-10).

Covers:
  P1-1  write_page_map page-number extraction + sorting (output_manager)
  P1-2  symbol.css default attributes (ch347/rf_sw/rj45_2x2_led)
  P1-3  csa_writer emits $LOCATION for single-section parts
  P1-4  EDIF transform orientation → rotation/mirror; NC pin flags;
        SymbolPin electrical_type field
  P1-5  cpc mark cells use #CELL (not #ISCELL)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cis2hdl.core.parser.edif_parser import EDIFParser
from cis2hdl.core.parser.symbol_css import SymbolCssParser
from cis2hdl.core.writer.cpc_writer import _ISCELL_CELLS
from cis2hdl.core.writer.output_manager import _extract_page_number

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "HG5015test"
HDL_LIB = Path(__file__).resolve().parents[1] / "fixtures" / "hdl_lib"


# ── P1-1: page.map page-number extraction ──────────────────────────────

class _FakePage:
    def __init__(self, page_name: str = "", page_id: str = ""):
        self.page_name = page_name
        self.page_id = page_id


class TestP1PageNumberExtraction:
    @pytest.mark.parametrize("name,expected", [
        ("01-Cover_Page", 1),
        ("10-SOC_SerDes", 10),
        ("21-4GE", 21),
        ("02-Block_Diagram", 2),
        ("24-LED_KEY", 24),
    ])
    def test_page_name_prefix(self, name, expected):
        assert _extract_page_number(_FakePage(page_name=name)) == expected

    def test_page_id_fallback(self):
        assert _extract_page_number(_FakePage(page_id="1.5")) == 5

    def test_empty_fallback(self):
        assert _extract_page_number(_FakePage()) == 0

    def test_edif_pages_real_numbers(self):
        """All 24 HG5015 EDIF pages map to distinct physical numbers."""
        ir = EDIFParser().parse(FIXTURES / "HG5015-BE36_V10.EDF")
        nums = [_extract_page_number(p) for p in ir.pages]
        assert len(nums) == 24
        assert len(set(nums)) == 24
        assert min(nums) == 1 and max(nums) == 24


# ── P1-2: symbol.css default attributes ────────────────────────────────

class TestP1SymbolCssDefaults:
    @pytest.mark.parametrize("sym", ["ch347", "rf_sw", "rj45_2x2_led"])
    def test_required_attributes(self, sym):
        css = (HDL_LIB / sym / "sym_1" / "symbol.css").read_text(encoding="utf-8")
        for attr in ("$LOCATION", "VALUE", "PART_NAME", "PATH"):
            assert f'P "{attr}"' in css, f"{sym} missing {attr}"

    def test_parser_reads_new_attributes(self):
        for sym in ("ch347", "rf_sw", "rj45_2x2_led"):
            text = (HDL_LIB / sym / "sym_1" / "symbol.css").read_text(encoding="utf-8")
            defn = SymbolCssParser().parse(text)
            keys = {a.key for a in defn.attributes}
            assert {"$LOCATION", "VALUE", "PART_NAME", "PATH"} <= keys


# ── P1-3: csa $LOCATION ────────────────────────────────────────────────

class TestP1CsaLocation:
    def test_main_emit_uses_dollar_location(self):
        """The conn instance block emits $LOCATION unconditionally."""
        src = (Path(__file__).resolve().parents[2] / "cis2hdl" /
               "core" / "writer" / "csa_writer.py").read_text(encoding="utf-8")
        # P1-3: single `FORCEPROP 1 LAST $LOCATION` in the conn path
        assert 'FORCEPROP 1 LAST $LOCATION {refdes}' in src
        # No legacy section>1 branch left in that block
        assert "if section > 1:\n            a(f\"FORCEPROP 1 LAST $LOCATION" not in src

    def test_converted_csa_uses_dollar_location(self):
        """End-to-end: page2.csa from the last conversion has no bare LOCATION."""
        candidates = sorted(Path("/tmp").glob("p1_verify*/worklib/5015/sch_1/page2.csa"))
        if not candidates:
            pytest.skip("no P1 conversion output on disk")
        content = candidates[-1].read_text(encoding="utf-8", errors="replace")
        assert re.search(r"FORCEPROP 1 LAST \$LOCATION [A-Z]", content)
        # bare `FORCEPROP 1 LAST LOCATION X` (not CDS_LOCATION) should be gone
        bare = re.findall(r"FORCEPROP 1 LAST LOCATION [A-Z0-9]+", content)
        assert bare == []


# ── P1-4: rotation / mirror / NC / electrical type ─────────────────────

class TestP1EdifTransform:
    def test_orientation_extracted(self):
        ir = EDIFParser().parse(FIXTURES / "HG5015-BE36_V10.EDF")
        rotated = mirror = 0
        for p in ir.pages:
            for inst in p.instances:
                if inst.rotation:
                    rotated += 1
                if inst.mirror:
                    mirror += 1
        # EDIF has 3842 orientation statements (R90×3152 / R180 / R270 /
        # MY / MX...); instances carrying them must be captured.
        assert rotated > 100
        assert mirror > 50

    def test_component_ir_has_nc_pins_field(self):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        inst = ComponentInstanceIR(refdes="U1", library_id="chip")
        assert inst.nc_pins == set()
        assert inst.mirror == 0

    def test_symbol_pin_has_electrical_type_field(self):
        from cis2hdl.core.parser.symbol_css import SymbolPin
        pin = SymbolPin(number="1", name="IN")
        assert pin.electrical_type == ""
        assert pin.pin_shape == ""


# ── P1-5: cpc mark uses #CELL ──────────────────────────────────────────

class TestP1CpcMark:
    def test_mark_not_in_iscell_cells(self):
        assert "mark" not in _ISCELL_CELLS

    def test_reference_cpc_uses_cell_for_mark(self):
        refs = [
            Path("docs_for_reference/OrCAD_files_references/cis_for_reference/"
                 "worklib/8367/sch_1/page1.cpc"),
            Path("docs_for_reference/previous_switch_programme/交换机练习/"
                 "OSJZX-6100F-RTK/OSJZX-6100F-RTK/OSJZX-6100F-RTK/"
                 "OSJZX-6100F-RTK/OSJZX-6100F-RTK/worklib/04p4/sch_1/page9.cpc"),
        ]
        found = False
        for ref in refs:
            if not ref.exists():
                continue
            content = ref.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"#(CELL|ISCELL)\s*\n\s*hdl_lib mark \*", content)
            assert m is not None, f"mark block missing in {ref}"
            assert m.group(1) == "CELL", f"{ref} emits mark as #ISCELL"
            found = True
        assert found, "no reference cpc found"


# ── P2-1: rotation / mirror of pin offsets ─────────────────────────────

class TestP2Rotation:
    def test_rotate_point_90(self):
        from cis2hdl.core.writer.coord_transform import rotate_point
        # capacitor sym_1 (0,-75)/(0,50) rotated 90° → sym_2 横向
        assert rotate_point(0, -75, 90) == (75, 0)
        assert rotate_point(0, 50, 90) == (-50, 0)

    def test_rotate_point_180(self):
        from cis2hdl.core.writer.coord_transform import rotate_point
        assert rotate_point(10, 20, 180) == (-10, -20)

    def test_rotate_point_mirror(self):
        from cis2hdl.core.writer.coord_transform import rotate_point
        assert rotate_point(10, 20, 0, 1) == (10, -20)   # flip Y
        assert rotate_point(10, 20, 0, 2) == (-10, 20)   # flip X

    def test_rotate_point_mirror_plus_rotation(self):
        """Phase XVI: EDIF 2.0.0 复合顺序 = 镜像在前、旋转在后。"""
        from cis2hdl.core.writer.coord_transform import rotate_point
        # MYR90 = MY(x→-x) 后 R90： (10,20) → (-10,20) → (-20,-10)
        assert rotate_point(10, 20, 90, 2) == (-20, -10)
        # MXR90 = MX(y→-y) 后 R90： (10,20) → (10,-20) → (20,10)
        assert rotate_point(10, 20, 90, 1) == (20, 10)
        # R180 + MX：先镜像 (10,-20) 再 180 → (-10,20)
        assert rotate_point(10, 20, 180, 1) == (-10, 20)
        # 复合后仍为 int（round 行为）
        rx, ry = rotate_point(3, 7, 90, 2)
        assert isinstance(rx, int) and isinstance(ry, int)

    def test_rotate_bbox(self):
        from cis2hdl.core.writer.coord_transform import rotate_bbox
        out = rotate_bbox("-50,0,50,-25", 90)
        # (x1,y1)=(0,-50), (x2,y2)=(25,50) after R90
        assert out == "0,-50,25,50"

    def test_edif_orientation_captured(self):
        """EDIF transform orientation → rotation/mirror (P1-4 data present)."""
        from cis2hdl.core.parser.edif_parser import EDIFParser
        ir = EDIFParser().parse(FIXTURES / "HG5015-BE36_V10.EDF")
        rots = [i.rotation for p in ir.pages for i in p.instances if i.rotation]
        mirs = [i.mirror for p in ir.pages for i in p.instances if i.mirror]
        assert len(rots) > 500
        assert len(mirs) > 100


# ── P2-2: NC pins excluded from nets ────────────────────────────────────

class TestP2NcPins:
    def test_net_pin_map_skips_nc(self):
        """csa_writer must not group NC pins into net_pin_map."""
        src = (Path(__file__).resolve().parents[2] / "cis2hdl" /
               "core" / "writer" / "csa_writer.py").read_text(encoding="utf-8")
        assert 'net_display.strip().upper() != "NC"' in src

    def test_component_ir_nc_pins_field_exists(self):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        inst = ComponentInstanceIR(refdes="U1", library_id="chip")
        assert hasattr(inst, "nc_pins")
        assert inst.nc_pins == set()

    def test_pstxnet_nc_count(self):
        from cis2hdl.core.parser.pstxnet_netlist_parser import PstxnetNetlistParser
        pst = PstxnetNetlistParser().parse(FIXTURES / "pstxnet.dat")
        nc_total = sum(
            1 for pins in pst.values()
            for pin, net in pins.items() if net.strip().upper() == "NC"
        )
        assert nc_total >= 60


# ── P0-A3: off-page connectors complete (522 + 243 = 765) ──────────────

class TestP0A3OffPage:
    def test_offpage_total_matches_edif(self):
        """Page-level (522) + design-level (243) off-pages = 765 raw count."""
        from cis2hdl.core.parser.edif_parser import EDIFParser
        ir = EDIFParser().parse(FIXTURES / "HG5015-BE36_V10.EDF")
        page_off = sum(len(p.off_pages) for p in ir.pages)
        design_off = ir.metadata.get("design_off_pages", [])
        assert page_off >= 500
        assert len(design_off) >= 200
        # raw occurrences in the file
        raw = (FIXTURES / "HG5015-BE36_V10.EDF").read_text(
            encoding="utf-8", errors="replace"
        )
        raw_count = raw.count("OFF_PAGE_CONNECTOR")
        assert page_off + len(design_off) == raw_count

    def test_design_off_pages_have_names(self):
        from cis2hdl.core.parser.edif_parser import EDIFParser
        ir = EDIFParser().parse(FIXTURES / "HG5015-BE36_V10.EDF")
        dop = ir.metadata.get("design_off_pages", [])
        assert all("name" in op and "net_name" in op for op in dop)


# ── CH347 pin bridge: chips.prt number → functional name ───────────────

class TestChipsPrtPinBridge:
    def test_pin_name_map(self):
        from cis2hdl.core.writer.csa_writer import CSAWriter
        w = CSAWriter(hdl_lib_path=str(HDL_LIB))
        pm = w._get_pin_name_map("CH347")
        assert len(pm) >= 15
        assert pm.get("1") == "RST#"
        assert pm.get("3") == "TXD1"

    def test_pin_name_map_lowercase(self):
        from cis2hdl.core.writer.csa_writer import CSAWriter
        w = CSAWriter(hdl_lib_path=str(HDL_LIB))
        pm = w._get_pin_name_map("ch347")
        assert len(pm) >= 15


# ── P0-C5: cross-page IOPORT symbols ───────────────────────────────────

class TestP0C5Ioport:
    def test_page_connectivity_carries_off_pages(self):
        """PageConnectivity now carries off_pages for IOPORT generation."""
        from cis2hdl.core.writer.connectivity_model import PageConnectivity
        pc = PageConnectivity(page_num=1, page_name="P1")
        assert pc.off_pages == []

    def test_ioport_block_structure(self):
        """_emit_ioport_block emits OFFPAGE TRUE + HDL_PORT + CDS_LIB."""
        src = (Path(__file__).resolve().parents[2] / "cis2hdl" /
               "core" / "writer" / "csa_writer.py").read_text(encoding="utf-8")
        assert "FORCEADD IOPORT..1" in src or "FORCEADD {body}..1" in src
        assert "OFFPAGE TRUE" in src
        assert "HDL_PORT INOUT" in src

    def test_ioport_level1_lastpin_no_outline(self):
        """Phase XIII T2: IOPORT LASTPIN is level 1; no CDS_LMAN_SYM_OUTLINE.

        Level-3 LASTPIN on IOPORT was the root cause of SPCOCN-543/541
        (Cadence bound file-end LASTPINs to the last FORCEADD IOPORT and
        deleted the unknown pins).  Level 1 matches 04p4/eeworm.
        """
        src = (Path(__file__).resolve().parents[2] / "cis2hdl" /
               "core" / "writer" / "csa_writer.py").read_text(encoding="utf-8")
        assert "FORCEPROP 1 LASTPIN ({px} {py}) HDL_PORT INOUT" in src
        assert "FORCEPROP 1 LASTPIN ({px} {py}) VHDL_PORT INOUT" in src
        # the old level-3 IOPORT template must be gone
        assert "FORCEPROP 3 LASTPIN ({px} {py}) HDL_PORT INOUT" not in src
        # no CDS_LMAN_SYM_OUTLINE emission inside the IOPORT block
        assert "CDS_LMAN_SYM_OUTLINE {body}" not in src
        # uniform 0.872340 label scale (04p4 evidence)
        assert "DISPLAY {_SCALE_IOPORT}" in src
        assert "_SCALE_IOPORT: float = 0.872340" in src

    def test_ioport_pin_coord_body_minus_50(self):
        """IOPORT pin-A coordinate = body + css C -50 0 'A'."""
        from cis2hdl.core.writer.csa_writer import CSAWriter
        w = CSAWriter(hdl_lib_path=str(HDL_LIB))
        # index 0 → body (-600, 7300); pin = (-600-50, 7300+0) = (-650, 7300)
        assert w._ioport_pin_coord(0) == (-650, 7300)

    def test_hl_lib_has_ioport_symbols(self):
        for sym in ("IOPORT", "INPORT", "OUTPORT"):
            assert (HDL_LIB / sym / "sym_1" / "symbol.css").exists()
