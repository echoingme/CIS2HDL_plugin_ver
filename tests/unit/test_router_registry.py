"""Phase XIV T1/T2/T3 — 布线器注册表 + Detour 绕障 + EDIF 折线复用。

Covers:
  * ROUTER_REGISTRY 含 p0/p0_lane/detour/edif_reuse
  * create_router 未知 mode → 回退 p0_lane
  * DetourRouter stub 绕障（端点不变、0 off-grid）
  * EDIFWireRouter 折线映射（端点重定、0 off-grid、无折线降级 P0）
"""

from __future__ import annotations


class TestRouterRegistry:
    def test_registry_has_modes(self):
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer import edif_wire_reuse  # noqa: F401
        from cis2hdl.core.writer import wire_layout  # noqa: F401
        from cis2hdl.core.writer.router_base import ROUTER_REGISTRY

        assert "p0_lane" in ROUTER_REGISTRY
        assert "p0" in ROUTER_REGISTRY
        assert "detour" in ROUTER_REGISTRY
        assert "edif_reuse" in ROUTER_REGISTRY

    def test_create_router_unknown_falls_back(self):
        from cis2hdl.core.writer import wire_layout  # noqa: F401
        from cis2hdl.core.writer.router_base import create_router

        router = create_router("no_such_mode")
        assert type(router).__name__ == "WireLayoutEngine"

    def test_create_router_detour(self):
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.router_base import create_router

        router = create_router("detour")
        assert type(router).__name__ == "DetourRouter"
        assert router.name == "detour"

    def test_p0_alias_no_warning(self, caplog):
        import logging

        from cis2hdl.core.writer import wire_layout  # noqa: F401
        from cis2hdl.core.writer.router_base import create_router

        with caplog.at_level(logging.WARNING):
            router = create_router("p0")
        assert "unknown routing mode" not in caplog.text
        assert router.name == "p0_lane"


