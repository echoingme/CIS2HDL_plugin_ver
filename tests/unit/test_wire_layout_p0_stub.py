"""Phase XXII T01 — p0 模式三段式 stub（D1 能力下沉）。

Covers:
  * p0（带 cfg）三段式 stub：段数 ≤ 3、端点 = 引脚坐标
  * self-overlap 0（无"原地掉头"线头）
  * WIRE 全 25 网格（off-grid 0）
  * 无 cfg 时保持旧直 stub（零回归）
  * Phase XXII QA 修复：条件三段式 —— 仅受阻 stub 走引出段（WIRE 收敛）
"""

from __future__ import annotations


class TestP0ThreeStageStub:
    """p0（WireLayoutEngine）带 RoutingConfig → 三段式 stub（D1）。"""

    #: 场景：3 引脚，trunk y=2000；body (-3100,700,-2900,1500) 挡住引脚
    #: (-3000,450) 的直 stub（E→trunk 穿体）→ 三段式折线成功。
    PINS = [(-3000, 450), (-6000, 4000), (-8000, 2000)]
    OUTLINES = [(-3100, 700, -2900, 1500)]

    @staticmethod
    def _router(three_stage: bool = True, stub_lead: int = 100):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer import wire_layout  # noqa: F401
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine

        cfg = RoutingConfig(
            stub_lead=stub_lead, three_stage_stub=three_stage,
            edge_clearance=100,
        )
        return WireLayoutEngine(cfg)

    def test_p0_cfg_stub_le_segments_and_endpoints(self):
        """p0 带 cfg：trunk 经 R-2 冲突计数避让后，受阻 stub 才引出。

        Phase XXIII R-2（Q1 授权更新）：trunk 从旧 y=2000（引脚 -3000,450
        的直 stub 穿 body [700,1500]）下移到 y=650（避让成功，stub 通畅）
        —— 通畅 stub 保持直连 1 段，端点 = 引脚坐标（坐标唯一原则）。
        """
        router = self._router(three_stage=True)
        routed = router.route_nets({"N1": self.PINS}, self.OUTLINES)["N1"]
        assert routed.wires, "expected routed wires"
        for w in routed.wires:
            assert (w.x1, w.y1) != (w.x2, w.y2), f"zero-length {w}"
        # trunk 已避让：y=650（outline [700,1500] 之下），无段穿体。
        trunk_ys = {w.y1 for w in routed.wires if w.is_horizontal}
        assert trunk_ys == {650}, f"trunk={trunk_ys}"
        # 端点 = 引脚坐标（坐标唯一原则）。
        endpoints = set()
        for w in routed.wires:
            endpoints.add((w.x1, w.y1))
            endpoints.add((w.x2, w.y2))
        for pin in self.PINS:
            assert pin in endpoints, f"pin {pin} endpoint lost"
        # 无段穿过 outline（R-2 避让成功）。
        for w in routed.wires:
            assert not (-3100 < w.x1 < -2900 and -3100 < w.x2 < -2900) or \
                not (700 < w.y1 < 1500 and 700 < w.y2 < 1500), \
                f"segment still crosses body: {w}"

    def test_p0_cfg_self_overlap_zero(self):
        """三段式无"原地掉头"线头：overlap_detector.self_intersections 空。"""
        from cis2hdl.core.writer.overlap_detector import self_intersections

        router = self._router(three_stage=True)
        routed = router.route_nets({"N1": self.PINS}, self.OUTLINES)["N1"]
        segs = [(w.x1, w.y1, w.x2, w.y2) for w in routed.wires]
        hits = self_intersections(segs)
        assert hits == [], f"self-overlap lineheads: {hits}"

    def test_p0_cfg_off_grid_zero(self):
        """WIRE 端点全 25 网格（off-grid 0）。"""
        router = self._router(three_stage=True)
        routed = router.route_nets({"N1": self.PINS}, self.OUTLINES)["N1"]
        for w in routed.wires:
            for v in (w.x1, w.y1, w.x2, w.y2):
                assert v % 25 == 0, f"off-grid coord {v}"

    def test_p0_no_cfg_straight_stub(self):
        """无 cfg 时保持直 stub 拓扑（Phase XXIII R-2 后 trunk 避让）。

        Phase XXIII R-2（Q1 授权更新）：trunk 从 y=2000 下移到 y=650 避让
        outline（引脚 -3000,450 直 stub 不再穿体）—— 3 条直 stub + 2 段
        trunk = 5 段（引脚 -8000 原在旧 trunk 上，现需 stub）。端点全保。
        """
        from cis2hdl.core.writer import wire_layout  # noqa: F401
        from cis2hdl.core.writer.wire_layout import WireLayoutEngine

        router = WireLayoutEngine()
        routed = router.route_nets({"N1": self.PINS}, self.OUTLINES)["N1"]
        assert len(routed.wires) == 5
        endpoints = set()
        for w in routed.wires:
            endpoints.add((w.x1, w.y1))
            endpoints.add((w.x2, w.y2))
        for pin in self.PINS:
            assert pin in endpoints
        # R-2：trunk 避让后无段穿 outline（旧 4 段时 stub 穿体）。
        for w in routed.wires:
            assert not (-3100 < w.x1 < -2900 and -3100 < w.x2 < -2900) or \
                not (700 < w.y1 < 1500 and 700 < w.y2 < 1500), \
                f"segment still crosses body: {w}"

    def test_p0_cfg_disabled_escape_hatch(self):
        """逃生舱：three_stage_stub=false → 直 stub（trunk 仍避让）。"""
        router = self._router(three_stage=False)
        routed = router.route_nets({"N1": self.PINS}, self.OUTLINES)["N1"]
        assert len(routed.wires) == 5  # 3 直 stub + 2 trunk（R-2 避让）
        for w in routed.wires:
            assert not (-3100 < w.x1 < -2900 and -3100 < w.x2 < -2900) or \
                not (700 < w.y1 < 1500 and 700 < w.y2 < 1500), \
                f"segment still crosses body: {w}"

    def test_clear_stub_stays_plain(self):
        """Phase XXII QA 修复（Issue 1）：通畅 stub 保持直连（不引出）。

        无 outline 时全部 stub 为 1 段直连 —— WIRE 段数不因三段式过度增长。
        """
        router = self._router(three_stage=True)
        # 无 outline：全部 stub 通畅 → 直连（4 段 = 旧直 stub 同量级）。
        routed = router.route_nets({"N1": self.PINS}, [])["N1"]
        assert len(routed.wires) == 4, (
            f"clear stubs must stay plain, got {len(routed.wires)}"
        )
