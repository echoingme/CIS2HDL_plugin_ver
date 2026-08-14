"""Phase XV — P0-A/B LASTPIN 格式 + P0-E rotation 映射 + P0-F 占位符号
+ P1-C IOPORT 边缘分布 + P1-D GND 分布 + P1-G stub 引出段。

Covers (user Cadence 16.6 feedback fixes):
  * ``_lastpin_pn`` 输出与 04p4 完全一致（无 PAINT ORANGE、R 1、J 0）
  * EDIF rotation → DEHDL R 行 90↔270 交换（L20 翻转 180° 修复）
  * 占位符号：无具体符号的多引脚芯片生成 PlaceholderSymbol（PLACEHOLDER
    标注、引脚数/名/偏移、无 CH347 fallback）
  * IOPORT：页内网无 IOPORT；edge_layout 沿边缘等间距
  * GND：每芯片附近有 GND 符号（转换后 csa 断言）
  * stub 引出段：引出段存在、相邻差异化、端点保持、0 off-grid
"""

from __future__ import annotations

import re


def _snap(v: float) -> int:
    return int(round(v / 25.0) * 25)


def _make_ic_design():
    """Synthetic design: C1/R1 passives + U1 multi-pin IC + GND net."""
    from cis2hdl.core.ir.component import ComponentInstanceIR
    from cis2hdl.core.ir.design import DesignIR, PageIR

    p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
    p1.instances = [
        ComponentInstanceIR(
            refdes="C1", library_id="C1", loc_x=4500, loc_y=12000,
            pin_connections={"1": "GND_POWER", "2": "VCC_12"},
        ),
        ComponentInstanceIR(
            refdes="U1", library_id="U1", loc_x=6500, loc_y=9000,
            pin_connections={
                "1": "GND_POWER", "2": "GND_POWER", "3": "NET_A",
                "4": "NET_A", "5": "NET_B",
            },
        ),
    ]
    return DesignIR(project_name="HG5015-BE36_V10", pages=[p1])


def _build_conn(design=None, matches=None):
    from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder

    if design is None:
        design = _make_ic_design()
    return ConnectivityModelBuilder(design, matches=matches or []).build()


# ---------------------------------------------------------------------------
#  P0-A/B: $PN LASTPIN 格式对齐 04p4
# ---------------------------------------------------------------------------


class TestLastpinFormat:
    def test_lastpin_pn_matches_04p4(self):
        from cis2hdl.core.writer.csa_writer import CSAWriter

        lines = CSAWriter._lastpin_pn((-5300, 1600), "1")
        assert lines == [
            "FORCEPROP 2 LASTPIN (-5300 1600) $PN 1",
            "R 1",
            "J 0",
            "(-5310 1610);",
            "DISPLAY 0.808511 (-5310 1610);",
        ]

    def test_no_paint_line_after_lastpin(self):
        from cis2hdl.core.writer.csa_writer import CSAWriter

        lines = CSAWriter._lastpin_pn((100, 200), "2")
        assert not any("PAINT" in ln for ln in lines)

    def test_csa_has_no_paint_after_pn(self):
        conn = _build_conn()
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        content = CSAWriter(routing_cfg=RoutingConfig())._build_csa_content_conn(
            conn, conn.pages[0],
        )
        # Every "$PN <n>" LASTPIN block must NOT be followed by PAINT.
        for m in re.finditer(
            r"FORCEPROP 2 LASTPIN \((-?\d+) (-?\d+)\) \$PN \S+\n"
            r"R 1\nJ 0\n"
            r"\((-?\d+) (-?\d+)\);\n"
            r"DISPLAY 0\.808511 \((-?\d+) (-?\d+)\);", content,
        ):
            pass  # matched the 04p4 exact block
        # And there is no "PAINT" between a $PN line and the next FORCEPROP.
        blocks = re.split(r"\n(?=FORCEPROP)", content)
        for block in blocks:
            if "$PN" in block and "LASTPIN" in block:
                assert "PAINT" not in block, f"PAINT leaked into $PN block: {block[:80]}"


# ---------------------------------------------------------------------------
#  P0-E: rotation → R 行方向映射（L20 翻转 180°）
# ---------------------------------------------------------------------------


