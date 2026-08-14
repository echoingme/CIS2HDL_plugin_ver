"""Phase XI P0-B/P0-C unit tests — T01 infrastructure.

Covers:
  * net_utils DEHDL naming (con_name / csv_display_name / auto_net_name)
  * CoordTransform page mapping
  * WireLayoutEngine trunk+stub routing / DOT computation
  * SymbolCssPinParser C-command pin offsets
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
#  net_utils naming (system_design.md C.5 three-state naming)
# ---------------------------------------------------------------------------


class TestNetUtilsNaming:
    def test_con_name_global(self):
        from cis2hdl.core.net_utils import con_name
        assert con_name("GND_POWER\\g") == "gnd_power"
        assert con_name("VCC_12\\g") == "vcc_12"
        assert con_name("CLK2SLAVE_OUTN_5G") == "clk2slave_outn_5g"

    def test_con_name_local_prefix(self):
        from cis2hdl.core.net_utils import con_name
        assert con_name("GND_POWER\\g", page=1, local=True) == "page1_gnd_power"
        assert con_name("CLK2SLAVE_OUTN_5G", page=3, local=True) == "page3_clk2slave_outn_5g"

    def test_con_name_dollar_to_underscore(self):
        from cis2hdl.core.net_utils import con_name
        assert con_name("$27N444466") == "27n444466"
        assert con_name("$27N444466", page=2, local=True) == "page2_27n444466"

    def test_con_name_ampersand_escape(self):
        from cis2hdl.core.net_utils import con_name
        assert con_name("&3V3_SOC") == "3v3_soc"

    def test_csv_display_name_global(self):
        from cis2hdl.core.net_utils import csv_display_name
        assert csv_display_name("GND_POWER", is_global=True) == "GND_POWER\\g"
        assert csv_display_name("VCC_12", is_global=True) == "VCC_12\\g"
        assert csv_display_name("VCC_12\\g", is_global=True) == "VCC_12\\g"

    def test_csv_display_name_local(self):
        from cis2hdl.core.net_utils import csv_display_name
        assert csv_display_name("CLK2SLAVE_OUTN_5G") == "CLK2SLAVE_OUTN_5G"
        assert csv_display_name("UN$1$CAPACITOR$I12$1") == "UN$1$CAPACITOR$I12$1"

    def test_auto_net_name_roundtrip(self):
        from cis2hdl.core.net_utils import auto_net_con_name, auto_net_csv_name
        con = auto_net_con_name(1, "capacitor", 12, "1")
        assert con == "unnamed_1_capacitor_i12_1"
        assert auto_net_csv_name(con) == "UN$1$CAPACITOR$I12$1"

    def test_auto_net_name_non_auto(self):
        from cis2hdl.core.net_utils import auto_net_csv_name
        assert auto_net_csv_name("gnd_power") == "gnd_power"

    def test_net_scope(self):
        from cis2hdl.core.net_utils import net_scope
        # power net on >= 2 pages -> global scope=2, bare name
        scope, name = net_scope("GND_POWER", appears_on_pages=3, page_num=1)
        assert scope == 2 and name == "gnd_power"
        # power net on 1 page -> local scope=0, pageN_ prefix
        scope, name = net_scope("VCC_12", appears_on_pages=1, page_num=2)
        assert scope == 0 and name == "page2_vcc_12"
        # flat net -> local
        scope, name = net_scope("CLK2SLAVE_OUTN_5G", appears_on_pages=1, page_num=1)
        assert scope == 0 and name == "page1_clk2slave_outn_5g"


# ---------------------------------------------------------------------------
#  CoordTransform (system_design.md B.3)
# ---------------------------------------------------------------------------


class _Inst:
    def __init__(self, refdes: str, x: int, y: int) -> None:
        self.refdes = refdes
        self.loc_x = x
        self.loc_y = y


class TestCoordTransform:
    def test_map_page_preserves_relative_order(self):
        from cis2hdl.core.writer.coord_transform import CoordTransform
        ct = CoordTransform()
        insts = [_Inst("C1", 4500, 12000), _Inst("R1", 5000, 13000), _Inst("U1", 6000, 9000)]
        mapped = ct.map_page(insts)
        assert len(mapped) == 3
        # mapped X order must follow source X order
        assert mapped["C1"][0] < mapped["R1"][0] < mapped["U1"][0]
        # all inside C-page usable area
        for x, y in mapped.values():
            assert ct.page_x0 <= x <= ct.page_x1
            assert ct.page_y0 <= y <= ct.page_y1

    def test_map_page_ignores_zero_coords(self):
        from cis2hdl.core.writer.coord_transform import CoordTransform
        ct = CoordTransform()
        insts = [_Inst("C1", 0, 0), _Inst("R1", 100, 200)]
        mapped = ct.map_page(insts)
        assert "C1" not in mapped
        assert "R1" in mapped

    def test_grid_position(self):
        from cis2hdl.core.writer.coord_transform import CoordTransform
        p0 = CoordTransform.grid_position(0)
        p1 = CoordTransform.grid_position(1)
        p5 = CoordTransform.grid_position(5)  # second row
        assert p0 != p1 and p1 != p5


# ---------------------------------------------------------------------------
#  WireLayoutEngine (system_design.md B.4)
# ---------------------------------------------------------------------------


class TestWireLayoutEngine:
    def test_route_three_pin_net(self):
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        pins = [(100, 100), (300, 150), (500, 200)]
        routed = WireLayoutEngine().route_net("N1", pins)
        # 3 off-trunk pins -> 3 vertical stubs + trunk pieces (>= 3 segments)
        assert len(routed.wires) >= 3
        endpoints = set()
        for w in routed.wires:
            endpoints.add((w.x1, w.y1))
            endpoints.add((w.x2, w.y2))
        # Connection rule (04p4 evidence): every pin must be a wire endpoint
        for p in pins:
            assert p in endpoints
        # Non-pin endpoints are trunk junctions (y == trunk y), where DOTs go
        trunk_ys = {w.y1 for w in routed.wires if w.is_horizontal}
        non_pin = endpoints - set(pins)
        if trunk_ys:
            for pt in non_pin:
                assert pt[1] in trunk_ys

    def test_route_single_pin_net_no_wire(self):
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        routed = WireLayoutEngine().route_net("N1", [(100, 100)])
        assert routed.wires == []
        assert routed.sig_name_pos == (100, 100)

    def test_compute_dots_tee_junction(self):
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine, WireSegment
        wires = [
            WireSegment(0, 0, 100, 0),   # trunk
            WireSegment(50, 0, 50, 50),  # stub joins trunk at (50, 0)
        ]
        dots = WireLayoutEngine().compute_dots(wires)
        assert (50, 0) in dots  # T-junction

    def test_avoid_body_outline(self):
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        pins = [(100, 100), (300, 110), (500, 105)]
        outlines = [(80.0, 90.0, 520.0, 120.0)]  # trunk y ~105 falls inside
        routed = WireLayoutEngine().route_net("N1", pins, body_outlines=outlines)
        trunk_ys = {w.y1 for w in routed.wires if w.is_horizontal}
        # trunk moved outside the outline y-range
        for ty in trunk_ys:
            assert not (90.0 <= ty <= 120.0)

    def test_route_nets_distinct_trunk_lanes(self):
        """Phase XIII T4: overlapping-span nets must not share a trunk lane."""
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        net_pin_map = {
            "N1": [(100, 100), (300, 150), (500, 200)],   # median y 150
            "N2": [(120, 105), (320, 145), (520, 195)],   # median y 145 → snap 150
        }
        results = WireLayoutEngine().route_nets(net_pin_map)
        assert set(results) == {"N1", "N2"}
        trunk_ys = []
        for name, routed in results.items():
            h = [w for w in routed.wires if w.is_horizontal]
            assert h, f"{name} has no trunk"
            trunk_ys.extend(w.y1 for w in h)
        # at least two distinct trunk y values (lane differentiation)
        assert len(set(trunk_ys)) >= 2, f"trunks not differentiated: {trunk_ys}"

    def test_route_nets_accepts_pin_dicts(self):
        """route_nets accepts csa_writer net_pin_map dict entries."""
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        net_pin_map = {
            "NET_A": [
                {"refdes": "R1", "pin": "1", "coord": (100, 100)},
                {"refdes": "R2", "pin": "1", "coord": (400, 160)},
                {"refdes": "R3", "pin": "1", "coord": (700, 130)},
            ],
        }
        results = WireLayoutEngine().route_nets(net_pin_map)
        assert "NET_A" in results
        endpoints = set()
        for w in results["NET_A"].wires:
            endpoints.add((w.x1, w.y1))
            endpoints.add((w.x2, w.y2))
        # every pin must remain a wire endpoint (connection rule)
        for p in net_pin_map["NET_A"]:
            assert tuple(p["coord"]) in endpoints

    def test_route_nets_avoids_body_outlines(self):
        """Route nets must keep trunks out of body rectangles."""
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        net_pin_map = {
            "N1": [(100, 100), (300, 150), (500, 200)],
        }
        outlines = [(80.0, 90.0, 520.0, 120.0)]
        routed = WireLayoutEngine().route_nets(net_pin_map, body_outlines=outlines)["N1"]
        trunk_ys = {w.y1 for w in routed.wires if w.is_horizontal}
        for ty in trunk_ys:
            assert not (90.0 <= ty <= 120.0)

    def test_route_nets_touching_trunk_spans_separated(self):
        """Phase XIII Round 2 (short-circuit bug): trunks whose spans meet
        at an endpoint must NOT share a lane.

        DEHDL connects coincident endpoints — if net A's trunk ends at
        x=400 and net B's trunk starts at x=400 on the same y, they short.
        The lane conflict test must use a CLOSED interval (<=).
        """
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        net_pin_map = {
            "NA": [(100, 100), (400, 150)],   # trunk span x [100, 400]
            "NB": [(400, 100), (700, 150)],   # trunk span x [400, 700] — touches
        }
        results = WireLayoutEngine().route_nets(net_pin_map)
        trunk_ys = {}
        for name in ("NA", "NB"):
            ys = {w.y1 for w in results[name].wires if w.is_horizontal}
            assert ys, f"{name} has no trunk"
            trunk_ys[name] = ys
        # different lanes → trunks do not share the touching coordinate
        assert trunk_ys["NA"] != trunk_ys["NB"], (
            f"touching trunks share a lane: {trunk_ys} → short"
        )

    def test_route_nets_all_endpoints_on_grid(self):
        """Phase XIII T1/T4: every generated WIRE endpoint is on the 25 grid."""
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        net_pin_map = {
            "NA": [(100, 100), (400, 150), (700, 125)],
            "NB": [(125, 300), (525, 325), (900, 275)],
            "NC": [(200, 500), (600, 550), (800, 525)],
        }
        results = WireLayoutEngine().route_nets(net_pin_map)
        for name, routed in results.items():
            for w in routed.wires:
                for v in (w.x1, w.y1, w.x2, w.y2):
                    assert v % 25 == 0, f"{name}: off-grid coord {v}"

    def test_route_nets_no_shared_endpoint_between_nets(self):
        """Phase XIII Round 2: different nets must not share any WIRE
        endpoint — coordinate coincidence is a DEHDL connection (short)."""
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        net_pin_map = {
            "NA": [(100, 100), (400, 150), (700, 125)],
            "NB": [(125, 300), (525, 325), (900, 275)],
            "NC": [(200, 500), (600, 550), (800, 525)],
        }
        results = WireLayoutEngine().route_nets(net_pin_map)
        owner: dict[tuple[int, int], str] = {}
        for name, routed in results.items():
            for w in routed.wires:
                for pt in ((w.x1, w.y1), (w.x2, w.y2)):
                    assert pt not in owner or owner[pt] == name, (
                        f"endpoint {pt} shared by {owner[pt]} and {name} → short"
                    )
                    owner[pt] = name

    def test_route_nets_trunk_avoids_other_pin(self):
        """Phase XIII Round 2: a trunk must not pass through another net's
        pin (the pin's stub endpoint would land on the trunk → short)."""
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine
        net_pin_map = {
            "NA": [(100, 500), (700, 550)],   # horizontal trunk median y=525
            "NB": [(400, 525), (500, 300)],   # pin (400, 525) on NA's trunk line
        }
        results = WireLayoutEngine().route_nets(net_pin_map)
        na_trunk_ys = {w.y1 for w in results["NA"].wires if w.is_horizontal}
        assert na_trunk_ys, "NA has no trunk"
        for ty in na_trunk_ys:
            assert ty != 525, (
                f"NA trunk at y={ty} passes through NB pin (400,525) → short"
            )
        # NB's own trunk must not pass through NA's pins either
        nb_trunk_xs = {w.x1 for w in results["NB"].wires if w.is_vertical}
        for tx in nb_trunk_xs:
            assert tx not in (100, 700), (
                f"NB trunk at x={tx} passes through NA pin → short"
            )


# ---------------------------------------------------------------------------
#  SymbolCssPinParser (system_design.md B.2)
# ---------------------------------------------------------------------------


class TestSymbolCssPinParser:
    def test_parse_capacitor_offsets(self):
        from cis2hdl.core.parser.symbol_css import SymbolCssPinParser
        css = (
            'C 0 -75 "1" 0 -60 0 0 32 1 R\n'
            'C 0 50 "2" 0 35 0 0 32 1 L\n'
            'P "CDS_LMAN_SYM_OUTLINE" "-25,50,25,-50" 0 0 0 0 0 1 0\n'
        )
        offsets, outline = SymbolCssPinParser().parse(css)
        assert offsets == {"1": (0, -75), "2": (0, 50)}
        assert outline == "-25,50,25,-50"

    def test_parse_dcdc_offsets(self):
        from cis2hdl.core.parser.symbol_css import SymbolCssPinParser
        css = (
            'C 200 -150 "FB" 0 0 0 0 0 32 1 R\n'
            'C -200 150 "IN" 0 0 0 0 0 32 1 L\n'
            'C -200 -150 "GND" 0 0 0 0 0 32 1 L\n'
        )
        offsets, _ = SymbolCssPinParser().parse(css)
        assert offsets["FB"] == (200, -150)
        assert offsets["IN"] == (-200, 150)
        assert offsets["GND"] == (-200, -150)


# ---------------------------------------------------------------------------
#  T02/T03: connectivity model + con/xcon/csv/cpc writers
# ---------------------------------------------------------------------------


def _make_synthetic_design():
    from cis2hdl.core.ir.component import ComponentInstanceIR
    from cis2hdl.core.ir.design import DesignIR, PageIR
    p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
    p1.instances = [
        ComponentInstanceIR(
            refdes="C1", library_id="C1", loc_x=4500, loc_y=12000,
            pin_connections={"1": "GND_POWER", "2": "VCC_12"},
        ),
        ComponentInstanceIR(
            refdes="R1", library_id="R1", loc_x=5000, loc_y=13000,
            pin_connections={"1": "GND_POWER", "2": "NET_A"},
        ),
    ]
    p2 = PageIR(page_id="1.2", page_name="06-Power_Supply2")
    p2.instances = [
        ComponentInstanceIR(
            refdes="C2", library_id="C2", loc_x=4500, loc_y=11000,
            pin_connections={"1": "GND_POWER", "2": "NET_A"},
        ),
    ]
    return DesignIR(project_name="HG5015-BE36_V10", pages=[p1, p2])


class _FakeMatch:
    def __init__(self, sid: str, tid: str) -> None:
        self.source_library_id = sid
        self.target_library_id = tid


class TestConnectivityModel:
    def test_build_counts(self):
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        design = _make_synthetic_design()
        matches = [
            _FakeMatch("C1", "hdl_lib/capacitor"),
            _FakeMatch("R1", "hdl_lib/resistor"),
            _FakeMatch("C2", "hdl_lib/capacitor"),
        ]
        conn = ConnectivityModelBuilder(design, matches=matches).build()
        # 2 unique cells, 6 nets (gnd_power global + 2 local, vcc_12 global
        # + 1 local, net_a flat), 3 instances, 6 pins
        assert conn.cell_count == 2
        assert conn.net_count == 6
        assert conn.instance_count == 3
        assert conn.pin_count == 6
        # power aliases — page numbers come from the page NAME prefix
        # (Phase XIII T0): "05-Power_Supply1" → 5, "06-Power_Supply2" → 6
        assert ("page5_gnd_power", "gnd_power") in conn.aliases
        assert ("page6_gnd_power", "gnd_power") in conn.aliases
        # lastIds consistency
        assert conn.pin_count == sum(len(i.pins) for i in conn.instances)

    def test_power_symbol_excluded_from_con(self):
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        # instances must be non-power (no power symbol cells in synthetic)
        assert all(not i.is_power_symbol for i in conn.instances)


class TestConXconCsvCpcWriters:
    def test_con_sexpr_parseable(self):
        from sexpdata import Symbol, loads
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.con_writer import ConWriter
        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        content = ConWriter._build_con_content(conn)
        tree = loads(content)
        # top-level: (version tool library design)
        assert len(tree) == 4
        assert tree[0][0] == Symbol("version")
        design_block = tree[3]
        assert design_block[0] == Symbol("design")
        # design block: (design "name" (lastIds ...) (cells ...) ...)
        last_ids = design_block[2]
        assert last_ids[0] == Symbol("lastIds")
        assert last_ids[1][0] == Symbol("lastInstanceId")
        assert last_ids[2][0] == Symbol("lastNetId")
        assert last_ids[3][0] == Symbol("lastInstTermId")
        # counts equal model counts
        assert last_ids[1][1] == conn.instance_count
        assert last_ids[2][1] == conn.net_count
        assert last_ids[3][1] == conn.pin_count

    def test_xcon_xml_parseable(self):
        import xml.etree.ElementTree as ET
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.xcon_writer import XconWriter
        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        content = XconWriter._build_xcon_content(conn)
        root = ET.fromstring(content)
        assert root.tag.endswith("schema")
        # pages section has 2 pages
        pages = root.find(".//{*}pages")
        assert pages is not None
        assert len(pages.findall("{*}page")) == 2

    def test_csv_format(self):
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.csv_writer import PageCsvWriter
        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        content = PageCsvWriter()._build_csv_content(conn, conn.pages[0])
        assert content.startswith("FILE_TYPE = CONNECTIVITY;")
        assert content.rstrip().endswith("END.")
        assert '0"NC";' in content
        assert 'GND_POWER\\g' in content
        assert '$PN' in content

    def test_cpc_names_consistent(self):
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.cpc_writer import CpcWriter
        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        content = CpcWriter()._build_cpc_content(conn, conn.pages[0])
        # page5_i1 and page5_i2 appear (real page number from the page
        # NAME prefix "05-Power_Supply1" — Phase XIII T0), shared k with
        # con internal names
        assert "page5_i1" in content
        assert "page5_i2" in content
        # first entry is the page frame
        assert content.startswith("#ISCELL")
        assert "c#20size#20page" in content


class TestCsaWriterConn:
    def test_csa_has_wire_lastpin_sig_name_dot_quit(self):
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.csa_writer import CSAWriter
        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        page_conn = conn.pages[0]
        content = CSAWriter()._build_csa_content_conn(conn, page_conn)
        assert content.startswith("FILE_TYPE = MACRO_DRAWING;")
        assert content.rstrip().endswith("QUIT")
        assert "WIRE 16 -1" in content
        assert "LASTPIN" in content
        assert "SIG_NAME" in content
        assert "DOT 1" in content

    def test_every_connected_pin_has_lastpin(self):
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.csa_writer import CSAWriter
        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        page_conn = conn.pages[0]
        content = CSAWriter()._build_csa_content_conn(conn, page_conn)
        pin_count = sum(len(i.pins) for i in page_conn.instances)
        # every connected pin yields a LASTPIN ($PN level 2, SIG_NAME level
        # 3, or level 1 for IOPORT pins — Phase XIII T2)
        import re
        lastpin_count = len(re.findall(r"FORCEPROP [0-3] LASTPIN", content))
        assert lastpin_count == pin_count

    def test_one_sig_name_per_net(self):
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.csa_writer import CSAWriter
        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        page_conn = conn.pages[0]
        content = CSAWriter()._build_csa_content_conn(conn, page_conn)
        import re
        sig_names = re.findall(r"SIG_NAME (\S+)", content)
        # page 1 nets: GND_POWER\g, VCC_12\g, NET_A — one label each
        assert len(sig_names) == 3
        assert sig_names.count("GND_POWER\\g") == 1
        assert sig_names.count("VCC_12\\g") == 1
        assert sig_names.count("NET_A") == 1

    def test_wire_endpoints_include_pins(self):
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.csa_writer import CSAWriter
        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        page_conn = conn.pages[0]
        content = CSAWriter()._build_csa_content_conn(conn, page_conn)
        import re
        # parse WIRE endpoints
        wires = re.findall(r"WIRE 16 -1 \((-?\d+) (-?\d+)\)\((-?\d+) (-?\d+)\);", content)
        endpoints = set()
        for w in wires:
            endpoints.add((int(w[0]), int(w[1])))
            endpoints.add((int(w[2]), int(w[3])))
        # nets with >= 2 pins on the page get wires; their pins must be
        # wire endpoints (connection rule)
        multi_pin_nets = {
            pnr.bare_name for pnr in page_conn.nets if len(pnr.connections) >= 2
        }
        lastpins = re.findall(r"LASTPIN \((-?\d+) (-?\d+)\) SIG_NAME (\S+)", content)
        for x, y, sig in lastpins:
            bare = sig.replace("\\g", "").lower()
            if bare in multi_pin_nets:
                assert (int(x), int(y)) in endpoints
        # GND_POWER has 2 pins on page 1 → both must be endpoints
        gnd_pins = {(int(x), int(y)) for x, y, sig in lastpins if sig == "GND_POWER\\g"}
        assert len(gnd_pins) >= 1
        for pc in gnd_pins:
            assert pc in endpoints


class TestXconXmlEscape:
    """SPCOCD-553 根因修复：xcon 是 XML，名称必须转义。

    真实数据中 MARK 元件自动网络名含裸 ``&``（如
    ``unnamed_22_mark_i73_&1``）→ 未转义时 XML 解析失败
    （not well-formed）→ Cadence 加载 5015.xcon 报 syntax error。
    """

    def test_xml_escape_ampersand(self):
        from cis2hdl.core.writer.xcon_writer import _xml

        assert _xml("unnamed_22_mark_i73_&1") == "unnamed_22_mark_i73_&amp;1"
        assert _xml("A<B>C\"D'E") == "A&lt;B&gt;C&quot;D&apos;E"

    def test_xcon_with_special_names_parseable(self):
        """含 & 的网络名经转义后生成的 xcon 必须可 XML 解析。"""
        import xml.etree.ElementTree as ET
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.xcon_writer import XconWriter

        design = _make_synthetic_design()
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        # 注入含特殊字符的网络名（模拟 MARK 自动命名）
        for net in conn.nets:
            if "unnamed" in net.internal_name:
                net.internal_name = net.internal_name + "_&1"
        content = XconWriter._build_xcon_content(conn)
        # 裸 & 必须为 0
        assert "&1" not in content.replace("&amp;1", "")
        root = ET.fromstring(content)
        assert root.tag.endswith("schema")