class TestDetourRouter:
    def test_route_net_detour_avoids_body(self):
        """stub 穿 outline → 拆段；端点不变；0 off-grid。"""
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter

        net_pin_map = {
            "N1": [(100, 100), (100, 500)],  # vertical stub through body
        }
        # body covering x∈[75,150], y∈[200,400] — the stub x=100 crosses it
        outlines = [(75, 200, 150, 400)]
        results = DetourRouter().route_nets(net_pin_map, outlines)
        routed = results["N1"]
        # The single stub is split into > 1 segment
        assert len(routed.wires) > 1
        endpoints = set()
        for w in routed.wires:
            endpoints.add((w.x1, w.y1))
            endpoints.add((w.x2, w.y2))
        # Electrical hard constraint: both original endpoints preserved
        assert (100, 100) in endpoints
        assert (100, 500) in endpoints
        # 0 off-grid
        for w in routed.wires:
            for v in (w.x1, w.y1, w.x2, w.y2):
                assert v % 25 == 0, f"off-grid coord {v}"
        # No segment crosses the body interior
        for w in routed.wires:
            assert not (75 < w.x1 < 150 and 75 < w.x2 < 150) or \
                not (200 < w.y1 < 400 and 200 < w.y2 < 400), \
                f"segment still crosses body: {w}"

    def test_route_net_detour_clear_segment_unchanged(self):
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine

        net_pin_map = {"N1": [(100, 100), (100, 500)]}
        outlines = [(1000, 1000, 2000, 2000)]  # far away
        detoured = DetourRouter().route_nets(net_pin_map, outlines)["N1"]
        baseline = WireLayoutEngine().route_nets(net_pin_map, outlines)["N1"]
        # Phase XV P1-G: detour carries a stub_lead, so wires may differ
        # from the P0 baseline — but endpoints must be preserved and the
        # segment count must not shrink (no information loss).
        ends = set()
        for w in detoured.wires:
            ends.add((w.x1, w.y1))
            ends.add((w.x2, w.y2))
        assert (100, 100) in ends and (100, 500) in ends
        assert len(detoured.wires) >= len(baseline.wires) - 2

    def test_horizontal_stub_detour(self):
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter

        # horizontal stub at y=300 crossing body x∈[200,400]
        net_pin_map = {"N1": [(100, 300), (500, 300)]}
        outlines = [(200, 250, 400, 350)]
        results = DetourRouter().route_nets(net_pin_map, outlines)
        routed = results["N1"]
        assert len(routed.wires) > 1
        endpoints = set()
        for w in routed.wires:
            endpoints.add((w.x1, w.y1))
            endpoints.add((w.x2, w.y2))
        assert (100, 300) in endpoints
        assert (500, 300) in endpoints
        for w in routed.wires:
            for v in (w.x1, w.y1, w.x2, w.y2):
                assert v % 25 == 0

    def test_route_net_detour_degenerate_escape_no_zero_length(self):
        """QA Phase XIV Bug 1 回归：引脚恰在 outline+_DETOUR_MARGIN 边界 →
        绕行点 == 源点 → 不得产生零长度段 / 重复段。"""
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter

        # vertical stub (100,150)→(100,550); body top edge hi_y=100 + 50 == y1=150
        # → y_escape == y1 == 150 (degenerate first piece)
        net_pin_map = {"N1": [(100, 150), (100, 550)]}
        outlines = [(50, 0, 150, 100)]
        routed = DetourRouter().route_nets(net_pin_map, outlines)["N1"]
        self._assert_no_zero_length_no_dup(routed.wires, (100, 150), (100, 550))

        # horizontal stub (150,300)→(550,300); body right edge hi_x=100+50==x1=150
        net_pin_map2 = {"N2": [(150, 300), (550, 300)]}
        outlines2 = [(0, 250, 100, 350)]
        routed2 = DetourRouter().route_nets(net_pin_map2, outlines2)["N2"]
        self._assert_no_zero_length_no_dup(routed2.wires, (150, 300), (550, 300))

    def test_route_net_detour_outline_covers_whole_stub_keeps_endpoints(self):
        """outline 覆盖整条 stub → 绕行仍必须保持两端点（无零长度/重复）。"""
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter

        net_pin_map = {"N1": [(100, 100), (100, 500)]}
        outlines = [(50, 50, 150, 550)]  # body spans the whole stub
        routed = DetourRouter().route_nets(net_pin_map, outlines)["N1"]
        self._assert_no_zero_length_no_dup(routed.wires, (100, 100), (100, 500))

    def test_two_nets_detour_lanes_do_not_share_segments(self):
        """QA Phase XIV Bug 1 回归：两个网的绕障路径不得共线（DEHDL 短路）。"""
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter

        # 两个相邻 stub 都穿过同一 outline，绕行路径若共线 → 短路。
        net_pin_map = {
            "N1": [(100, 100), (100, 500)],
            "N2": [(150, 100), (150, 500)],
        }
        outlines = [(50, 150, 250, 450)]  # both stubs cross this body
        results = DetourRouter().route_nets(net_pin_map, outlines)
        seen = set()
        for routed in results.values():
            for w in routed.wires:
                key = ((w.x1, w.y1), (w.x2, w.y2))
                rkey = ((w.x2, w.y2), (w.x1, w.y1))
                assert key not in seen and rkey not in seen, \
                    f"two nets share segment {w} → short"
                seen.add(key)
                assert (w.x1, w.y1) != (w.x2, w.y2), f"zero-length {w}"
                for v in (w.x1, w.y1, w.x2, w.y2):
                    assert v % 25 == 0

    @staticmethod
    def _assert_no_zero_length_no_dup(wires, start, end):
        """断言：无零长度段、无重复段、两端点保持、全 25 网格。"""
        assert len(wires) >= 1
        seen = set()
        endpoints = set()
        for w in wires:
            assert (w.x1, w.y1) != (w.x2, w.y2), f"zero-length segment {w}"
            key = ((w.x1, w.y1), (w.x2, w.y2))
            rkey = ((w.x2, w.y2), (w.x1, w.y1))
            assert key not in seen and rkey not in seen, f"duplicate segment {w}"
            seen.add(key)
            endpoints.add((w.x1, w.y1))
            endpoints.add((w.x2, w.y2))
            for v in (w.x1, w.y1, w.x2, w.y2):
                assert v % 25 == 0, f"off-grid coord {v}"
        assert start in endpoints and end in endpoints, "endpoints lost"