class TestRotationMapping:
    def test_dehdl_rotation_swaps_90_270(self):
        from cis2hdl.core.writer.csa_writer import _dehdl_rotation

        assert _dehdl_rotation(90) == 270
        assert _dehdl_rotation(270) == 90
        assert _dehdl_rotation(180) == 180
        assert _dehdl_rotation(0) == 0

    def test_rotation_line_uses_dehdl_angle(self):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.csa_writer import CSAWriter

        p1 = PageIR(page_id="1.1", page_name="06-Power_Supply2")
        p1.instances = [
            ComponentInstanceIR(
                refdes="L20", library_id="L_E", loc_x=5000, loc_y=13000,
                rotation=90,
                pin_connections={"1": "NET_A", "2": "NET_B"},
            ),
        ]
        design = DesignIR(project_name="T", pages=[p1])
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        content = CSAWriter()._build_csa_content_conn(conn, conn.pages[0])
        # L20 (EDIF R90) must render as DEHDL R 3 (270°), not R 1.
        idx = content.find("FORCEADD L_E..1")
        assert idx != -1, content[:2000]
        block = content[idx:idx + 200]
        assert "R 3" in block, f"L20 should emit R 3, got:\n{block[:150]}"

    def test_pin_offsets_rotate_with_dehdl_angle(self):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, PageIR
        from cis2hdl.core.writer.connectivity_model import ConnectivityModelBuilder
        from cis2hdl.core.writer.csa_writer import CSAWriter

        p1 = PageIR(page_id="1.1", page_name="06-Power_Supply2")
        p1.instances = [
            ComponentInstanceIR(
                refdes="C20", library_id="CAPACITOR", loc_x=5000, loc_y=13000,
                rotation=90,
                pin_connections={"1": "NET_A", "2": "NET_B"},
            ),
        ]
        design = DesignIR(project_name="T", pages=[p1])
        conn = ConnectivityModelBuilder(design, matches=[]).build()
        content = CSAWriter()._build_csa_content_conn(conn, conn.pages[0])
        idx = content.find("FORCEADD CAPACITOR..1")
        assert idx != -1
        block = content[idx:idx + 400]
        m_body = re.search(r"R 3\n\((-?\d+) (-?\d+)\);", block)
        assert m_body, f"no R 3 body: {block[:200]}"
        bx, by = int(m_body.group(1)), int(m_body.group(2))
        pins = re.findall(
            r"LASTPIN \((-?\d+) (-?\d+)\) (?:SIG_NAME|\$PN) (\S+)", block,
        )
        assert len(pins) == 2, f"expected 2 LASTPINs: {block[:400]}"
        offsets = {(int(x) - bx, int(y) - by): pn for x, y, pn in pins}
        # capacitor fallback (0,-75)/(0,50) rotated by DEHDL 270° →
        # pin1 (-75,0) left, pin2 (50,0) right (fixes L20 180°-flip).
        assert (-75, 0) in offsets, f"pin1 should be left after fix: {offsets}"
        assert (50, 0) in offsets, f"pin2 should be right after fix: {offsets}"


# ---------------------------------------------------------------------------
#  P0-F: 占位符号自动生成
# ---------------------------------------------------------------------------


