"""Phase XVIII R8 — 电线长度限制（split_long_wires）。

Covers:
  * `split_long_wires`：超 max_wire_len 线段拆分 + 断口标签坐标
  * 短线段保持不动、方向保持
"""

from __future__ import annotations


class TestSplitLongWires:
    def test_short_stays(self):
        from cis2hdl.core.writer.wire_simplifier import split_long_wires

        segs, breaks = split_long_wires([(0, 0, 1000, 0)], max_len=5000)
        assert segs == [(0, 0, 1000, 0)]
        assert breaks == []

    def test_long_split_into_pieces(self):
        from cis2hdl.core.writer.wire_simplifier import split_long_wires

        segs, breaks = split_long_wires(
            [(0, 0, 6000, 0)], max_len=5000, segment_len=2500,
        )
        assert len(segs) == 3
        assert segs[0] == (0, 0, 2500, 0)
        assert segs[1] == (2500, 0, 5000, 0)
        assert segs[2] == (5000, 0, 6000, 0)
        assert len(breaks) == 3  # 每个断口两端标签坐标

    def test_vertical_split(self):
        from cis2hdl.core.writer.wire_simplifier import split_long_wires

        segs, _ = split_long_wires(
            [(0, 0, 0, 6000)], max_len=5000, segment_len=2500,
        )
        assert len(segs) == 3
        assert all(s[0] == s[2] == 0 for s in segs)  # x 不变

    def test_direction_preserved(self):
        """负方向长段拆分后仍保持方向。"""
        from cis2hdl.core.writer.wire_simplifier import split_long_wires

        segs, _ = split_long_wires(
            [(6000, 0, 0, 0)], max_len=5000, segment_len=2500,
        )
        # 首段从 6000 开始递减
        assert segs[0][0] == 6000
        assert segs[0][2] == 5000
        assert segs[-1][2] == 0

    def test_exact_limit_kept(self):
        from cis2hdl.core.writer.wire_simplifier import split_long_wires

        segs, breaks = split_long_wires([(0, 0, 5000, 0)], max_len=5000)
        assert len(segs) == 1
        assert breaks == []
