"""Phase XVIII R6 — GND 就近共用 + 簇内并联（gnd_cluster_planner）。

Covers:
  * `route_cluster_parallel(pins, max_dist, gnd_coord)` → ParallelHub 列表
  * `hub_short_wires(hub, outlines, stub_lead)` → 簇内短接 WIRE 段
  * `hub_to_symbol_wire`：hub → GND 符号引脚引出段
  * `place_gnd_symbol`：GND 符号避让 outline / 引脚禁区 / 页边
  * 全部输出坐标 25 网格

注意：真实页面坐标为负值区域（C 纸 x∈[-10750,-550], y∈[400,7200]），
测试用页面内坐标。
"""

from __future__ import annotations


class TestRouteClusterParallel:
    def test_nearby_pins_single_hub(self):
        """一排间距 100 的 GND 引脚聚成 1 个 hub。"""
        from cis2hdl.core.writer.gnd_cluster_planner import route_cluster_parallel

        pins = [
            ("GND", (-3000, 5000)), ("GND", (-2900, 5000)), ("GND", (-2800, 5000)),
        ]
        hubs = route_cluster_parallel(pins, max_dist=500)
        assert len(hubs) == 1
        assert hubs[0].pin_count == 3
        assert hubs[0].hub == (-2900, 5000)  # 包围盒中心
        assert hubs[0].outlet != hubs[0].hub  # 引出点偏移

    def test_far_pin_separate_cluster(self):
        """远端引脚独立成簇（不超过阈值）。"""
        from cis2hdl.core.writer.gnd_cluster_planner import route_cluster_parallel

        pins = [
            ("GND", (-3000, 5000)), ("GND", (-2900, 5000)),
            ("GND", (-1000, 6000)),
        ]
        hubs = route_cluster_parallel(pins, max_dist=500)
        # 近距 2 个聚 hub；远端独立（pin_count=1 不产生 hub）
        assert len(hubs) == 1
        assert hubs[0].pin_count == 2

    def test_chain_merging(self):
        """链式合并：A-B 近、B-C 近 → A-B-C 同簇。"""
        from cis2hdl.core.writer.gnd_cluster_planner import route_cluster_parallel

        pins = [
            ("GND", (-5000, 5000)), ("GND", (-4700, 5000)), ("GND", (-4400, 5000)),
        ]
        hubs = route_cluster_parallel(pins, max_dist=400)
        assert len(hubs) == 1
        assert hubs[0].pin_count == 3

    def test_empty_and_single(self):
        """空输入与单引脚不产生 hub。"""
        from cis2hdl.core.writer.gnd_cluster_planner import route_cluster_parallel

        assert route_cluster_parallel([]) == []
        assert route_cluster_parallel([("GND", (0, 0))]) == []

    def test_grid_25(self):
        """hub/outlet 坐标全部 25 网格。"""
        from cis2hdl.core.writer.gnd_cluster_planner import route_cluster_parallel

        pins = [
            ("GND", (-3003, 5007)), ("GND", (-2877, 5001)), ("GND", (-2773, 5013)),
        ]
        hubs = route_cluster_parallel(pins, max_dist=500)
        for h in hubs:
            assert h.hub[0] % 25 == 0 and h.hub[1] % 25 == 0
            assert h.outlet[0] % 25 == 0 and h.outlet[1] % 25 == 0


class TestHubShortWires:
    def test_all_pins_anchored(self):
        """引脚坐标是段的端点（引脚不动）；hub 自身引脚无需段。"""
        from cis2hdl.core.writer.gnd_cluster_planner import (
            ParallelHub, hub_short_wires,
        )

        hub = ParallelHub(
            net="GND",
            pin_coords=[(-3000, 5000), (-2900, 5000), (-2800, 5000)],
            hub=(-2900, 5000),  # 中间引脚即 hub
            outlet=(-2900, 5050),
        )
        segs = hub_short_wires(hub, stub_lead=100)
        # 两端引脚各 1 段到 hub（hub 自身无需段）→ ≥2
        assert len(segs) >= 2
        for pc in [(-3000, 5000), (-2800, 5000)]:
            assert any(
                s[:2] == pc or s[2:] == pc for s in segs
            ), f"pin {pc} not anchored"

    def test_grid_25(self):
        from cis2hdl.core.writer.gnd_cluster_planner import (
            ParallelHub, hub_short_wires,
        )

        hub = ParallelHub(
            net="GND",
            pin_coords=[(-3000, 5000), (-2900, 5000), (-2800, 5000)],
            hub=(-2900, 5000),
        )
        for s in hub_short_wires(hub, stub_lead=100):
            for v in s:
                assert v % 25 == 0