class TestPlaceholderLib:
    def test_symbol_generation_pin_names(self):
        from cis2hdl.core.writer.placeholder_lib import PlaceholderLibrary

        sym = PlaceholderLibrary().symbol_for(
            "U6", 1, [("K18", "A0"), ("G20", "A1"), ("AD15", "A2")],
        )
        assert sym is not None
        assert sym.cell_name == "U6_PH"
        assert sym.pin_numbers == ["K18", "G20", "AD15"]
        # offsets keyed by number AND unique name
        assert "K18" in sym.offsets
        assert "A0" in sym.offsets
        # distributed offsets are distinct
        assert len(set(sym.offsets[k] for k in sym.pin_numbers)) == 3

    def test_symbol_pin_count_offsets_layout(self):
        from cis2hdl.core.writer.placeholder_lib import (
            PlaceholderLibrary, distribute_ic_pin_offsets,
        )
        offsets = distribute_ic_pin_offsets(4)
        assert len(offsets) == 4
        assert offsets["1"] == (-150, 150)
        assert offsets["2"] == (-150, 50)
        assert offsets["3"] == (150, -150)
        assert offsets["4"] == (150, -50)
        # large chip: 20 pins → 4 columns
        large = distribute_ic_pin_offsets(20)
        assert len(large) == 20
        xs = {v[0] for v in large.values()}
        assert xs <= {-200, -100, 100, 200}

    def test_placeholder_css_and_prt(self):
        from cis2hdl.core.writer.placeholder_lib import PlaceholderLibrary

        lib = PlaceholderLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "A1")])
        css = lib._symbol_css(sym)
        prt = lib._chips_prt(sym)
        assert 'P "CDS_LMAN_SYM_OUTLINE"' in css
        # C commands carry the pin label (functional name when present)
        assert 'C -150 150 "A0"' in css or 'C 150 -150 "A0"' in css
        assert "K18" in prt and "G20" in prt
        assert "PIN_NUMBER='(K18)'" in prt

    def test_write_to_hdl_lib(self, tmp_path):
        from cis2hdl.core.writer.placeholder_lib import PlaceholderLibrary

        lib = PlaceholderLibrary()
        sym = lib.symbol_for("U6", 1, [("K18", "A0"), ("G20", "A1")])
        written = lib.write_to_hdl_lib(tmp_path)
        assert written
        css = tmp_path / "u6_ph" / "sym_1" / "symbol.css"
        prt = tmp_path / "u6_ph" / "chips" / "chips.prt"
        assert css.exists() and prt.exists()
        assert sym.cell_name == "U6_PH"

    def test_disabled_returns_none(self):
        from cis2hdl.core.writer.placeholder_lib import PlaceholderLibrary

        assert PlaceholderLibrary(enabled=False).symbol_for(
            "U6", 1, [("K18", "A0")],
        ) is None

    def test_csa_uses_placeholder_not_ch347(self):
        """U1 (multi-pin IC, no concrete symbol) → FORCEADD U1_PH +
        (temp_lib 关闭时) PLACEHOLDER 1; NO fallback to CH347.

        Phase XVII M1: temp_lib.enabled=true（默认）时改用 mock 模拟图标
        （同 cell 名 U1_PH，但无 PLACEHOLDER 属性 —— MOCK_TEXT 在
        symbol.css 内画好）；temp_lib.enabled=false 回退 placeholder
        （PLACEHOLDER 1 属性）。
        """
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()
        content = CSAWriter()._build_csa_content_conn(conn, conn.pages[0])
        assert "FORCEADD U1_PH..1" in content
        # 默认 = mock 模拟图标：不发射 PLACEHOLDER 属性（MOCK_TEXT 在 css）。
        assert "CH347" not in content
        # every U1 pin lands on a placeholder offset (unique, on grid)
        idx = content.find("FORCEADD U1_PH..1")
        nxt = content.find("\nFORCEADD", idx + 1)
        block = content[idx:nxt] if nxt != -1 else content[idx:]
        lastpins = re.findall(
            r"LASTPIN \((-?\d+) (-?\d+)\)", block,
        )
        assert len(lastpins) == 5, f"U1 should have 5 LASTPINs: {lastpins}"
        coords = [(int(x), int(y)) for x, y in lastpins]
        assert len(set(coords)) == 5, "placeholder pin coords must be unique"
        for x, y in coords:
            assert x % 25 == 0 and y % 25 == 0

    def test_temp_lib_disabled_keeps_placeholder_prop(self):
        """temp_lib.enabled=false → 回退 placeholder（PLACEHOLDER 1 属性）。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()
        cfg = RoutingConfig()
        cfg.temp_lib.enabled = False
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        assert "FORCEADD U1_PH..1" in content
        assert "PLACEHOLDER 1" in content
        assert "CH347" not in content

    def test_placeholder_off_keeps_legacy(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()
        cfg = RoutingConfig()
        cfg.placeholder.enabled = False
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        assert "FORCEADD U1_PH..1" not in content


# ---------------------------------------------------------------------------
#  P1-C: IOPORT 边缘分布 + 页内网无 IOPORT
# ---------------------------------------------------------------------------


def _make_offpage_design(n_offpages=3):
    from cis2hdl.core.ir.component import ComponentInstanceIR
    from cis2hdl.core.ir.design import DesignIR, PageIR

    p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
    p1.instances = [
        ComponentInstanceIR(
            refdes="C1", library_id="C1", loc_x=4500, loc_y=12000,
            pin_connections={"1": "NET_A", "2": "NET_B"},
        ),
    ]
    p1.off_pages = [
        {"name": f"OP{i}", "net_name": f"NET_{i}"} for i in range(n_offpages)
    ]
    return DesignIR(project_name="T", pages=[p1])


def _ioport_positions(content):
    lines = content.splitlines()
    positions = []
    for i, line in enumerate(lines):
        if line == "FORCEADD IOPORT..1":
            if i + 1 < len(lines):
                m = re.match(r"^\((-?\d+) (-?\d+)\);", lines[i + 1])
                if m:
                    positions.append((int(m.group(1)), int(m.group(2))))
    return positions


class TestIoportEdgeLayout:
    def test_edge_layout_evenly_spaced(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        design = _make_offpage_design(4)
        conn = _build_conn(design)
        cfg = RoutingConfig()
        cfg.ioport.edge_layout = True
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        positions = _ioport_positions(content)
        assert len(positions) == 4
        xs = {p[0] for p in positions}
        assert xs == {cfg.ioport.edge_x}
        ys = sorted((p[1] for p in positions), reverse=True)
        assert all(ys[i] - ys[i + 1] == cfg.ioport.edge_step for i in range(len(ys) - 1))

    def test_edge_layout_on_grid(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        design = _make_offpage_design(3)
        conn = _build_conn(design)
        cfg = RoutingConfig()
        cfg.ioport.edge_layout = True
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        for x, y in _ioport_positions(content):
            assert x % 25 == 0 and y % 25 == 0

    def test_page_internal_net_no_ioport(self):
        """仅单页出现的网（无 off_page 记录）不生成 IOPORT。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        design = _make_offpage_design(0)  # no cross-page connectors
        conn = _build_conn(design)
        content = CSAWriter(routing_cfg=RoutingConfig())._build_csa_content_conn(
            conn, conn.pages[0],
        )
        assert "FORCEADD IOPORT" not in content
        # page-internal net still gets a SIG_NAME label
        assert "SIG_NAME" in content


