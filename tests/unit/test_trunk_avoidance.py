"""Phase XXIII R-2 — trunk 避让增强（_avoid_outlines / trunk_blocked 标记）。

Covers:
  * `_avoid_outlines`：单 outline 推离、多 outline 双向最小冲突、
    无解回退（穿透最少并返回）
  * `route_nets`：trunk 无解回退直穿时标记 ``_trunk_blocked_nets``
    （report reason=trunk_blocked）
  * WIRE 段数不增（trunk 坐标变化不产生新段）
"""

from __future__ import annotations

from cis2hdl.core.writer.wire_layout import WireLayoutEngine


class TestAvoidOutlines:
    def test_single_outline_pushed(self):
        """单 outline 覆盖中位 → 推离到不穿 outline 的坐标。"""
        result = WireLayoutEngine._avoid_outlines(
            100, [(50, 90, 150, 120)], vertical=True,
        )
        assert not (90 < result < 120), result
        assert result % 25 == 0

    def test_multi_outline_chain_all_clear(self):
        """多个堆叠 outline → 结果与任何 outline 内部都不重叠（严格区间）。"""
        outlines = [
            (50, 90, 150, 120),
            (50, 120, 150, 150),
            (50, 150, 150, 180),
        ]
        result = WireLayoutEngine._avoid_outlines(100, outlines, vertical=True)
        for (ox0, oy0, ox1, oy1) in outlines:
            assert not (min(oy0, oy1) < result < max(oy0, oy1)), result

    def test_span_aware_no_push_for_far_outline(self):
        """span 感知：trunk span 与 outline x 不重叠 → 不推离（R-2 核心修复）。

        旧实现只查 y 区间 → 把 trunk 推离 x 方向根本不经过的远端 outline
        （密集页推太远 → 车道被占 → 回退直穿）。span 提供时按真穿体判定。
        """
        # trunk 固定 y=5000、span x∈[100,500]；outline 在 x∈[5000,6000]。
        result = WireLayoutEngine._avoid_outlines(
            5000, [(5000, 4900, 6000, 5100)], vertical=True, span=(100, 500),
        )
        assert result == 5000, f"不应推离远端 outline: {result}"

    def test_span_aware_push_when_overlap(self):
        """span 感知：span 与 outline x 重叠且 y 含 trunk → 推离。"""
        result = WireLayoutEngine._avoid_outlines(
            5000, [(4800, 4900, 5200, 5100)], vertical=True, span=(100, 5000),
        )
        assert not (4900 < result < 5100), result

    def test_push_above_deterministic(self):
        """trunk 落 outline 内 → 单向 +50 推离（最大扩展，确定性方向）。"""
        result = WireLayoutEngine._avoid_outlines(
            100, [(0, 80, 200, 5000)], vertical=True,
        )
        assert result == 5050, result

    def test_span_aware_push_through_overlapping_stack(self):
        """span 重叠的堆叠 outline → 推离到最后一个 outline 之上。"""
        outlines = [(0, 80, 200, 120), (0, 120, 200, 160)]  # 覆盖 [80,160]
        result = WireLayoutEngine._avoid_outlines(100, outlines, vertical=True)
        # 100 在 [80,120] → 推至 170 → snap 175（已在 [120,160] 之上）。
        assert result == 175, result
        assert not (80 < result < 160), result

    def test_push_past_all_outlines_when_span_overlaps(self):
        """span 与每个 outline 都重叠 → 推过全部（结果不与任何重叠）。"""
        outlines = [(0, -700, 200, 800), (0, 800, 200, 1500)]
        result = WireLayoutEngine._avoid_outlines(100, outlines, vertical=True)
        assert result == 1500 + 50, result
        for (ox0, oy0, ox1, oy1) in outlines:
            assert not (min(oy0, oy1) < result < max(oy0, oy1)), result

    def test_vertical_trunk(self):
        """垂直 trunk（x 固定）同样双向避让。"""
        result = WireLayoutEngine._avoid_outlines(
            -3000, [(-3050, 0, -2950, 5000)], vertical=False,
        )
        assert not (-3050 < result < -2950), result


class TestTrunkBlockedMarking:
    def _router(self):
        from cis2hdl.core.writer import wire_layout  # noqa: F401
        return WireLayoutEngine()

    def test_route_nets_marks_trunk_blocked_no_escape(self):
        """trunk 中位被覆盖全页（含页界外）的 outline 挡住 → 标记。"""
        router = self._router()
        # 覆盖 y∈[-100,8375]（页内 y∈[0,8275] 全部被严格包含）→ 无页内
        # 空隙可避让 → _find_lane 回退中位直穿 → 标记 trunk_blocked。
        outlines = [(50, -100, 550, 8375)]
        results = router.route_nets(
            {"N1": [(100, 100), (300, 105), (500, 110)]}, outlines,
        )
        assert "N1" in results
        assert "N1" in router._trunk_blocked_nets, (
            f"trunk 无解回退应标记: {router._trunk_blocked_nets}"
        )
        trunk, vertical = router._trunk_line["N1"]
        assert vertical is True  # 水平 trunk（y 固定）
        # 标记的 trunk 确实穿 outline。
        assert WireLayoutEngine._trunk_crosses_outlines(
            trunk, 100, 500, outlines, vertical=True,
        )

    def test_route_nets_not_marked_when_clear(self):
        """trunk 完全避让 → 不标记 trunk_blocked。"""
        router = self._router()
        outlines = [(80, 200, 200, 400)]  # 远离 trunk y=105
        results = router.route_nets(
            {"N1": [(100, 100), (300, 105), (500, 110)]}, outlines,
        )
        assert "N1" in results
        assert "N1" not in router._trunk_blocked_nets

    def test_avoidable_crossing_cleared(self):
        """可避让穿体（outline 有两侧空隙）→ trunk 被推离且不标记。"""
        router = self._router()
        # 单 outline 覆盖中位 y=105（[90,120]），两侧有空隙 → 推离。
        outlines = [(80, 90, 520, 120)]
        results = router.route_nets(
            {"N1": [(100, 100), (300, 105), (500, 110)]}, outlines,
        )
        trunk_ys = {w.y1 for w in results["N1"].wires if w.is_horizontal}
        assert trunk_ys, "缺 trunk"
        for ty in trunk_ys:
            assert not (90 < ty < 120), f"trunk y={ty} 仍穿体"
        assert "N1" not in router._trunk_blocked_nets

    def test_wire_count_not_increased(self):
        """trunk 避让不增加 WIRE 段数（坐标变化不产生新段）。

        引脚 y=200/215/230（中位 225 无一引脚落 trunk）：无 outline 与
        有 outline（trunk 推离到 275）都是 3 stub + 2 trunk 段 = 5 段。
        """
        router = self._router()
        pins = [(100, 200), (300, 215), (500, 230)]
        outlines = [(80, 200, 520, 240)]
        base = WireLayoutEngine().route_nets({"N1": pins}, [])["N1"]
        routed = router.route_nets({"N1": pins}, outlines)["N1"]
        assert len(routed.wires) == len(base.wires) == 5, (
            f"WIRE 段数不增：{len(base.wires)} → {len(routed.wires)}"
        )
        # trunk 确实被推离 outline（y ∈ (200,240) 之外，严格区间）。
        trunk_ys = {w.y1 for w in routed.wires if w.is_horizontal}
        for ty in trunk_ys:
            assert not (200 < ty < 240), f"trunk y={ty} 仍穿体"