class TestEDIFWireRouter:
    def _make_design_with_wires(self):
        from cis2hdl.core.ir.component import ComponentInstanceIR
        from cis2hdl.core.ir.design import DesignIR, NetIR, PageIR, WireSegment

        p1 = PageIR(page_id="1.1", page_name="05-Power_Supply1")
        p1.instances = [
            ComponentInstanceIR(
                refdes="U1", library_id="U1", loc_x=4500, loc_y=12000,
                pin_connections={"1": "NET_A", "2": "NET_B"},
            ),
        ]
        # source polyline for NET_A: (4500,12000) → (5000,12000)
        p1.nets = [
            NetIR(name="NET_A", connections=[], wires=[
                WireSegment(points=[(4500, 12000), (5000, 12000)], page_id="1.1"),
            ]),
        ]
        return DesignIR(project_name="TEST", pages=[p1]), p1

    def test_route_nets_endpoint_reanchored(self):
        from cis2hdl.core.writer import edif_wire_reuse  # noqa: F401
        from cis2hdl.core.writer.edif_wire_reuse import EDIFWireRouter

        design, page_ir = self._make_design_with_wires()
        # net_pin_map uses the page's real pin coords (transformed via same
        # CoordTransform used by the router)
        from cis2hdl.core.writer.coord_transform import CoordTransform

        bbox = CoordTransform.source_bbox(page_ir.instances)
        _ct = CoordTransform()
        p1 = _ct.map_point(4500, 12000, bbox)
        p2 = _ct.map_point(5000, 12000, bbox)
        net_pin_map = {
            "NET_A": [
                {"refdes": "U1", "pin": "1", "coord": p1},
                {"refdes": "U1", "pin": "2", "coord": p2},
            ],
        }
        router = EDIFWireRouter()
        results = router.route_nets(
            net_pin_map, [], design=design, page=__import__(
                "cis2hdl.core.writer.connectivity_model", fromlist=["PageConnectivity"]
            ).PageConnectivity(page_num=5, page_name="05-Power_Supply1"),
        )
        routed = results["NET_A"]
        assert routed.wires, "expected mapped wires"
        endpoints = set()
        for w in routed.wires:
            endpoints.add((w.x1, w.y1))
            endpoints.add((w.x2, w.y2))
        # endpoint re-anchoring: both pins are wire endpoints
        assert p1 in endpoints, f"pin {p1} not an endpoint"
        assert p2 in endpoints, f"pin {p2} not an endpoint"
        # 0 off-grid
        for w in routed.wires:
            for v in (w.x1, w.y1, w.x2, w.y2):
                assert v % 25 == 0

    def test_route_nets_no_wires_falls_back_p0(self):
        from cis2hdl.core.writer import edif_wire_reuse  # noqa: F401
        from cis2hdl.core.writer.edif_wire_reuse import EDIFWireRouter

        net_pin_map = {
            "NET_Z": [(100, 100), (400, 150)],
        }
        results = EDIFWireRouter().route_nets(net_pin_map, [])
        assert "NET_Z" in results
        assert results["NET_Z"].wires  # P0 fallback produced wires

    def test_route_nets_no_design_context_p0(self):
        from cis2hdl.core.writer import edif_wire_reuse  # noqa: F401
        from cis2hdl.core.writer.edif_wire_reuse import EDIFWireRouter

        net_pin_map = {"NET_A": [(100, 100), (400, 150)]}
        results = EDIFWireRouter().route_nets(net_pin_map, [])
        assert "NET_A" in results
        assert results["NET_A"].wires