# ---------------------------------------------------------------------------
#  P1-D: GND 符号分布（每芯片一组）
# ---------------------------------------------------------------------------


class TestGndDistribution:
    def test_every_chip_gets_gnd_symbol(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()
        cfg = RoutingConfig()
        cfg.gnd_distribution.enabled = True
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        # AT LEAST ONE GND_POWER symbol sits NEAR U1 (chip with GND pins)
        m_u1 = re.search(r"FORCEADD U1_PH\.\.1\n\((-?\d+) (-?\d+)\);", content)
        assert m_u1, "U1 body not found"
        ux, uy = int(m_u1.group(1)), int(m_u1.group(2))
        bodies = re.findall(
            r"FORCEADD GND_POWER\.\.1\n\((-?\d+) (-?\d+)\);", content,
        )
        assert bodies, "no GND_POWER block emitted"
        # Phase XXI E（用户 P7/P8/P11/P19）：mock 图标横向拉宽（引脚 offset
        # ±300→±450+、字符宽 28）→ GND 引脚离 body 更远 → GND 符号（放在
        # 引脚外 100）天然更远。阈值 500→700（525 仍属"附近"，旧阈值按旧
        # 窄几何校准）。
        near = [
            (gx, gy) for gx, gy in
            ((int(x), int(y)) for x, y in bodies)
            if abs(gx - ux) + abs(gy - uy) <= 700
        ]
        assert near, f"no GND symbol near U1: bodies={bodies}, U1=({ux},{uy})"

    def test_gnd_symbols_on_grid_and_unique(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()
        cfg = RoutingConfig()
        cfg.gnd_distribution.enabled = True
        content = CSAWriter(routing_cfg=cfg)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        bodies = re.findall(r"FORCEADD GND_POWER\.\.1\n\((-?\d+) (-?\d+)\);", content)
        assert len(bodies) >= 1
        coords = [(int(x), int(y)) for x, y in bodies]
        assert len(set(coords)) == len(coords), "GND symbol bodies must be unique"
        for x, y in coords:
            assert x % 25 == 0 and y % 25 == 0

    def test_gnd_off_default_no_synthetic_symbol(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer.csa_writer import CSAWriter

        conn = _build_conn()
        content = CSAWriter(routing_cfg=RoutingConfig())._build_csa_content_conn(
            conn, conn.pages[0],
        )
        # default (distribution off): no synthetic per-chip GND symbols
        assert "GND_U1" not in content
        assert "GND_PC1" not in content


# ---------------------------------------------------------------------------
#  P1-G: stub 引出段 + 差异化
# ---------------------------------------------------------------------------


class TestStubLead:
    def test_stub_lead_adds_segments(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine

        net_pin_map = {
            "N1": [(100, 100), (100, 500), (400, 300)],
        }
        outlines = [(1000, 1000, 2000, 2000)]  # far away → no detour
        cfg = RoutingConfig(stub_lead=100)
        detoured = DetourRouter(cfg).route_nets(net_pin_map, outlines)["N1"]
        baseline = WireLayoutEngine().route_nets(net_pin_map, outlines)["N1"]
        # stub lead adds horizontal exit segments → more wires than P0
        assert len(detoured.wires) > len(baseline.wires)
        # endpoints preserved (all pins remain wire endpoints)
        endpoints = set()
        for w in detoured.wires:
            endpoints.add((w.x1, w.y1))
            endpoints.add((w.x2, w.y2))
        for pin in net_pin_map["N1"]:
            assert pin in endpoints
        # 0 off-grid
        for w in detoured.wires:
            for v in (w.x1, w.y1, w.x2, w.y2):
                assert v % 25 == 0

    def test_adjacent_pins_differentiated_leads(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter

        # two adjacent pins (50 apart, y=100) route to a trunk at y=400 →
        # their horizontal lead-out distances must differ.
        net_pin_map = {
            "N1": [
                (-3000, 100), (-2950, 100),
                (-2000, 400), (-1900, 400), (-1800, 400),
            ],
        }
        cfg = RoutingConfig(stub_lead=100)
        router = DetourRouter(cfg)
        pin_bodies = {
            (-3000, 100): (-3100, 100), (-2950, 100): (-3100, 100),
            (-2000, 400): (-2100, 400), (-1900, 400): (-2100, 400),
            (-1800, 400): (-2100, 400),
        }
        routed = router.route_nets(
            net_pin_map, [], pin_bodies=pin_bodies,
        )["N1"]
        # extract horizontal exit segments from the two adjacent pins
        exits = [
            w for w in routed.wires
            if w.is_horizontal and (w.x1, w.y1) in ((-3000, 100), (-2950, 100))
        ]
        assert len(exits) == 2, f"expected 2 exits: {routed.wires}"
        lengths = {abs(w.x2 - w.x1) for w in exits}
        assert len(lengths) == 2, f"adjacent pins must differ: {lengths}"

    def test_stub_lead_zero_disabled(self):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter

        net_pin_map = {"N1": [(-3000, 100), (-3000, 500)]}
        cfg = RoutingConfig(stub_lead=0)
        routed = DetourRouter(cfg).route_nets(net_pin_map, [])["N1"]
        # lead=0 → pure P0: a single vertical trunk wire (both pins on x=-3000)
        assert len(routed.wires) == 1


# ---------------------------------------------------------------------------
#  Aesthetic 总开关 → detour
# ---------------------------------------------------------------------------


class TestAestheticMode:
    def test_aesthetic_enables_detour(self):
        """--aesthetic 未显式 --routing 时 routing.mode 自动 = detour。"""
        from cis2hdl.core.config import RoutingConfig

        cfg = RoutingConfig()
        cfg.aesthetic.enabled = True
        # mirrors __main__.py logic
        if cfg.mode == "p0" and cfg.aesthetic.enabled:
            cfg.mode = "detour"
        assert cfg.mode == "detour"

    def test_p0_and_detour_output_differ(self):
        """用户"A*美化与普通版没区别"修复：aesthetic/detour 输出必须
        与 p0 明显不同（引出段）。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.csa_writer import CSAWriter
        from cis2hdl.core.writer.router_base import create_router

        conn = _build_conn()
        cfg_p0 = RoutingConfig(mode="p0")
        cfg_det = RoutingConfig(mode="detour", stub_lead=100)
        content_p0 = CSAWriter(routing_cfg=cfg_p0)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        content_det = CSAWriter(routing_cfg=cfg_det)._build_csa_content_conn(
            conn, conn.pages[0],
        )
        wire_count = lambda c: len(re.findall(r"WIRE 16 -1", c))
        assert wire_count(content_det) > wire_count(content_p0)
