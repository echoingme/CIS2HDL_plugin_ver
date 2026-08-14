"""Phase XVII M4 — wire_simplifier（SKiDL cleanup_wires 移植）。

Covers:
  * merge_segments（共线重叠合并）
  * trim_stubs（悬空 stub 删除）
  * remove_jogs（3 段阶梯 → 2 段直角 + 避让）
  * add_junctions（仅 T/X 真交点，排除直角端点相接）
  * long_wire_report（超长电线阈值）
"""

from __future__ import annotations


class TestMergeSegments:
    def test_merge_overlapping_horizontal(self):
        from cis2hdl.core.writer.wire_simplifier import merge_segments

        merged = merge_segments([
            (0, 0, 100, 0), (50, 0, 150, 0),
            (0, 50, 200, 50), (0, 50, 300, 50),
        ])
        assert (0, 0, 150, 0) in merged
        assert (0, 50, 300, 50) in merged
        assert len(merged) == 2

    def test_merge_overlapping_vertical(self):
        from cis2hdl.core.writer.wire_simplifier import merge_segments

        merged = merge_segments([(100, 0, 100, 50), (100, 25, 100, 100)])
        assert (100, 0, 100, 100) in merged

    def test_no_merge_non_collinear(self):
        from cis2hdl.core.writer.wire_simplifier import merge_segments

        merged = merge_segments([(0, 0, 100, 0), (0, 50, 100, 50)])
        assert len(merged) == 2


class TestTrimStubs:
    def test_remove_dangling_segment(self):
        from cis2hdl.core.writer.wire_simplifier import trim_stubs

        # 悬空段 (300,0)-(400,0) 连不到任何引脚。
        wires = [(0, 0, 100, 0), (100, 0, 100, 50), (300, 0, 400, 0)]
        pins = [(0, 0), (100, 50)]
        kept = trim_stubs(wires, pins)
        assert (300, 0, 400, 0) not in kept
        assert (0, 0, 100, 0) in kept

    def test_keep_all_when_all_anchored(self):
        from cis2hdl.core.writer.wire_simplifier import trim_stubs

        wires = [(0, 0, 100, 0), (100, 0, 100, 50)]
        pins = [(0, 0), (100, 50)]
        kept = trim_stubs(wires, pins)
        assert len(kept) == 2


class TestRemoveJogs:
    def test_hvh_jog_to_l(self):
        from cis2hdl.core.writer.wire_simplifier import remove_jogs

        jogged = remove_jogs([
            (0, 0, 100, 0), (100, 0, 100, 50), (100, 50, 200, 50),
        ])
        # 3 段 → 2 段直角，两端点保持（(0,0) 与 (200,50) 连通）。
        assert len(jogged) == 2
        # 终点 (200,50) 由末段垂直段到达。
        assert any(s[2] == 200 and s[3] == 50 for s in jogged)
        # 起点 (0,0) 保留。
        assert any(s[0] == 0 and s[1] == 0 for s in jogged)

    def test_vhv_jog_to_l(self):
        from cis2hdl.core.writer.wire_simplifier import remove_jogs

        jogged = remove_jogs([
            (0, 0, 0, 100), (0, 100, 50, 100), (50, 100, 50, 200),
        ])
        assert len(jogged) == 2

    def test_jog_blocked_by_obstacle(self):
        from cis2hdl.core.writer.wire_simplifier import remove_jogs

        wires = [
            (0, 0, 100, 0), (100, 0, 100, 50), (100, 50, 200, 50),
        ]
        jogged = remove_jogs(wires, obstacles=[(0, 0, 300, 50)])
        # 两条候选 L 都被障碍挡住 → 保持 3 段。
        assert len(jogged) == 3


class TestAddJunctions:
    def test_t_junction_only(self):
        from cis2hdl.core.writer.wire_simplifier import add_junctions

        # T 型（100,0）：竖段端点落在横段内部 → 真交点。
        junctions = add_junctions([
            (0, 0, 200, 0), (100, -50, 100, 50),
        ])
        assert (100, 0) in junctions

    def test_excludes_right_angle_corner(self):
        from cis2hdl.core.writer.wire_simplifier import add_junctions

        # L 形直角端点相接 → 不产生 DOT。
        junctions = add_junctions([
            (0, 0, 100, 0), (100, 0, 100, 50),
        ])
        assert (100, 0) not in junctions

    def test_x_crossing_junction(self):
        from cis2hdl.core.writer.wire_simplifier import add_junctions

        junctions = add_junctions([
            (0, 50, 200, 50), (100, 0, 100, 100),
        ])
        assert (100, 50) in junctions


class TestLongWireReport:
    def test_long_segments_detected(self):
        from cis2hdl.core.writer.wire_simplifier import long_wire_report

        long = long_wire_report([(0, 0, 6000, 0), (0, 0, 100, 0)], 5000)
        assert len(long) == 1
        assert long[0] == (0, 0, 6000, 0)


class TestSimplifyWires:
    def test_end_to_end(self):
        from cis2hdl.core.writer.wire_simplifier import simplify_wires

        # 悬空 + 重叠 + jog 混合。
        wires = [
            (0, 0, 100, 0), (50, 0, 150, 0),        # 重叠水平
            (150, 0, 150, 50), (150, 50, 250, 50),  # jog 阶梯
            (400, 0, 500, 0),                       # 悬空
        ]
        pins = [(0, 0), (250, 50)]
        res = simplify_wires(wires, pins, dot_merge=50, max_wire_len=5000)
        assert (400, 0, 500, 0) not in res.wires
        # 悬空段被删；jog 化简后段数 < 原段数。
        assert len(res.wires) < len(wires)
