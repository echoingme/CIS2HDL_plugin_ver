"""Phase XVII M2/M3 — 统一碰撞检测（overlap_detector）+ 腾挪器（overlap_resolver）。

Covers:
  * detect_collisions：rect-rect / point-rect / segment-rect / segment-segment
  * margin 膨胀与最小分离向量
  * OverlapResolver：只推可动件、芯片本体不动、多轮迭代
"""

from __future__ import annotations


class TestDetectCollisions:
    def test_rect_rect(self):
        from cis2hdl.core.writer.overlap_detector import detect_collisions

        cols = detect_collisions([(0, 0, 100, 100)], [(50, 50, 150, 150)], margin=0)
        assert len(cols) == 1
        assert cols[0].kind == "rect-rect"
        assert cols[0].separation != (0, 0)

    def test_rect_rect_no_collision(self):
        from cis2hdl.core.writer.overlap_detector import detect_collisions

        cols = detect_collisions([(0, 0, 100, 100)], [(500, 500, 600, 600)], margin=0)
        assert cols == []

    def test_point_in_rect(self):
        from cis2hdl.core.writer.overlap_detector import detect_collisions

        cols = detect_collisions([(60, 60)], [(0, 0, 100, 100)], margin=0)
        assert len(cols) == 1
        assert cols[0].kind == "point-rect"

    def test_point_outside_margin(self):
        from cis2hdl.core.writer.overlap_detector import detect_collisions

        # margin=25 时点距矩形 30 → 无碰撞。
        cols = detect_collisions([(130, 60)], [(0, 0, 100, 100)], margin=25)
        assert cols == []

    def test_segment_crosses_rect(self):
        from cis2hdl.core.writer.overlap_detector import detect_collisions

        cols = detect_collisions([(0, 50, 200, 50)], [(0, 0, 100, 100)], margin=0)
        assert len(cols) == 1
        assert cols[0].kind == "segment-rect"

    def test_segment_segment_cross(self):
        from cis2hdl.core.writer.overlap_detector import detect_collisions

        cols = detect_collisions(
            [(0, 0, 100, 0)], [(50, -50, 50, 50)], margin=0,
        )
        assert len(cols) == 1
        assert cols[0].kind == "segment-segment"

    def test_margin_expansion(self):
        from cis2hdl.core.writer.overlap_detector import detect_collisions

        # 贴边（相距 0）无 margin 不算；margin=10 算。
        assert detect_collisions([(100, 0, 200, 100)], [(0, 0, 100, 100)], margin=0) == []
        cols = detect_collisions([(100, 0, 200, 100)], [(0, 0, 100, 100)], margin=10)
        assert len(cols) == 1


class TestOverlapResolver:
    def test_point_pushed_out_of_rect(self):
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        res = OverlapResolver(max_iter=4).resolve(
            {"gnd": (60, 60)}, [(0, 0, 100, 100)],
        )
        assert res.collisions_before == 1
        assert res.collisions_after == 0
        assert "gnd" in res.displacements

    def test_no_collision_no_move(self):
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        res = OverlapResolver().resolve(
            {"gnd": (500, 500)}, [(0, 0, 100, 100)],
        )
        assert res.displacements == {}

    def test_rect_pushed_fully_out(self):
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        res = OverlapResolver(max_iter=4).resolve(
            {"label": (0, 0, 100, 100)}, [(50, 50, 150, 150)],
        )
        assert res.collisions_before == 1
        assert res.collisions_after == 0
        assert "label" in res.displacements

    def test_multiple_movables(self):
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        # 两个可动件各自挤压一个障碍（障碍不重叠 → 双双解出）。
        res = OverlapResolver(max_iter=4).resolve(
            {"gnd1": (60, 60), "gnd2": (560, 60)},
            [(0, 0, 100, 100), (500, 0, 600, 100)],
        )
        assert res.collisions_before == 2
        assert res.collisions_after == 0
        assert "gnd1" in res.displacements
        assert "gnd2" in res.displacements

    def test_fixed_not_moved(self):
        from cis2hdl.core.writer.overlap_resolver import OverlapResolver

        fixed = [(0, 0, 100, 100)]
        res = OverlapResolver(max_iter=2).resolve({"gnd": (60, 60)}, fixed)
        # 固定件（芯片本体）不被移动 —— 位移表只含可动件。
        assert res.displacements.keys() == {"gnd"}