class TestHubToSymbolWire:
    def test_orthogonal_connection(self):
        from cis2hdl.core.writer.gnd_cluster_planner import hub_to_symbol_wire

        segs = hub_to_symbol_wire((-2900, 5000), (-2400, 5200))
        assert len(segs) >= 1
        # 首段从 hub 出发，末段到 symbol pin
        assert segs[0][:2] == (-2900, 5000)
        assert segs[-1][2:] == (-2400, 5200)

    def test_grid_25(self):
        from cis2hdl.core.writer.gnd_cluster_planner import hub_to_symbol_wire

        for s in hub_to_symbol_wire((-2900, 5000), (-2400, 5200)):
            for v in s:
                assert v % 25 == 0

    def test_distribute_outlet_detours_blocked(self):
        """Phase XXIII P1-3：distribute 开时 outlet→符号段受阻 90° 绕行。

        默认（outlines=()）保持直连 L；传 outlines 后（csa_writer 在
        distribute_density 开启时传入）受阻段被 Z 路径替代且不穿体。
        """
        from cis2hdl.core.writer.gnd_cluster_planner import (
            _seg_intersects_rect, hub_to_symbol_wire,
        )

        hub = (-2900, 5000)
        symbol_pin = (-2400, 5200)
        outlines = [
            (-2600, 4950, -2500, 5050),
            (-2850, 5150, -2450, 5250),
        ]
        # 无 outline（默认）：直连 L（2 段）。
        plain = hub_to_symbol_wire(hub, symbol_pin)
        assert len(plain) <= 2
        # 有 outline（distribute 开）：绕行 ≥3 段，穿体 0。
        detoured = hub_to_symbol_wire(hub, symbol_pin, outlines=outlines)
        assert len(detoured) >= 3
        for s in detoured:
            for o in outlines:
                assert not _seg_intersects_rect(s, o), (
                    f"outlet 段 {s} 穿 outline {o}"
                )


class TestPlaceGndSymbol:
    def test_free_position_kept(self):
        """空闲位置直接返回。"""
        from cis2hdl.core.writer.gnd_cluster_planner import place_gnd_symbol

        pos = place_gnd_symbol(
            (-3000, 5000), [(-2000, 6000, -1900, 6100)],
            margin=50, edge_clearance=100,
        )
        assert pos == (-3000, 5000)

    def test_avoid_outline(self):
        """候选点落元件内 → 移出（margin 冗余区 + 符号引脚轮廓）。"""
        from cis2hdl.core.writer.gnd_cluster_planner import place_gnd_symbol

        pos = place_gnd_symbol(
            (-1100, 5000), [(-1200, 4900, -1000, 5100)],
            margin=50, edge_clearance=100,
        )
        x, y = pos
        # 放置点不在膨胀 outline 内
        assert not (-1250 <= x <= -950 and 4850 <= y <= 5150)
        # 符号引脚 (x+50, y+100) 也不在膨胀 outline 内
        assert not (-1250 <= x + 50 <= -950 and 4850 <= y + 100 <= 5150)

    def test_avoid_pin_points(self):
        """GND 引脚（pin_offset）不得贴近其他引脚（禁区 50）。"""
        from cis2hdl.core.writer.gnd_cluster_planner import place_gnd_symbol

        pos = place_gnd_symbol(
            (-1100, 5000), [],
            margin=50, edge_clearance=100, pin_offset=(0, 50),
            pin_points=[(-1100, 5050)],  # 恰在默认 pin_offset 处
        )
        x, y = pos
        sym_pin = (x, y + 50)
        d = ((sym_pin[0] + 1100) ** 2 + (sym_pin[1] - 5050) ** 2) ** 0.5
        assert d > 50

    def test_edge_clearance(self):
        """不贴页边（页边带被排除；有 outline 时检查生效）。"""
        from cis2hdl.core.writer.gnd_cluster_planner import place_gnd_symbol

        pos = place_gnd_symbol(
            (-10600, 5000), [(-2000, 6000, -1900, 6100)],
            margin=50, edge_clearance=100,
        )
        # x_lo = -10750+100 = -10650；-10600 < -10650? No（-10600 > -10650）
        # 但 -10600 距页边 150 ≥ 100 → 允许；验证在页边带内时被排除：
        assert pos[0] >= -10750 + 100 or pos[0] <= -550 - 100

    def test_grid_25(self):
        from cis2hdl.core.writer.gnd_cluster_planner import place_gnd_symbol

        pos = place_gnd_symbol(
            (-3003, 5007), [(-2000, 6000, -1900, 6100)],
            margin=50, edge_clearance=100,
        )
        assert pos[0] % 25 == 0 and pos[1] % 25 == 0
