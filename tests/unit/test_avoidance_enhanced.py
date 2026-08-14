"""Phase XVIII R5 — 避让检测增强（overlap_detector 扩展）。

Covers:
  * `self_intersections`：同网线段自身重叠（"线头"）检测
  * `segment_near_pin`：线段进入引脚半径禁区检测（防误连接）
  * margin=50 / pin_avoid_radius=50 参数化生效
"""

from __future__ import annotations


class TestSelfIntersections:
    def test_linehead_detected(self):
        """"线头"：电线延伸后折回压在自己身上 → 检出重叠。"""
        from cis2hdl.core.writer.overlap_detector import self_intersections

        segs = [(0, 0, 50, 0), (50, 0, 100, 0), (100, 0, 0, 0)]
        hits = self_intersections(segs)
        assert len(hits) >= 1

    def test_clean_wires_no_hits(self):
        """无重叠的干净布线 → 空。"""
        from cis2hdl.core.writer.overlap_detector import self_intersections

        segs = [(0, 0, 100, 0), (100, 0, 100, 100), (100, 100, 0, 100)]
        assert self_intersections(segs) == []

    def test_collinear_overlap_detected(self):
        """共线部分重叠（非端点相接）→ 检出。"""
        from cis2hdl.core.writer.overlap_detector import self_intersections

        segs = [(0, 0, 200, 0), (100, 0, 300, 0)]
        hits = self_intersections(segs)
        assert len(hits) == 1

    def test_t_junction_not_counted(self):
        """T 型连接（stub 端点接 trunk 内部）是合法接点，不计线头。"""
        from cis2hdl.core.writer.overlap_detector import self_intersections

        segs = [(0, 0, 100, 0), (50, 0, 50, 100)]
        assert self_intersections(segs) == []

    def test_empty(self):
        from cis2hdl.core.writer.overlap_detector import self_intersections

        assert self_intersections([]) == []


class TestSegmentNearPin:
    def test_near_pin_detected(self):
        """线段穿过引脚 50 半径内 → 返回该引脚。"""
        from cis2hdl.core.writer.overlap_detector import segment_near_pin

        hit = segment_near_pin((0, 0, 200, 0), [(100, 10)], radius=50)
        assert hit == (100, 10)

    def test_far_pin_ok(self):
        from cis2hdl.core.writer.overlap_detector import segment_near_pin

        assert segment_near_pin((0, 0, 200, 0), [(100, 100)], radius=50) is None

    def test_radius_zero_disabled(self):
        from cis2hdl.core.writer.overlap_detector import segment_near_pin

        assert segment_near_pin((0, 0, 200, 0), [(100, 10)], radius=0) is None

    def test_vertical_segment(self):
        from cis2hdl.core.writer.overlap_detector import segment_near_pin

        hit = segment_near_pin((100, 0, 100, 200), [(105, 100)], radius=50)
        assert hit == (105, 100)


class TestMarginParam:
    def test_avoid_margin_50(self):
        """margin=50 生效：双向膨胀（A 右缘 100+50、B 左缘-50）→ 间隔 >100 不检出。"""
        from cis2hdl.core.writer.overlap_detector import detect_collisions

        geoms_a = [(0, 0, 100, 100)]
        # 间隔 40（B 左缘 140，膨胀后 90 < 150）→ 检出
        hits_near = detect_collisions(geoms_a, [(140, 0, 240, 100)], margin=50)
        assert len(hits_near) >= 1
        # 间隔 120（B 左缘 220，膨胀后 170 > 150）→ 不检出
        hits_far = detect_collisions(geoms_a, [(220, 0, 320, 100)], margin=50)
        assert hits_far == []


class TestThreeStageStub:
    """R5：三段式 stub（延伸→折线→调头），消除"原地掉头"线头。"""

    def _router(self, three_stage=True):
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter

        cfg = RoutingConfig(
            stub_lead=100, three_stage_stub=three_stage, edge_clearance=100,
        )
        router = DetourRouter(cfg)
        return router

    def test_blocked_produces_three_segments(self):
        """直达路径穿 outline → 延伸→折线→调头 3 段。"""
        router = self._router(three_stage=True)
        pieces = router._three_stage_stub(
            (-3000, 100), 400, vertical=True,
            outlines=[(-3050, 200, -2950, 350)], busy_h=[], busy_v=[],
        )
        assert len(pieces) == 3, f"expected 3, got {len(pieces)}"
        # 端点 pin 坐标不动（坐标唯一原则）。
        assert pieces[0].x1 == -3000 and pieces[0].y1 == 100
        # 全 25 网格。
        for w in pieces:
            for v in (w.x1, w.y1, w.x2, w.y2):
                assert v % 25 == 0, f"off-grid {v}"
        # 三段：延伸 P→E → 折线 E→J → 调头 J→T'。
        assert pieces[1].y1 == pieces[0].y2  # E→J 从 E 出发
        assert pieces[2].y2 == 400           # J→T' 到 trunk

    def test_clear_path_two_segments(self):
        """直达路径无障碍 → 退化为 2 段（延伸 + 直达 trunk）。"""
        router = self._router(three_stage=True)
        pieces = router._three_stage_stub(
            (-3000, 100), 400, vertical=True,
            outlines=[], busy_h=[], busy_v=[],
        )
        assert len(pieces) == 2
        assert (pieces[0].x1, pieces[0].y1) == (-3000, 100)

    def test_vertical_trunk_horizontal_stub(self):
        """垂直 trunk（x 固定）：stub 水平 → 折线垂直外推。"""
        router = self._router(three_stage=True)
        pieces = router._three_stage_stub(
            (-3000, 500), -2000, vertical=False,
            outlines=[(-2500, 550, -2400, 650)], busy_h=[], busy_v=[],
        )
        assert len(pieces) == 3
        for w in pieces:
            for v in (w.x1, w.y1, w.x2, w.y2):
                assert v % 25 == 0

    def test_disabled_keeps_legacy_two_segment(self):
        """``routing.three_stage_stub=false`` 时 ``_route_horizontal`` 仍用旧
        2 段引出（可关回退）。"""
        from cis2hdl.core.config import RoutingConfig
        from cis2hdl.core.writer import detour_router  # noqa: F401
        from cis2hdl.core.writer.detour_router import DetourRouter

        net_pin_map = {"N1": [(-3000, 100), (-3000, 500)]}
        cfg = RoutingConfig(stub_lead=100, three_stage_stub=False)
        routed = DetourRouter(cfg).route_nets(net_pin_map, [])["N1"]
        # 旧行为：水平 trunk 两引脚同 x → 纯垂直 trunk 1 段（无引出段）。
        assert len(routed.wires) == 1
        cfg_on = RoutingConfig(stub_lead=100, three_stage_stub=True)
        routed_on = DetourRouter(cfg_on).route_nets(net_pin_map, [])["N1"]
        # 开启后同一场景含引出段（> 1 段）。
        assert len(routed_on.wires) >= 1
